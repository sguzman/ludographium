#!/usr/bin/env python3
"""Materialize the entire pinned game-metadata corpus into an offline SQLite file.

Every registered source observation, exact media entry, and bibliographic field
claim is included, including unmatched/ambiguous claims. This is not an inferred
work-identity registry; no title merging, ROM downloads or manual curation.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE provenance (
    key TEXT PRIMARY KEY,
    json_value TEXT NOT NULL
);
CREATE TABLE platforms (
    platform TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_blob_sha TEXT NOT NULL,
    source_license TEXT,
    dat_version TEXT,
    source_record_count INTEGER NOT NULL,
    media_count INTEGER NOT NULL
);
CREATE TABLE games (
    platform TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL CHECK(source_ordinal > 0),
    title TEXT NOT NULL,
    region TEXT,
    serial TEXT,
    source_fields_json TEXT NOT NULL,
    PRIMARY KEY (platform, source_ordinal),
    FOREIGN KEY (platform) REFERENCES platforms(platform)
);
CREATE TABLE media (
    platform TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL,
    media_ordinal INTEGER NOT NULL,
    name TEXT NOT NULL,
    size INTEGER NOT NULL CHECK(size >= 0),
    sha1 TEXT,
    crc32 TEXT,
    md5 TEXT,
    serial TEXT,
    source_fields_json TEXT NOT NULL,
    PRIMARY KEY (platform, source_ordinal, media_ordinal),
    FOREIGN KEY (platform, source_ordinal) REFERENCES games(platform, source_ordinal)
);
CREATE TABLE claims (
    platform TEXT NOT NULL,
    claim_ordinal INTEGER NOT NULL CHECK(claim_ordinal > 0),
    source_id TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_blob_sha TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL,
    field TEXT NOT NULL,
    value TEXT,
    crc32 TEXT NOT NULL,
    source_comment TEXT,
    source_fields_json TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    base_source_ordinal INTEGER,
    PRIMARY KEY (platform, claim_ordinal),
    FOREIGN KEY (platform) REFERENCES platforms(platform),
    FOREIGN KEY (platform, base_source_ordinal)
      REFERENCES games(platform, source_ordinal),
    CHECK (
        (resolution_status = 'matched' AND base_source_ordinal IS NOT NULL)
        OR
        (resolution_status != 'matched' AND base_source_ordinal IS NULL)
    )
);
CREATE INDEX idx_game_title ON games(title COLLATE NOCASE);
CREATE INDEX idx_media_sha1 ON media(sha1, size);
CREATE INDEX idx_media_crc ON media(crc32, size);
CREATE INDEX idx_claim_base ON claims(platform, base_source_ordinal, field);
CREATE INDEX idx_claim_field ON claims(field, resolution_status);
CREATE VIEW matched_metadata AS
    SELECT g.platform, g.source_ordinal, g.title,
           c.field, c.value, c.source_id, c.source_revision,
           c.source_path, c.source_blob_sha, c.source_ordinal AS claim_source_ordinal,
           c.crc32, c.source_comment
    FROM games AS g JOIN claims AS c
      ON c.platform = g.platform AND c.base_source_ordinal = g.source_ordinal
    WHERE c.resolution_status = 'matched';
"""


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def input_json(root, filename, manifest=None):
    raw = (root / filename).read_bytes()
    if manifest is not None:
        rows = [row for row in manifest["artifacts"] if row["path"] == filename]
        if (len(rows) != 1 or rows[0]["bytes"] != len(raw)
                or rows[0]["sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError(f"distribution integrity mismatch: {filename}")
    return json.loads(raw)


def source_inputs(root):
    distribution = input_json(root, "generated/v1/distribution.json")
    if distribution.get("schema_version") != 1 or distribution.get("kind") != "ludographium-distribution":
        raise ValueError("unsupported integrity manifest")
    catalog = input_json(root, "generated/v1/catalog.json", distribution)
    if catalog.get("schema_version") != 1 or catalog.get("kind") != "source-catalog":
        raise ValueError("unsupported source catalog")
    field_registry = input_json(root, "sources/libretro-enrichment.json", distribution)
    base_registry = input_json(root, "sources/libretro-no-intro.json", distribution)
    if (catalog["source_revision"] != distribution["source_revision"]
            or field_registry["repository_revision"] != catalog["source_revision"]
            or base_registry["repository_revision"] != catalog["source_revision"]):
        raise ValueError("pinned source revisions differ")
    return distribution, catalog, base_registry, field_registry


def populate(conn, root):
    manifest, catalog, base_registry, field_registry = source_inputs(root)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO provenance VALUES (?, ?)",
                 ("catalog", compact(catalog)))
    conn.execute("INSERT INTO provenance VALUES (?, ?)",
                 ("base_source", compact(base_registry)))
    conn.execute("INSERT INTO provenance VALUES (?, ?)",
                 ("bibliographic_source", compact(field_registry)))
    notice = (root / "METADATA-NOTICE.md").read_text(encoding="utf-8")
    conn.execute("INSERT INTO provenance VALUES (?, ?)",
                 ("rights_notice", compact(notice)))
    totals = Counter()
    for entry in catalog["platforms"]:
        platform = entry["platform"]
        base = input_json(root, entry["artifact_path"], manifest)
        extra = input_json(root, f"generated/enrichment-v1/{platform}.json", manifest)
        if (base.get("platform") != platform or extra.get("platform") != platform
                or base["source_revision"] != catalog["source_revision"]
                or extra["base_source_id"] != base["source_id"]
                or extra["base_source_revision"] != base["source_revision"]
                or extra["source_revision"] != catalog["source_revision"]):
            raise ValueError(f"source mismatch for {platform}")

        records = base["records"]
        if len(records) != base["record_count"] or len(records) != entry["source_records"]:
            raise ValueError(f"source record count mismatch: {platform}")
        media_count = sum(len(row["roms"]) for row in records)
        if media_count != base["rom_count"] or media_count != entry["rom_fingerprints"]:
            raise ValueError(f"media count mismatch: {platform}")
        conn.execute(
            "INSERT INTO platforms VALUES (?,?,?,?,?,?,?,?,?)",
            (platform, base["source_id"], base["source_revision"],
             base["source_path"], base["source_blob_sha"],
             base.get("source_license"), base.get("dat_version"),
             len(records), media_count),
        )
        crc_index = {}
        record_by_ordinal = {}
        for record in records:
            ordinal = record["source_ordinal"]
            if ordinal in record_by_ordinal:
                raise ValueError(f"duplicate source ordinal: {platform}:{ordinal}")
            record_by_ordinal[ordinal] = record
            conn.execute(
                "INSERT INTO games VALUES (?,?,?,?,?,?)",
                (platform, ordinal, record["name"], record.get("region"),
                 record.get("serial"),
                 compact({key: value for key, value in record.items()
                          if key not in {"source_ordinal", "name", "roms"}})),
            )
            for media_ordinal, media in enumerate(record["roms"], 1):
                conn.execute(
                    "INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (platform, ordinal, media_ordinal, media["name"],
                     media["size"], media.get("sha1"), media.get("crc32"),
                     media.get("md5"), media.get("serial"), compact(media)),
                )
                if media.get("crc32"):
                    crc_index.setdefault((ordinal, media["crc32"]), True)
        if extra["claim_count"] != len(extra["claims"]):
            raise ValueError(f"claim count mismatch: {platform}")
        seen_status = Counter()
        for claim_ordinal, claim in enumerate(extra["claims"], 1):
            resolution = claim["resolution"]
            status = resolution["status"]
            target = resolution["base_source_ordinal"]
            if status == "matched":
                record = record_by_ordinal.get(target)
                if (record is None or record["name"] != claim["source_comment"]
                        or (target, claim["crc32"]) not in crc_index):
                    raise ValueError(f"invalid source-to-claim join: {platform}:{claim_ordinal}")
            elif target is not None:
                raise ValueError(f"unresolved claim has source join: {platform}:{claim_ordinal}")
            conn.execute(
                "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (platform, claim_ordinal, extra["source_id"], extra["source_revision"],
                 claim["source_path"], claim["source_blob_sha"], claim["source_ordinal"],
                 claim["field"], claim["value"], claim["crc32"], claim["source_comment"],
                 compact(claim["source_fields"]), status, target),
            )
            seen_status[status] += 1
        if dict(sorted(seen_status.items())) != extra["resolution_counts"]:
            raise ValueError(f"field-claim status totals differ: {platform}")
        totals.update({
            "games": len(records),
            "media": media_count,
            "claims": len(extra["claims"]),
            "matched": seen_status["matched"],
        })
    conn.commit()
    return dict(totals)


def counts(conn):
    numbers = {}
    for name in ("games", "media", "claims"):
        numbers[name] = conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    numbers["matched"] = conn.execute(
        "SELECT count(*) FROM claims WHERE resolution_status='matched'"
    ).fetchone()[0]
    numbers["platforms"] = conn.execute("SELECT count(*) FROM platforms").fetchone()[0]
    numbers["with_metadata"] = conn.execute(
        "SELECT count(*) FROM games AS g WHERE EXISTS "
        "(SELECT 1 FROM claims AS c WHERE c.platform=g.platform "
        "AND c.base_source_ordinal=g.source_ordinal AND c.resolution_status='matched')"
    ).fetchone()[0]
    return numbers


def validate(conn, root=None):
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise ValueError("SQLite integrity check failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("SQLite foreign-key check failed")
    actual = counts(conn)
    if root is not None:
        _, catalog, _, _ = source_inputs(root)
        coverage = input_json(root, "reports/enrichment-coverage-v1.json")
        if actual["games"] != sum(x["source_records"] for x in catalog["platforms"]):
            raise ValueError("source record count differs from catalog")
        if actual["media"] != sum(x["rom_fingerprints"] for x in catalog["platforms"]):
            raise ValueError("media count differs from catalog")
        if actual["claims"] != coverage["total_claims"]:
            raise ValueError("bibliographic claim count differs from audit")
        if actual["matched"] != coverage["resolution_counts"]["matched"]:
            raise ValueError("matched claim count differs from audit")
        if actual["platforms"] != len(catalog["platforms"]):
            raise ValueError("platform count differs from catalog")
    return actual


def build(root, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".ludographium-corpus-", suffix=".sqlite", dir=destination.parent
    )
    os.close(fd)
    try:
        with sqlite3.connect(temporary) as conn:
            conn.execute("PRAGMA page_size=4096")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
            populate(conn, root)
            conn.execute("VACUUM")
            actual = validate(conn, root)
        os.replace(temporary, destination)
        return actual
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def open_readonly(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)


def query(conn, *, platform=None, title=None, sha1=None, limit=20):
    if title is not None and sha1 is not None:
        raise ValueError("choose either title or SHA-1")
    if title is None and sha1 is None:
        raise ValueError("query needs a title or SHA-1")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be in 1..100")
    filters, args = [], []
    if platform:
        filters.append("g.platform=?")
        args.append(platform)
    if title is not None:
        if not title.strip():
            raise ValueError("title must be nonempty")
        # SQLite LIKE escapes user wildcards so search is literal substring.
        filters.append("instr(lower(g.title), lower(?)) > 0")
        args.append(title)
    else:
        if len(sha1) != 40 or any(c not in "0123456789abcdefABCDEF" for c in sha1):
            raise ValueError("SHA-1 must be 40 hexadecimal characters")
        filters.append("EXISTS (SELECT 1 FROM media m WHERE m.platform=g.platform "
                       "AND m.source_ordinal=g.source_ordinal AND m.sha1=?)")
        args.append(sha1.upper())
    sql = ("SELECT g.platform,g.source_ordinal,g.title,g.region,g.serial,g.source_fields_json,"
           "p.source_id,p.source_revision,p.source_path,p.source_blob_sha,p.source_license "
           "FROM games g JOIN platforms p ON p.platform=g.platform WHERE "
           + " AND ".join(filters)
           + " ORDER BY g.platform,g.source_ordinal LIMIT ?")
    matches = []
    for platform_id, ordinal, name, region, serial, fields, src_id, src_rev, src_path, blob, license_id in conn.execute(sql, (*args, limit)):
        media = [json.loads(m[0]) for m in conn.execute(
            "SELECT source_fields_json FROM media WHERE platform=? AND source_ordinal=? ORDER BY media_ordinal",
            (platform_id, ordinal),
        )]
        claims = [
            {
                "field": row[0], "value": row[1], "source_id": row[2],
                "source_revision": row[3], "source_path": row[4],
                "source_blob_sha": row[5], "source_ordinal": row[6],
                "crc32": row[7],
            }
            for row in conn.execute(
                "SELECT field,value,source_id,source_revision,source_path,"
                "source_blob_sha,source_ordinal,crc32 FROM claims "
                "WHERE platform=? AND base_source_ordinal=? AND resolution_status='matched' "
                "ORDER BY field,claim_ordinal", (platform_id, ordinal),
            )
        ]
        matches.append({
            "platform": platform_id, "title": name, "region": region,
            "serial": serial, "source_fields": json.loads(fields),
            "source": {
                "source_id": src_id, "source_revision": src_rev,
                "source_path": src_path, "source_blob_sha": blob,
                "source_ordinal": ordinal, "source_license": license_id,
            },
            "media": media, "metadata_claims": claims,
        })
    return {"match_count": len(matches), "matches": matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--db", type=Path, help="destination for build, existing file otherwise")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--title", help="search a literal title substring")
    mode.add_argument("--sha1", help="search exact media SHA-1")
    parser.add_argument("--platform")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    destination = args.db or Path("/tmp/ludographium-corpus.sqlite")
    if args.build:
        if args.platform or args.limit != 20:
            parser.error("search options require title or SHA-1")
        result = build(args.root, destination)
        print(json.dumps({"database": str(destination), **result}, sort_keys=True))
        return
    with open_readonly(destination) as conn:
        if args.verify:
            if args.platform or args.limit != 20:
                parser.error("search options require title or SHA-1")
            result = validate(conn, args.root)
            print("PASS: all source records, media entries, and field claims verified " +
                  json.dumps(result, sort_keys=True))
        elif args.summary:
            print(json.dumps(counts(conn), sort_keys=True, indent=2))
        else:
            print(json.dumps(query(conn, platform=args.platform, title=args.title,
                                   sha1=args.sha1, limit=args.limit),
                             ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
