#!/usr/bin/env python3
"""Generate a disposable, provenance-first SQLite reader for pinned MAME sources.

The checked-in XML/JSONL source observations remain canonical. This derived
database is deliberately never committed, released, or uploaded as a CI
artifact. Exact SHA-1 links are media evidence, not game/release identity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata

from acquire_mame_softlists import ROOT, source_register, verify_one
from query_mame_sources import original_index_rows
from query_mame_media import INDEX as LINKS_PATH, REPORT as LINKS_REPORT
from import_dat import import_dat
from build_expanded_corpus import pinned_manifest

ORIGINAL_REPORTS = (
    "reports/mame-software-observations-v1-summary.json",
    "reports/mame-software-observations-v2-summary.json",
)
CONFLICTS = Path("data/reconciliation/mame-libretro-sha1-v1/size-disagreements.jsonl")
TITLE_REPORT = Path("reports/mame-libretro-title-review-v1-summary.json")
TITLE_CANDIDATES = Path("data/reconciliation/mame-libretro-title-review-v1/candidates.jsonl")
EXPECTED = {
    "source_lists": 65,
    "software": 32953,
    "libretro_sources": 75,
    "libretro_records": 117145,
    "libretro_media": 117145,
    "links": 19025,
    "conflicts": 1,
    "title_review": 6825,
}
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE provenance (
    source_path TEXT PRIMARY KEY,
    original_sha256 TEXT NOT NULL,
    source_bytes INTEGER NOT NULL
);
CREATE TABLE source_lists (
    source_list TEXT PRIMARY KEY,
    cohort TEXT NOT NULL CHECK (cohort IN ('v1','v2')),
    original_xml_path TEXT NOT NULL,
    original_xml_sha256 TEXT NOT NULL,
    original_index_path TEXT NOT NULL,
    original_index_sha256 TEXT NOT NULL,
    original_entries INTEGER NOT NULL,
    source_license TEXT NOT NULL CHECK (source_license='CC0-1.0')
);
CREATE TABLE software (
    source_list TEXT NOT NULL REFERENCES source_lists(source_list),
    source_ordinal INTEGER NOT NULL CHECK (source_ordinal > 0),
    software_name TEXT NOT NULL,
    title_literal TEXT,
    publisher_literal TEXT,
    year_literal TEXT,
    original_json TEXT NOT NULL,
    PRIMARY KEY(source_list,source_ordinal)
);
CREATE TABLE serial_claims (
    source_list TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL,
    serial_ordinal INTEGER NOT NULL,
    serial_literal TEXT NOT NULL,
    PRIMARY KEY(source_list,source_ordinal,serial_ordinal),
    FOREIGN KEY(source_list,source_ordinal)
      REFERENCES software(source_list,source_ordinal)
);
CREATE TABLE media_claims (
    source_list TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL,
    media_ordinal INTEGER NOT NULL,
    media_kind TEXT NOT NULL CHECK (media_kind IN ('rom','disk')),
    media_name TEXT,
    sha1 TEXT,
    crc32 TEXT,
    declared_size_bytes INTEGER,
    original_json TEXT NOT NULL,
    PRIMARY KEY(source_list,source_ordinal,media_ordinal),
    FOREIGN KEY(source_list,source_ordinal)
      REFERENCES software(source_list,source_ordinal)
);
CREATE TABLE libretro_sources (
    platform TEXT PRIMARY KEY,
    original_dat_path TEXT NOT NULL,
    original_git_blob_sha TEXT NOT NULL,
    original_dat_sha256 TEXT NOT NULL,
    original_records INTEGER NOT NULL,
    source_license TEXT NOT NULL CHECK(source_license='CC-BY-SA-4.0')
);
CREATE TABLE libretro_records (
    platform TEXT NOT NULL REFERENCES libretro_sources(platform),
    source_ordinal INTEGER NOT NULL CHECK(source_ordinal>0),
    title_literal TEXT NOT NULL,
    region_literal TEXT,
    serial_literal TEXT,
    original_json TEXT NOT NULL,
    PRIMARY KEY(platform,source_ordinal)
);
CREATE TABLE libretro_media (
    platform TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL,
    media_ordinal INTEGER NOT NULL,
    sha1 TEXT NOT NULL,
    media_size_bytes INTEGER NOT NULL CHECK(media_size_bytes>=0),
    media_name TEXT NOT NULL,
    original_json TEXT NOT NULL,
    PRIMARY KEY(platform,source_ordinal,media_ordinal),
    FOREIGN KEY(platform,source_ordinal)
      REFERENCES libretro_records(platform,source_ordinal)
);
CREATE TABLE exact_media_links (
    source_ordinal INTEGER PRIMARY KEY,
    mame_list TEXT NOT NULL,
    mame_software_ordinal INTEGER NOT NULL,
    mame_media_ordinal INTEGER NOT NULL,
    libretro_platform TEXT NOT NULL,
    libretro_software_ordinal INTEGER NOT NULL,
    libretro_media_ordinal INTEGER NOT NULL,
    media_sha1 TEXT NOT NULL,
    media_size_bytes INTEGER NOT NULL,
    original_json TEXT NOT NULL,
    FOREIGN KEY(mame_list,mame_software_ordinal,mame_media_ordinal)
      REFERENCES media_claims(source_list,source_ordinal,media_ordinal),
    FOREIGN KEY(libretro_platform,libretro_software_ordinal,libretro_media_ordinal)
      REFERENCES libretro_media(platform,source_ordinal,media_ordinal)
);
CREATE TABLE title_review_candidates (
    source_ordinal INTEGER PRIMARY KEY,
    mame_list TEXT NOT NULL,
    mame_software_ordinal INTEGER NOT NULL,
    libretro_platform TEXT NOT NULL,
    libretro_software_ordinal INTEGER NOT NULL,
    normalized_title TEXT NOT NULL,
    scope_support INTEGER NOT NULL CHECK(scope_support>=3),
    original_json TEXT NOT NULL,
    FOREIGN KEY(mame_list,mame_software_ordinal)
      REFERENCES software(source_list,source_ordinal),
    FOREIGN KEY(libretro_platform,libretro_software_ordinal)
      REFERENCES libretro_records(platform,source_ordinal)
);
CREATE TABLE rejected_size_conflicts (
    source_ordinal INTEGER PRIMARY KEY,
    mame_list TEXT NOT NULL,
    mame_software_ordinal INTEGER NOT NULL,
    mame_media_ordinal INTEGER NOT NULL,
    media_sha1 TEXT NOT NULL,
    original_json TEXT NOT NULL,
    FOREIGN KEY(mame_list,mame_software_ordinal,mame_media_ordinal)
      REFERENCES media_claims(source_list,source_ordinal,media_ordinal)
);
CREATE INDEX idx_software_title ON software(title_literal COLLATE NOCASE);
CREATE INDEX idx_software_publisher ON software(publisher_literal COLLATE NOCASE);
CREATE INDEX idx_software_year ON software(year_literal);
CREATE INDEX idx_serial_literal ON serial_claims(serial_literal);
CREATE INDEX idx_media_sha1 ON media_claims(sha1);
CREATE INDEX idx_libretro_title ON libretro_records(title_literal COLLATE NOCASE);
CREATE INDEX idx_libretro_media_sha1 ON libretro_media(sha1);
CREATE INDEX idx_links_libretro ON exact_media_links(libretro_platform,libretro_software_ordinal);
CREATE INDEX idx_links_mame ON exact_media_links(mame_list,mame_software_ordinal);
CREATE INDEX idx_title_review_mame ON title_review_candidates(mame_list,mame_software_ordinal);
CREATE INDEX idx_title_review_libretro ON title_review_candidates(libretro_platform,libretro_software_ordinal);
CREATE VIEW original_mame_claims AS
    SELECT s.source_list,s.source_ordinal,s.software_name,
      s.title_literal,s.publisher_literal,s.year_literal,
      s.original_json,l.cohort,l.original_xml_sha256,l.source_license
    FROM software s JOIN source_lists l ON s.source_list=l.source_list;
"""


def source_bytes(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"symlinked source evidence: {relative}")
    return path.read_bytes()


def source_json(root, relative):
    return json.loads(source_bytes(root, relative))


def source_digest(root, relative):
    raw = source_bytes(root, relative)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def unicode_casefold(value):
    if value is None:
        return ""
    return unicodedata.normalize("NFKC", str(value)).casefold()


def numeric_size(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("original media size is not a source literal")
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
        return int(value, 16)
    if re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError(f"unexpected source media size: {value}")


def optional_sha1(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch("[0-9a-fA-F]{40}", value):
        raise ValueError("malformed original media SHA-1")
    return value.lower()


def libretro_original_scopes(root):
    original = source_json(root, Path("sources/libretro-no-intro.json"))
    expanded = pinned_manifest(root)
    if (
        original["source_id"] != expanded["source_id"]
        or original["repository_revision"] != expanded["repository_revision"]
        or original["declared_repository_license"] != expanded["declared_repository_license"]
        or len(original["files"]) != 10
        or len(expanded["platforms"]) != 65
    ):
        raise ValueError("incompatible original Libretro source revisions or licenses")
    imported_expansion = {**expanded, "files": expanded["platforms"]}
    original_scopes = [
        (entry, original, Path("archive/libretro-no-intro") / (entry["platform"] + ".dat"))
        for entry in original["files"]
    ]
    original_scopes += [
        (entry, imported_expansion, Path("archive/libretro-bulk") / entry["source_path"])
        for entry in expanded["platforms"]
    ]
    if len({entry["platform"] for entry, _, _ in original_scopes}) != EXPECTED["libretro_sources"]:
        raise ValueError("duplicate independent Libretro platform collection")
    return original_scopes


def inputs(root):
    register_paths = (
        Path("sources/mame-softlists-v1.json"),
        Path("sources/mame-softlists-v2.json"),
        Path(ORIGINAL_REPORTS[0]),
        Path(ORIGINAL_REPORTS[1]),
        LINKS_REPORT,
        LINKS_PATH,
        CONFLICTS,
        TITLE_REPORT,
        TITLE_CANDIDATES,
        Path("sources/libretro-no-intro.json"),
        Path("sources/bulk-expansion-v1.json"),
    ) + tuple(path for _, _, path in libretro_original_scopes(root))
    report = source_json(root, LINKS_REPORT)
    if (
        report["schema_version"] != 1
        or report["kind"] != "independent-cross-source-media-sha1-exact-match-review"
        or report["mame_software_lists"] != 65
        or report["libretro_source_platforms"] != 75
        or report["exact_sha1_source_candidate_pairs"] != EXPECTED["links"]
    ):
        raise ValueError("unsupported cross-source evidence release")
    digest, byte_count = source_digest(root, LINKS_PATH)
    conflict_digest, conflict_bytes = source_digest(root, CONFLICTS)
    if (
        digest != report["match_index_sha256"]
        or byte_count != report["match_index_bytes"]
        or conflict_digest != report["size_disagreement_sha256"]
        or conflict_bytes != report["size_disagreement_bytes"]
        or report["size_disagreement_rows"] != EXPECTED["conflicts"]
    ):
        raise ValueError("original exact-hash index no longer matches pinned report")
    counts = (31464, 1489)
    for relative, count in zip(ORIGINAL_REPORTS, counts):
        registered = source_json(root, Path(relative))
        if registered["source_observation_totals"]["software_entries"] != count:
            raise ValueError(f"unverified source-entry inventory: {relative}")
    return register_paths


def populate(conn, root):
    pinned_inputs = inputs(root)
    conn.executescript(SCHEMA)
    for path in pinned_inputs:
        digest, size = source_digest(root, path)
        conn.execute("INSERT INTO provenance VALUES (?,?,?)", (str(path), digest, size))
    total_software = 0
    total_media = 0
    for cohort in ("v1", "v2"):
        register = source_register(root, cohort)
        for filename in register["files"]:
            source = verify_one(root, register, filename)
            key = filename.removesuffix(".xml")
            observation_base = Path(f"data/mame/software-observations-{cohort}") / key
            observed_manifest = source_json(root, observation_base / "manifest.json")
            if (
                observed_manifest["original_xml_sha256"] != source["original_xml_sha256"]
                or observed_manifest["index_rows"] != source["source_software_entries"]
            ):
                raise ValueError(f"original MAME XML/index mismatch: {filename}")
            source_list = source["source_list_name"]
            original_xml_path = observed_manifest["original_xml_path"]
            conn.execute(
                "INSERT INTO source_lists VALUES (?,?,?,?,?,?,?,?)",
                (source_list, cohort, original_xml_path,
                 source["original_xml_sha256"],
                 str(observation_base / "observations.jsonl"),
                 observed_manifest["index_sha256"],
                 observed_manifest["index_rows"], "CC0-1.0"),
            )
            observed_count = 0
            for row in original_index_rows(root, filename, source, cohort):
                ordinal = row["original_software_ordinal"]
                media_list = row["original_media_claims"]
                conn.execute(
                    "INSERT INTO software VALUES (?,?,?,?,?,?,?)",
                    (source_list, ordinal,
                     row["original_software_attributes"]["name"],
                     row["original_title"],row["original_publisher_literal"],
                     row["original_year_literal"],compact(row)),
                )
                serials = [
                    info["value"] for info in row["original_info_attributes"]
                    if info.get("name") == "serial" and "value" in info
                ]
                for serial_ordinal, serial in enumerate(serials, 1):
                    conn.execute(
                        "INSERT INTO serial_claims VALUES (?,?,?,?)",
                        (source_list, ordinal, serial_ordinal, serial),
                    )
                for media in media_list:
                    original_attributes = media["original_media_attributes"]
                    conn.execute(
                        "INSERT INTO media_claims VALUES (?,?,?,?,?,?,?, ?,?)",
                        (source_list, ordinal, media["source_ordinal"],
                         media["kind"], original_attributes.get("name"),
                         optional_sha1(original_attributes.get("sha1")),
                         original_attributes.get("crc"),
                         numeric_size(original_attributes.get("size")), compact(media)),
                    )
                    total_media += 1
                total_software += 1
                observed_count += 1
            if observed_count != observed_manifest["index_rows"]:
                raise ValueError(f"missing source claims for {source_list}")
    libretro_records = 0
    libretro_media_count = 0
    for entry, original_register, relative in libretro_original_scopes(root):
        raw = source_bytes(root, relative)
        parsed = import_dat(raw, original_register, entry["platform"])
        if parsed["source_revision"] != original_register["repository_revision"]:
            raise ValueError(f"stale Libretro source scope: {entry['platform']}")
        if entry.get("bytes") is not None and entry["bytes"] != len(raw):
            raise ValueError(f"changed original DAT size: {relative}")
        platform = entry["platform"]
        conn.execute(
            "INSERT INTO libretro_sources VALUES (?,?,?,?,?,?)",
            (platform, str(relative), parsed["source_blob_sha"],
             hashlib.sha256(raw).hexdigest(), parsed["record_count"],
             parsed["source_license"]),
        )
        for row in parsed["records"]:
            ordinal = row["source_ordinal"]
            conn.execute(
                "INSERT INTO libretro_records VALUES (?,?,?,?,?,?)",
                (platform, ordinal, row["name"], row.get("region"),
                 row.get("serial"), compact(row)),
            )
            libretro_records += 1
            for media_ordinal, media in enumerate(row["roms"], 1):
                conn.execute(
                    "INSERT INTO libretro_media VALUES (?,?,?,?,?,?,?)",
                    (platform, ordinal, media_ordinal,
                     optional_sha1(media["sha1"]), media["size"],
                     media["name"], compact(media)),
                )
                libretro_media_count += 1
    if (
        libretro_records != EXPECTED["libretro_records"]
        or libretro_media_count != EXPECTED["libretro_media"]
    ):
        raise ValueError("Libretro source observation inventory drifted")

    for table, path, expected, expected_kind in (
        ("exact_media_links", LINKS_PATH, EXPECTED["links"],
         "exact-mame-libretro-media-sha1-source-candidate"),
        ("rejected_size_conflicts", CONFLICTS, EXPECTED["conflicts"],
         "unresolved-mame-libretro-same-sha1-size-conflict"),
    ):
        observed = 0
        for raw in source_bytes(root, path).splitlines():
            row = json.loads(raw)
            if row["schema_version"] != 1 or row["kind"] != expected_kind:
                raise ValueError(f"unapproved source correspondence in {path}")
            mame = row["mame"]
            if table == "exact_media_links":
                libretro = row["libretro"]
                if (
                    not row["size_corroborated"]
                    or mame["source_size_bytes"] != libretro["media_size_bytes"]
                    or not row["interpretation"].startswith("review-only")
                ):
                    raise ValueError("source link attempts an unsupported identity join")
                conn.execute(
                    "INSERT INTO exact_media_links VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (observed + 1, mame["source_list"], mame["software_ordinal"],
                     mame["source_media_ordinal"], libretro["platform"],
                     libretro["source_record_ordinal"],
                     libretro["source_media_ordinal"], row["media_sha1"],
                     mame["source_size_bytes"], compact(row)),
                )
            else:
                if not row["interpretation"].startswith("excluded-from-match-index"):
                    raise ValueError("unreviewed mismatch promoted into match index")
                conn.execute(
                    "INSERT INTO rejected_size_conflicts VALUES (?,?,?,?,?,?)",
                    (observed + 1, mame["source_list"],
                     mame["software_ordinal"], mame["source_media_ordinal"],
                     row["media_sha1"], compact(row)),
                )
            observed += 1
        if observed != expected:
            raise ValueError(f"incomplete {table} original source observations")

    title_report = source_json(root, TITLE_REPORT)
    title_original = source_bytes(root, TITLE_CANDIDATES)
    if (
        title_report["schema_version"] != 1
        or title_report["kind"] != "conservative-sha1-grounded-exact-title-review"
        or title_report["candidate_path"] != str(TITLE_CANDIDATES)
        or title_report["candidate_sha256"] != hashlib.sha256(title_original).hexdigest()
        or title_report["candidate_bytes"] != len(title_original)
        or title_report["total_review_only_exact_title_candidates"] != EXPECTED["title_review"]
        or title_report["minimum_distinct_mame_media_supported_scope_records"] != 3
    ):
        raise ValueError("unverified SHA1-grounded title review source report")
    from reconcile_mame_titles import normalized_title
    review_count = 0
    for raw in title_original.splitlines():
        row = json.loads(raw)
        mame = row["mame"]
        libretro = row["libretro"]
        key = row["normalized_title_key"]
        if (
            row["schema_version"] != 1
            or row["kind"] != "review-only-exact-source-title-correspondence"
            or row["source_scope_pair_sha1_supported_mame_records"] < 3
            or not row["interpretation"].startswith("review-only-")
            or normalized_title(mame["original_title"]) != key
            or normalized_title(libretro["original_title"]) != key
        ):
            raise ValueError("unsubstantiated original source title lead")
        mame_title = conn.execute(
            "SELECT title_literal FROM software WHERE source_list=? AND source_ordinal=?",
            (mame["source_list"], mame["software_ordinal"]),
        ).fetchone()
        libretro_title = conn.execute(
            "SELECT title_literal FROM libretro_records WHERE platform=? AND source_ordinal=?",
            (libretro["platform"], libretro["source_ordinal"]),
        ).fetchone()
        original_mame_source = conn.execute(
            "SELECT original_xml_sha256 FROM source_lists WHERE source_list=?",
            (mame["source_list"],),
        ).fetchone()
        original_libretro_source = conn.execute(
            "SELECT original_git_blob_sha FROM libretro_sources WHERE platform=?",
            (libretro["platform"],),
        ).fetchone()
        if (
            mame_title is None or mame_title[0] != mame["original_title"]
            or libretro_title is None or libretro_title[0] != libretro["original_title"]
            or original_mame_source is None
            or original_mame_source[0] != mame["original_source_xml_sha256"]
            or original_libretro_source is None
            or original_libretro_source[0] != libretro["original_git_blob_sha"]
        ):
            raise ValueError("title candidate points at a different original source record")
        conn.execute(
            "INSERT INTO title_review_candidates VALUES (?,?,?,?,?,?,?,?)",
            (review_count + 1, mame["source_list"], mame["software_ordinal"],
             libretro["platform"], libretro["source_ordinal"], key,
             row["source_scope_pair_sha1_supported_mame_records"], compact(row)),
        )
        review_count += 1
    if review_count != EXPECTED["title_review"]:
        raise ValueError("incomplete pinned title-review candidate inventory")

    if total_software != EXPECTED["software"]:
        raise ValueError(f"MAME source record count changed: {total_software}")
    conn.commit()
    return {"software": total_software, "media": total_media}


def counts(conn):
    result = {}
    for table in (
        "provenance", "source_lists", "software", "serial_claims",
        "media_claims", "libretro_sources", "libretro_records", "libretro_media",
        "exact_media_links", "rejected_size_conflicts",
        "title_review_candidates",
    ):
        result[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return result


def verify(conn, root):
    conn.execute("PRAGMA foreign_keys=ON")
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("derived local MAME index failed SQLite integrity check")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("derived local MAME index has broken source-ordinal references")
    observed = counts(conn)
    for table, expected in (
        ("provenance", 86),
        ("source_lists", EXPECTED["source_lists"]),
        ("software", EXPECTED["software"]),
        ("libretro_sources", EXPECTED["libretro_sources"]),
        ("libretro_records", EXPECTED["libretro_records"]),
        ("libretro_media", EXPECTED["libretro_media"]),
        ("exact_media_links", EXPECTED["links"]),
        ("rejected_size_conflicts", EXPECTED["conflicts"]),
        ("title_review_candidates", EXPECTED["title_review"]),
    ):
        if observed[table] != expected:
            raise ValueError(f"derived source index count mismatch: {table}")
    registered = {
        path: (digest, size) for path, digest, size in
        conn.execute("SELECT source_path,original_sha256,source_bytes FROM provenance")
    }
    if set(registered) != {str(path) for path in inputs(root)}:
        raise ValueError("unexpected original source inventory in derived database")
    for name, (digest, size) in registered.items():
        if (digest, size) != source_digest(root, Path(name)):
            raise ValueError(f"original source evidence changed: {name}")
    if conn.execute(
        """SELECT count(*) FROM exact_media_links a
           JOIN media_claims m ON
             a.mame_list=m.source_list
             AND a.mame_software_ordinal=m.source_ordinal
             AND a.mame_media_ordinal=m.media_ordinal
           JOIN libretro_media l ON
             a.libretro_platform=l.platform
             AND a.libretro_software_ordinal=l.source_ordinal
             AND a.libretro_media_ordinal=l.media_ordinal
           WHERE a.media_sha1 != m.sha1
              OR a.media_size_bytes != m.declared_size_bytes
              OR a.media_sha1 != l.sha1
              OR a.media_size_bytes != l.media_size_bytes"""
    ).fetchone()[0]:
        raise ValueError("SHA-1 or size claims differ from original media evidence")
    if conn.execute(
        """SELECT count(*) FROM title_review_candidates t
           JOIN exact_media_links l ON
             t.mame_list=l.mame_list
             AND t.mame_software_ordinal=l.mame_software_ordinal"""
    ).fetchone()[0]:
        raise ValueError("already-hash-corroborated source records entered title-only backlog")
    return observed


def build(root, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=".ludographium-mame-", suffix=".sqlite", dir=destination.parent
    )
    os.close(fd)
    try:
        with sqlite3.connect(temp_name) as conn:
            conn.execute("PRAGMA journal_mode=DELETE")
            populate(conn, root)
            verify(conn, root)
            conn.execute("VACUUM")
        os.replace(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def open_readonly(destination):
    uri = Path(destination).resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.create_function("unicode_casefold", 1, unicode_casefold, deterministic=True)
    conn.row_factory = sqlite3.Row
    return conn


def query(conn, *, source_list=None, title=None, publisher=None, year=None,
          serial=None, media_sha1=None, libretro_platform=None,
          linked_only=False, limit=20):
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    for value in (source_list, title, publisher, year, serial, libretro_platform):
        if value is not None and (not value.strip() or len(value) > 250):
            raise ValueError("search filters must be nonempty and reasonably bounded")
    if media_sha1 is not None and not re.fullmatch("[0-9a-fA-F]{40}", media_sha1):
        raise ValueError("invalid original media SHA-1")
    filters, values = [], []
    if source_list:
        filters.append("s.source_list=?")
        values.append(source_list)
    if title:
        filters.append("instr(unicode_casefold(s.title_literal),?)>0")
        values.append(unicode_casefold(title))
    if publisher:
        filters.append("instr(unicode_casefold(s.publisher_literal),?)>0")
        values.append(unicode_casefold(publisher))
    if year:
        filters.append("s.year_literal=?")
        values.append(year)
    if serial:
        filters.append(
            "EXISTS (SELECT 1 FROM serial_claims r WHERE "
            "r.source_list=s.source_list AND r.source_ordinal=s.source_ordinal "
            "AND r.serial_literal=?)"
        )
        values.append(serial)
    if media_sha1:
        filters.append(
            "EXISTS (SELECT 1 FROM media_claims m WHERE "
            "m.source_list=s.source_list AND m.source_ordinal=s.source_ordinal "
            "AND m.sha1=?)"
        )
        values.append(media_sha1.lower())
    if libretro_platform or linked_only:
        clause = (
            "EXISTS (SELECT 1 FROM exact_media_links c WHERE "
            "c.mame_list=s.source_list AND c.mame_software_ordinal=s.source_ordinal"
        )
        if libretro_platform:
            clause += " AND c.libretro_platform=?"
            values.append(libretro_platform)
        filters.append(clause + ")")
    sql_from = " FROM software s "
    if filters:
        sql_from += " WHERE " + " AND ".join(filters)
    total = conn.execute("SELECT count(*)" + sql_from, values).fetchone()[0]
    records = conn.execute(
        "SELECT s.source_list,s.source_ordinal,s.original_json" + sql_from
        + " ORDER BY s.source_list,s.source_ordinal LIMIT ?",
        (*values, limit),
    ).fetchall()
    hits = []
    for source_list, ordinal, original_json in records:
        links = conn.execute(
            "SELECT original_json FROM exact_media_links "
            "WHERE mame_list=? AND mame_software_ordinal=? "
            "ORDER BY source_ordinal LIMIT 51",
            (source_list, ordinal),
        ).fetchall()
        all_links = conn.execute(
            "SELECT count(*) FROM exact_media_links "
            "WHERE mame_list=? AND mame_software_ordinal=?",
            (source_list, ordinal),
        ).fetchone()[0]
        candidate_titles = conn.execute(
            "SELECT original_json FROM title_review_candidates WHERE "
            "mame_list=? AND mame_software_ordinal=? ORDER BY source_ordinal LIMIT 51",
            (source_list, ordinal),
        ).fetchall()
        title_count = conn.execute(
            "SELECT count(*) FROM title_review_candidates WHERE "
            "mame_list=? AND mame_software_ordinal=?",
            (source_list, ordinal),
        ).fetchone()[0]
        hits.append({
            "original_source_observation": json.loads(original_json),
            "exact_media_evidence_links": [
                json.loads(value[0]) for value in links[:50]
            ],
            "total_exact_media_evidence_links": all_links,
            "links_truncated": all_links > 50,
            "separate_unverified_title_review_leads": [
                json.loads(value[0]) for value in candidate_titles[:50]
            ],
            "total_unverified_title_review_leads": title_count,
            "title_review_leads_truncated": title_count > 50,
        })
    return {
        "source_mode": "local-derived-read-only-attributed-mame-source-index",
        "source_software_entries": EXPECTED["software"],
        "independent_mame_source_lists": EXPECTED["source_lists"],
        "total_filtered_source_observations": total,
        "returned_source_observations": len(hits),
        "records": hits,
        "interpretation": "original-source-observations-with-review-only-media-links-not-canonical-game-or-release-identities",
    }



def query_libretro(conn, *, platform=None, title=None, region=None,
                   serial=None, sha1=None, linked_only=False, limit=20):
    """Read original Libretro DAT statements, with separately attributable MAME links."""
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    for value in (platform, title, region, serial):
        if value is not None and (not value.strip() or len(value) > 250):
            raise ValueError("invalid Libretro source filter")
    if sha1 is not None and not re.fullmatch("[0-9a-fA-F]{40}", sha1):
        raise ValueError("invalid original Libretro media SHA-1")
    clauses, args = [], []
    if platform:
        clauses.append("r.platform=?")
        args.append(platform)
    if title:
        clauses.append("instr(unicode_casefold(r.title_literal),?)>0")
        args.append(unicode_casefold(title))
    if region:
        clauses.append("r.region_literal=?")
        args.append(region)
    if serial:
        clauses.append("r.serial_literal=?")
        args.append(serial)
    if sha1:
        clauses.append(
            "EXISTS (SELECT 1 FROM libretro_media m WHERE m.platform=r.platform "
            "AND m.source_ordinal=r.source_ordinal AND m.sha1=?)"
        )
        args.append(sha1.lower())
    if linked_only:
        clauses.append(
            "EXISTS (SELECT 1 FROM exact_media_links x WHERE "
            "x.libretro_platform=r.platform AND x.libretro_software_ordinal=r.source_ordinal)"
        )
    tail = " FROM libretro_records r"
    if clauses:
        tail += " WHERE " + " AND ".join(clauses)
    total = conn.execute("SELECT count(*)" + tail, args).fetchone()[0]
    rows = conn.execute(
        "SELECT r.platform,r.source_ordinal,r.original_json" + tail
        + " ORDER BY r.platform,r.source_ordinal LIMIT ?",
        (*args, limit),
    ).fetchall()
    hits = []
    for name, ordinal, raw in rows:
        refs = conn.execute(
            "SELECT original_json FROM exact_media_links "
            "WHERE libretro_platform=? AND libretro_software_ordinal=? "
            "ORDER BY source_ordinal LIMIT 51",
            (name, ordinal),
        ).fetchall()
        total_refs = conn.execute(
            "SELECT count(*) FROM exact_media_links WHERE "
            "libretro_platform=? AND libretro_software_ordinal=?",
            (name, ordinal),
        ).fetchone()[0]
        source = conn.execute(
            "SELECT original_dat_path,original_git_blob_sha,original_dat_sha256,"
            "source_license FROM libretro_sources WHERE platform=?", (name,)
        ).fetchone()
        title_refs = conn.execute(
            "SELECT original_json FROM title_review_candidates WHERE "
            "libretro_platform=? AND libretro_software_ordinal=? "
            "ORDER BY source_ordinal LIMIT 51",
            (name, ordinal),
        ).fetchall()
        title_ref_count = conn.execute(
            "SELECT count(*) FROM title_review_candidates WHERE "
            "libretro_platform=? AND libretro_software_ordinal=?",
            (name, ordinal),
        ).fetchone()[0]
        hits.append({
            "original_libretro_record": json.loads(raw),
            "source_platform": name,
            "original_source_path": source[0],
            "original_git_blob_sha": source[1],
            "original_dat_sha256": source[2],
            "source_license": source[3],
            "review_only_mame_media_links": [json.loads(ref[0]) for ref in refs[:50]],
            "total_review_only_mame_media_links": total_refs,
            "links_truncated": total_refs > 50,
            "separate_unverified_title_review_leads": [
                json.loads(value[0]) for value in title_refs[:50]
            ],
            "total_unverified_title_review_leads": title_ref_count,
            "title_review_leads_truncated": title_ref_count > 50,
        })
    return {
        "source_mode": "local-derived-read-only-attributed-libretro-original-dat",
        "independent_libretro_source_collections": EXPECTED["libretro_sources"],
        "original_libretro_source_records": EXPECTED["libretro_records"],
        "total_filtered_source_observations": total,
        "returned_source_observations": len(hits),
        "records": hits,
        "interpretation": "original-CC-BY-SA-source-records-with-optional-CC0-MAME-media-review-evidence-not-canonical-identity",
    }


def unsupported_mode_filters(args):
    """Return explicit unsupported filters, never silently ignore user constraints."""
    if args.query:
        fields = ("platform", "region")
    elif args.query_libretro:
        fields = ("list", "publisher", "year", "libretro_platform")
    else:
        fields = (
            "list", "title", "publisher", "year", "serial", "sha1",
            "libretro_platform", "platform", "region", "linked_only",
        )
    return [
        field for field in fields if getattr(args, field, None) not in (None, False)
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--query", action="store_true")
    mode.add_argument("--query-libretro", action="store_true")
    parser.add_argument("--list")
    parser.add_argument("--title")
    parser.add_argument("--publisher")
    parser.add_argument("--year")
    parser.add_argument("--serial")
    parser.add_argument("--sha1")
    parser.add_argument("--libretro-platform")
    parser.add_argument("--platform")
    parser.add_argument("--region")
    parser.add_argument("--linked-only", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    unsupported = unsupported_mode_filters(args)
    if unsupported:
        parser.error(
            "unsupported filters for selected source mode: " + ", ".join(unsupported)
        )
    if args.build:
        build(ROOT, args.db)
        with open_readonly(args.db) as db:
            result = verify(db, ROOT)
    else:
        if not args.db.is_file() or args.db.is_symlink():
            parser.error("missing or linked disposable SQLite index; run --build")
        with open_readonly(args.db) as db:
            if args.verify:
                result = verify(db, ROOT)
            elif args.summary:
                verify(db, ROOT)
                result = counts(db)
            elif args.query_libretro:
                verify(db, ROOT)
                result = query_libretro(
                    db, platform=args.platform, title=args.title,
                    region=args.region, serial=args.serial, sha1=args.sha1,
                    linked_only=args.linked_only, limit=args.limit,
                )
            else:
                verify(db, ROOT)
                result = query(
                    db, source_list=args.list, title=args.title,
                    publisher=args.publisher, year=args.year, serial=args.serial,
                    media_sha1=args.sha1, libretro_platform=args.libretro_platform,
                    linked_only=args.linked_only, limit=args.limit,
                )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
