#!/usr/bin/env python3
"""Bulk-attach all pinned extra field-DAT observations without per-game curation.

Reads a complete expanded source SQLite, appends original field-DAT claims from
all registered sources, and keeps unresolved ones visible. Exact, unambiguous
CRC32 plus exact title matches are evidence associations, not game identities.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

from build_corpus import counts, open_readonly
from build_expanded_corpus import git_blob, pinned_manifest, retrieve, validate_expanded, PLATFORM, HEX_SHA
from import_enrichment import parse_field_dat

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "sources/bulk-fields-v1.json"
FIELD_ARCHIVES = """
CREATE TABLE field_archives (
    platform TEXT NOT NULL,
    field TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_blob_sha TEXT NOT NULL,
    dat_bytes BLOB NOT NULL,
    PRIMARY KEY (platform, field),
    FOREIGN KEY (platform) REFERENCES platforms(platform)
);
"""


def field_manifest(root):
    manifest = json.loads((root / MANIFEST).read_bytes())
    if (manifest.get("schema_version") != 1
            or manifest.get("kind") != "pinned-bulk-bibliographic-expansion"
            or manifest.get("source_id") != "libretro-metadata"
            or manifest.get("base_source_id") != "libretro-no-intro"
            or manifest.get("declared_repository_license") != "CC-BY-SA-4.0"
            or manifest.get("repository") != "https://github.com/libretro/libretro-database"
            or not HEX_SHA.fullmatch(manifest["repository_revision"])):
        raise ValueError("unsupported bulk bibliographic source manifest")
    base = pinned_manifest(root)
    if manifest["repository_revision"] != base["repository_revision"]:
        raise ValueError("metadata and identification sources must share pinned revision")
    allowed_platforms = {e["platform"] for e in base["platforms"]}
    allowed_fields = {
        "developer", "publisher", "genre", "franchise", "serial",
        "releaseyear", "releasemonth", "users", "esrb_rating", "rumble",
    }
    directory = {
        "developer": "developer", "publisher": "publisher", "genre": "genre",
        "franchise": "franchise", "serial": "serial",
        "releaseyear": "releaseyear", "releasemonth": "releasemonth",
        "users": "maxusers", "esrb_rating": "esrb", "rumble": "rumble",
    }
    names = set()
    labels = {p["platform"]: p["label"] for p in base["platforms"]}
    for entry in manifest["files"]:
        platform, field = entry["platform"], entry["field"]
        if (platform not in allowed_platforms or field not in allowed_fields
                or (platform, field) in names):
            raise ValueError(f"unknown, repeated or unsafe source metadata field: {platform}/{field}")
        names.add((platform, field))
        if entry["source_path"] != f"metadat/{directory[field]}/{labels[platform]}.dat":
            raise ValueError(f"field metadata provenance path mismatch: {platform}/{field}")
        if (not HEX_SHA.fullmatch(entry["git_blob_sha"])
                or type(entry["bytes"]) is not int or not 0 < entry["bytes"] < 50_000_000):
            raise ValueError(f"invalid source metadata hash or size: {platform}/{field}")
    if not names:
        raise ValueError("empty field source manifest")
    return manifest


def ingest(root, expanded_db, target, manifest, *, cache_dir=None, workers=12):
    shutil.copyfile(expanded_db, target)
    files = sorted(manifest["files"], key=lambda e: (e["platform"], e["field"]))
    # Reuse the pinned byte downloader but use unique cache keys by platform + field.
    namespaced = [
        {**entry, "platform": f"{entry['platform']}--{entry['field']}"}
        for entry in files
    ]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        raw_sources = dict(pool.map(
            lambda entry: retrieve(entry, manifest["repository_revision"], cache_dir),
            namespaced,
        ))
    with sqlite3.connect(target) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        base = counts(conn)
        source_manifest = pinned_manifest(root)
        validate_expanded(conn, source_manifest)
        conn.executescript(FIELD_ARCHIVES)
        conn.execute("INSERT INTO provenance VALUES (?,?)",
                     ("bulk_fields", json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))))
        source_index = {}
        extra_status = Counter()
        with_claims = set()
        claim_number = defaultdict(int)
        for source in files:
            platform, field = source["platform"], source["field"]
            key = f"{platform}--{field}"
            raw = raw_sources[key]
            conn.execute(
                "INSERT INTO field_archives VALUES (?,?,?,?,?)",
                (platform, field, source["source_path"], source["git_blob_sha"], raw),
            )
            if platform not in source_index:
                grouped = defaultdict(list)
                rows = conn.execute(
                    "SELECT m.crc32,g.source_ordinal,g.title FROM media m "
                    "JOIN games g ON g.platform=m.platform AND g.source_ordinal=m.source_ordinal "
                    "WHERE m.platform=? AND m.crc32 IS NOT NULL", (platform,),
                )
                for crc, ordinal, title in rows:
                    grouped[crc].append((ordinal, title))
                source_index[platform] = grouped
            crc_index = source_index[platform]
            parsed = parse_field_dat(raw, field=field)
            status_counts = Counter()
            for record in parsed:
                candidates = crc_index.get(record["crc32"], [])
                if record["value"] is None:
                    status, target_ordinal = "missing_value", None
                elif not candidates:
                    status, target_ordinal = "unmatched_crc", None
                elif len(candidates) > 1:
                    status, target_ordinal = "ambiguous_crc", None
                elif record["comment"] is None:
                    status, target_ordinal = "missing_comment", None
                elif candidates[0][1] != record["comment"]:
                    status, target_ordinal = "comment_mismatch", None
                else:
                    status, target_ordinal = "matched", candidates[0][0]
                    with_claims.add((platform, target_ordinal))
                claim_number[platform] += 1
                conn.execute(
                    "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (platform, claim_number[platform], manifest["source_id"],
                     manifest["repository_revision"], source["source_path"],
                     source["git_blob_sha"], record["source_ordinal"],
                     field, record["value"], record["crc32"], record["comment"],
                     json.dumps(record["source_fields"], ensure_ascii=False, separators=(",", ":")),
                     status, target_ordinal),
                )
                status_counts[status] += 1
            extra_status.update(status_counts)
            print(f"FIELD {platform}/{field}: {len(parsed)} observations; "
                  + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items())), flush=True)
        conn.commit()
        conn.execute("VACUUM")
        numbers = counts(conn)
        expected = {
            **base,
            "claims": base["claims"] + sum(extra_status.values()),
            "matched": base["matched"] + extra_status["matched"],
            "with_metadata": base["with_metadata"] + len(with_claims),
        }
        if numbers != expected:
            raise ValueError(f"bulk bibliographic coverage mismatch: {numbers} != {expected}")
        validate_fields(conn, manifest, expected=expected)
        return numbers


def validate_fields(conn, manifest, expected=None):
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("bibliographic corpus SQLite integrity check failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("bibliographic corpus SQLite foreign-key check failed")
    if conn.execute("SELECT count(*) FROM field_archives").fetchone()[0] != len(manifest["files"]):
        raise ValueError("archived metadata DAT inventory differs")
    for f in manifest["files"]:
        row = conn.execute(
            "SELECT source_path,source_blob_sha,dat_bytes FROM field_archives "
            "WHERE platform=? AND field=?", (f["platform"], f["field"]),
        ).fetchone()
        if (row is None or row[0] != f["source_path"]
                or row[1] != f["git_blob_sha"]
                or len(row[2]) != f["bytes"] or git_blob(row[2]) != f["git_blob_sha"]):
            raise ValueError(f"field archive source corruption: {f['platform']}/{f['field']}")
    observed = counts(conn)
    if expected is not None and observed != expected:
        raise ValueError(f"field corpus coverage differs: {observed} != {expected}")
    return observed


def build(root, expanded_db, destination, *, cache_dir=None, workers=12):
    manifest = field_manifest(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".ludographium-fields-", suffix=".sqlite", dir=destination.parent
    )
    os.close(fd)
    try:
        result = ingest(root, expanded_db, temporary, manifest, cache_dir=cache_dir, workers=workers)
        os.replace(temporary, destination)
        return result
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--db", type=Path, default=Path("/tmp/ludographium-enriched-expanded.sqlite"))
    p.add_argument("--from-db", type=Path, dest="from_db")
    p.add_argument("--source-dir", type=Path)
    p.add_argument("--workers", type=int, default=12)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--title")
    mode.add_argument("--sha1")
    p.add_argument("--platform")
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    if not 1 <= args.workers <= 24:
        p.error("--workers must be 1..24")
    if args.build:
        if not args.from_db or args.from_db == args.db:
            p.error("--build needs a separate --from-db source")
        result = build(args.root, args.from_db, args.db, cache_dir=args.source_dir, workers=args.workers)
    else:
        with open_readonly(args.db) as conn:
            if args.verify:
                result = validate_fields(conn, field_manifest(args.root))
                # Validate platform archive evidence as well.
                validate_expanded(conn, pinned_manifest(args.root))
            elif args.summary:
                result = counts(conn)
            else:
                result = query(conn, platform=args.platform, title=args.title,
                               sha1=args.sha1, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
