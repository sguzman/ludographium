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
from query_source_review_units import (
    validate as validated_source_review_units,
    validate_v3 as validated_v3_source_review_units,
)

ORIGINAL_REPORTS = (
    "reports/mame-software-observations-v1-summary.json",
    "reports/mame-software-observations-v2-summary.json",
    "reports/mame-software-observations-v3-summary.json",
)
CONFLICTS = Path("data/reconciliation/mame-libretro-sha1-v1/size-disagreements.jsonl")
TITLE_REPORT = Path("reports/mame-libretro-title-review-v1-summary.json")
TITLE_CANDIDATES = Path("data/reconciliation/mame-libretro-title-review-v1/candidates.jsonl")
REVIEW_INDEX = Path("data/reconciliation/source-review-units-v1/units.jsonl")
REVIEW_REPORT = Path("reports/source-review-units-v1-summary.json")
V3_MEDIA_REPORT = Path("reports/mame-libretro-sha1-v3-summary.json")
V3_MEDIA_INDEX = Path("data/reconciliation/mame-libretro-sha1-v3/links.jsonl")
V3_CONFLICTS = Path("data/reconciliation/mame-libretro-sha1-v3/size-disagreements.jsonl")
V3_TITLE_REPORT = Path("reports/mame-libretro-title-review-v3-summary.json")
V3_TITLE_INDEX = Path("data/reconciliation/mame-libretro-title-review-v3/candidates.jsonl")
V3_REVIEW_REPORT = Path("reports/source-review-units-v3-summary.json")
V3_REVIEW_INDEX = Path("data/reconciliation/source-review-units-v3/units.jsonl")
BASELINE = {
    "source_lists": 65,
    "software": 32953,
    "libretro_sources": 75,
    "libretro_records": 117145,
    "libretro_media": 117145,
    "links": 19025,
    "conflicts": 1,
    "title_review": 6825,
    "review_units": 21712,
}
EXPECTED = {
    **BASELINE,
    "source_lists": 69,
    "software": 33119,
    "links": 19152,
    "title_review": 6833,
    "review_units": 21845,
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
    cohort TEXT NOT NULL CHECK (cohort IN ('v1','v2','v3')),
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
CREATE TABLE source_review_units (
    review_id TEXT PRIMARY KEY,
    mame_list TEXT NOT NULL,
    mame_software_ordinal INTEGER NOT NULL,
    priority_class TEXT NOT NULL,
    ambiguous INTEGER NOT NULL CHECK(ambiguous IN (0,1)),
    evidence_kind TEXT NOT NULL CHECK(evidence_kind IN ('media','title')),
    original_json TEXT NOT NULL,
    UNIQUE(mame_list,mame_software_ordinal),
    FOREIGN KEY(mame_list,mame_software_ordinal)
      REFERENCES software(source_list,source_ordinal)
);
CREATE TABLE source_review_targets (
    review_id TEXT NOT NULL REFERENCES source_review_units(review_id),
    libretro_platform TEXT NOT NULL,
    libretro_software_ordinal INTEGER NOT NULL,
    media_supported INTEGER NOT NULL CHECK(media_supported IN (0,1)),
    exact_title_supported INTEGER NOT NULL CHECK(exact_title_supported IN (0,1)),
    original_json TEXT NOT NULL,
    PRIMARY KEY(review_id,libretro_platform,libretro_software_ordinal),
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
CREATE INDEX idx_source_review_scope ON source_review_units(mame_list,priority_class);
CREATE INDEX idx_source_review_class ON source_review_units(evidence_kind,ambiguous);
CREATE INDEX idx_source_review_libretro ON source_review_targets(libretro_platform,libretro_software_ordinal);
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
        Path("sources/mame-softlists-v3.json"),
        *(Path(p) for p in ORIGINAL_REPORTS),
        LINKS_REPORT,
        LINKS_PATH,
        CONFLICTS,
        TITLE_REPORT,
        TITLE_CANDIDATES,
        REVIEW_REPORT,
        REVIEW_INDEX,
        V3_MEDIA_REPORT,
        V3_MEDIA_INDEX,
        V3_CONFLICTS,
        V3_TITLE_REPORT,
        V3_TITLE_INDEX,
        V3_REVIEW_REPORT,
        V3_REVIEW_INDEX,
        Path("sources/libretro-no-intro.json"),
        Path("sources/bulk-expansion-v1.json"),
    ) + tuple(path for _, _, path in libretro_original_scopes(root))
    report = source_json(root, LINKS_REPORT)
    if (
        report["schema_version"] != 1
        or report["kind"] != "independent-cross-source-media-sha1-exact-match-review"
        or report["mame_software_lists"] != 65
        or report["libretro_source_platforms"] != 75
        or report["exact_sha1_source_candidate_pairs"] != BASELINE["links"]
    ):
        raise ValueError("unsupported cross-source evidence release")
    digest, byte_count = source_digest(root, LINKS_PATH)
    conflict_digest, conflict_bytes = source_digest(root, CONFLICTS)
    if (
        digest != report["match_index_sha256"]
        or byte_count != report["match_index_bytes"]
        or conflict_digest != report["size_disagreement_sha256"]
        or conflict_bytes != report["size_disagreement_bytes"]
        or report["size_disagreement_rows"] != BASELINE["conflicts"]
    ):
        raise ValueError("original exact-hash index no longer matches pinned report")
    counts = (31464, 1489, 166)
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
    for cohort in ("v1", "v2", "v3"):
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
        ("exact_media_links", LINKS_PATH, BASELINE["links"],
         "exact-mame-libretro-media-sha1-source-candidate"),
        ("rejected_size_conflicts", CONFLICTS, BASELINE["conflicts"],
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
        or title_report["total_review_only_exact_title_candidates"] != BASELINE["title_review"]
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
    if review_count != BASELINE["title_review"]:
        raise ValueError("incomplete pinned title-review candidate inventory")

    review_manifest, original_units, _ = validated_source_review_units(root)
    if (
        review_manifest["source_review_units"] != BASELINE["review_units"]
        or review_manifest["source_media_index_sha256"] !=
            source_json(root, LINKS_REPORT)["match_index_sha256"]
        or review_manifest["source_title_index_sha256"] !=
            title_report["candidate_sha256"]
    ):
        raise ValueError("stale or incomplete stable-ID original source review queue")
    targets_inserted = 0
    for unit in original_units:
        mame = unit["mame"]
        source_list = mame["source_list"]
        ordinal = mame["original_software_ordinal"]
        original = conn.execute(
            "SELECT s.title_literal,l.original_xml_sha256 FROM software s "
            "JOIN source_lists l ON s.source_list=l.source_list "
            "WHERE s.source_list=? AND s.source_ordinal=?",
            (source_list, ordinal),
        ).fetchone()
        if (
            original is None
            or original[0] != mame["original_title"]
            or original[1] != mame["original_xml_sha256"]
        ):
            raise ValueError("source review unit refers to another original MAME record")
        media_ordinals = unit["media_evidence_jsonl_source_ordinals"]
        title_ordinals = unit["title_evidence_jsonl_source_ordinals"]
        evidence_kind = "media" if media_ordinals else "title"
        conn.execute(
            "INSERT INTO source_review_units VALUES (?,?,?,?,?,?,?)",
            (unit["stable_review_id"], source_list, ordinal,
             unit["source_review_priority_class"],
             int(unit["multiple_source_target_alternatives"]),
             evidence_kind, compact(unit)),
        )
        actual_targets = set()
        for target in unit["candidate_libretro_targets"]:
            platform = target["platform"]
            target_ordinal = target["original_source_ordinal"]
            matched = conn.execute(
                "SELECT r.title_literal,s.original_git_blob_sha FROM libretro_records r "
                "JOIN libretro_sources s ON r.platform=s.platform "
                "WHERE r.platform=? AND r.source_ordinal=?",
                (platform, target_ordinal),
            ).fetchone()
            if (
                matched is None or matched[0] != target["original_title"]
                or matched[1] != target["original_git_blob_sha"]
            ):
                raise ValueError("source review unit target does not match original DAT")
            conn.execute(
                "INSERT INTO source_review_targets VALUES (?,?,?,?,?,?)",
                (unit["stable_review_id"], platform, target_ordinal,
                 int(target["has_equal_sha1_and_size_evidence"]),
                 int(target["has_exact_normalized_title_review_evidence"]),
                 compact(target)),
            )
            actual_targets.add((platform, target_ordinal))
            targets_inserted += 1
        for table, row_ordinals in (
            ("exact_media_links", media_ordinals),
            ("title_review_candidates", title_ordinals),
        ):
            for evidence_ordinal in row_ordinals:
                source_link = conn.execute(
                    f"SELECT mame_list,mame_software_ordinal,"
                    f"libretro_platform,libretro_software_ordinal "
                    f"FROM {table} WHERE source_ordinal=?",
                    (evidence_ordinal,),
                ).fetchone()
                if (
                    source_link is None
                    or (source_link[0],source_link[1]) != (source_list,ordinal)
                    or (source_link[2],source_link[3]) not in actual_targets
                ):
                    raise ValueError("review unit references unrelated evidence row")
    if targets_inserted < BASELINE["review_units"]:
        raise ValueError("source-review target inventory is truncated")

    # Appended v3 records retain their own XML snapshot, source ordinal,
    # raw JSON and evidence namespace. Historical baseline evidence is unchanged.
    append_v3_evidence(conn, root)
    if total_software != EXPECTED["software"]:
        raise ValueError(f"MAME source record count changed: {total_software}")
    conn.commit()
    return {"software": total_software, "media": total_media}


def append_v3_evidence(conn, root):
    """Index separate third-cohort claims without changing baseline coordinates."""
    media_report = source_json(root, V3_MEDIA_REPORT)
    title_report = source_json(root, V3_TITLE_REPORT)
    report, units, _ = validated_v3_source_review_units(root)
    media_raw = source_bytes(root, V3_MEDIA_INDEX)
    title_raw = source_bytes(root, V3_TITLE_INDEX)
    rejected_raw = source_bytes(root, V3_CONFLICTS)
    if (
        media_report["schema_version"] != 1
        or media_report["kind"] != "separate-third-cohort-exact-original-media-source-candidates"
        or media_report["mame_original_source_lists"] != 4
        or media_report["source_media_sha1_candidate_pairs"] != 127
        or media_report["candidate_path"] != str(V3_MEDIA_INDEX)
        or media_report["candidate_sha256"] != hashlib.sha256(media_raw).hexdigest()
        or media_report["candidate_bytes"] != len(media_raw)
        or media_report["rejected_size_conflicts_path"] != str(V3_CONFLICTS)
        or media_report["rejected_size_conflicts_sha256"] != hashlib.sha256(rejected_raw).hexdigest()
        or media_report["rejected_size_conflicts_bytes"] != len(rejected_raw)
        or rejected_raw
        or title_report["schema_version"] != 1
        or title_report["kind"] != "additive-third-mame-cohort-title-review"
        or title_report["original_title_review_candidate_pairs"] != 8
        or title_report["candidate_path"] != str(V3_TITLE_INDEX)
        or title_report["candidate_sha256"] != hashlib.sha256(title_raw).hexdigest()
        or title_report["candidate_bytes"] != len(title_raw)
        or report["original_media_candidate_pairs"] != 127
        or report["original_title_candidate_pairs"] != 8
        or report["additional_original_review_units"] != 133
        or len(units) != 133
    ):
        raise ValueError("unverified third-cohort source evidence accession")

    media_pairs = [json.loads(raw) for raw in media_raw.splitlines()]
    title_pairs = [json.loads(raw) for raw in title_raw.splitlines()]
    if len(media_pairs) != 127 or len(title_pairs) != 8:
        raise ValueError("truncated third-cohort original evidence inventory")

    for ordinal, row in enumerate(media_pairs, 1):
        mame, libretro = row["mame"], row["libretro"]
        digest = optional_sha1(row["original_media_sha1"])
        mame_claim = conn.execute(
            "SELECT m.sha1,m.declared_size_bytes,m.media_kind,s.title_literal,"
            "l.original_xml_sha256,l.cohort FROM media_claims m "
            "JOIN software s ON s.source_list=m.source_list "
            "AND s.source_ordinal=m.source_ordinal "
            "JOIN source_lists l ON l.source_list=m.source_list "
            "WHERE m.source_list=? AND m.source_ordinal=? AND m.media_ordinal=?",
            (mame["source_list"], mame["software_ordinal"], mame["source_media_ordinal"]),
        ).fetchone()
        libretro_claim = conn.execute(
            "SELECT m.sha1,m.media_size_bytes,r.title_literal,l.original_git_blob_sha "
            "FROM libretro_media m JOIN libretro_records r ON "
            "r.platform=m.platform AND r.source_ordinal=m.source_ordinal "
            "JOIN libretro_sources l ON l.platform=m.platform "
            "WHERE m.platform=? AND m.source_ordinal=? AND m.media_ordinal=?",
            (libretro["platform"], libretro["source_record_ordinal"],
             libretro["source_media_ordinal"]),
        ).fetchone()
        size = mame["original_declared_size_bytes"]
        if (
            row["schema_version"] != 1
            or row["kind"] != "review-only-v3-mame-libretro-exact-media-sha1-candidate"
            or not row["size_corroborated"]
            or mame_claim != (
                digest, size, mame["source_media_kind"], mame["original_title"],
                mame["source_xml_sha256"], "v3"
            )
            or libretro_claim != (
                digest, size, libretro["original_title"], libretro["source_dat_blob_sha"]
            )
            or size != libretro["original_media_size_bytes"]
            or row["interpretation"] != (
                "review-only-source-sha1-candidate-not-accepted-game-or-release-identity"
            )
        ):
            raise ValueError(f"third-cohort media evidence does not match original sources: {ordinal}")
        conn.execute(
            "INSERT INTO exact_media_links VALUES (?,?,?,?,?,?,?,?,?,?)",
            (BASELINE["links"] + ordinal, mame["source_list"], mame["software_ordinal"],
             mame["source_media_ordinal"], libretro["platform"],
             libretro["source_record_ordinal"], libretro["source_media_ordinal"],
             digest, size, compact(row)),
        )

    from reconcile_mame_titles import normalized_title
    for ordinal, row in enumerate(title_pairs, 1):
        mame, libretro = row["mame"], row["libretro"]
        original_mame = conn.execute(
            "SELECT s.title_literal,l.original_xml_sha256,l.cohort FROM software s "
            "JOIN source_lists l ON l.source_list=s.source_list "
            "WHERE s.source_list=? AND s.source_ordinal=?",
            (mame["source_list"], mame["original_software_ordinal"]),
        ).fetchone()
        original_libretro = conn.execute(
            "SELECT r.title_literal,l.original_git_blob_sha FROM libretro_records r "
            "JOIN libretro_sources l ON r.platform=l.platform "
            "WHERE r.platform=? AND r.source_ordinal=?",
            (libretro["platform"], libretro["original_source_ordinal"]),
        ).fetchone()
        key = row["normalized_title_key"]
        if (
            row["schema_version"] != 1
            or row["kind"] != "third-mame-cohort-review-only-exact-title-evidence"
            or original_mame != (mame["original_title"], mame["source_xml_sha256"], "v3")
            or original_libretro != (
                libretro["original_title"], libretro["original_git_blob_sha"]
            )
            or normalized_title(mame["original_title"]) != key
            or normalized_title(libretro["original_title"]) != key
            or row["scope_pair_distinct_mame_sha1_supported_records"] < 3
            or row["interpretation"] != (
                "review-only-name-equality-in-media-supported-source-scope-"
                "not-a-verified-game-or-release-identity"
            )
        ):
            raise ValueError(f"third-cohort title evidence does not match original sources: {ordinal}")
        conn.execute(
            "INSERT INTO title_review_candidates VALUES (?,?,?,?,?,?,?,?)",
            (BASELINE["title_review"] + ordinal, mame["source_list"],
             mame["original_software_ordinal"], libretro["platform"],
             libretro["original_source_ordinal"], key,
             row["scope_pair_distinct_mame_sha1_supported_records"], compact(row)),
        )

    for unit in units:
        mame = unit["mame"]
        name, ordinal = mame["source_list"], mame["original_software_ordinal"]
        original = conn.execute(
            "SELECT s.title_literal,l.original_xml_sha256,l.cohort FROM software s "
            "JOIN source_lists l ON l.source_list=s.source_list "
            "WHERE s.source_list=? AND s.source_ordinal=?",
            (name, ordinal),
        ).fetchone()
        if original != (mame["original_title"], mame["original_xml_sha256"], "v3"):
            raise ValueError("third-cohort stable review task has changed MAME source")
        media_ordinals = unit["media_evidence_jsonl_source_ordinals"]
        title_ordinals = unit["title_evidence_jsonl_source_ordinals"]
        evidence_kind = "media" if media_ordinals else "title"
        conn.execute(
            "INSERT INTO source_review_units VALUES (?,?,?,?,?,?,?)",
            (unit["stable_review_id"], name, ordinal,
             unit["source_review_priority_class"],
             int(unit["multiple_source_target_alternatives"]),
             evidence_kind, compact(unit)),
        )
        targets = set()
        for target in unit["candidate_libretro_targets"]:
            platform, target_ordinal = target["platform"], target["original_source_ordinal"]
            source = conn.execute(
                "SELECT r.title_literal,l.original_git_blob_sha FROM libretro_records r "
                "JOIN libretro_sources l ON r.platform=l.platform "
                "WHERE r.platform=? AND r.source_ordinal=?",
                (platform, target_ordinal),
            ).fetchone()
            if source != (target["original_title"], target["original_git_blob_sha"]):
                raise ValueError("third-cohort review target has changed original DAT")
            conn.execute(
                "INSERT INTO source_review_targets VALUES (?,?,?,?,?,?)",
                (unit["stable_review_id"], platform, target_ordinal,
                 int(target["has_equal_sha1_and_size_evidence"]),
                 int(target["has_exact_normalized_title_review_evidence"]),
                 compact(target)),
            )
            targets.add((platform, target_ordinal))
        for table, ordinals, baseline in (
            ("exact_media_links", media_ordinals, BASELINE["links"]),
            ("title_review_candidates", title_ordinals, BASELINE["title_review"]),
        ):
            for evidence_ordinal in ordinals:
                link = conn.execute(
                    f"SELECT mame_list,mame_software_ordinal,"
                    f"libretro_platform,libretro_software_ordinal "
                    f"FROM {table} WHERE source_ordinal=?",
                    (baseline + evidence_ordinal,),
                ).fetchone()
                if (
                    link is None
                    or link[:2] != (name, ordinal)
                    or link[2:] not in targets
                ):
                    raise ValueError("third-cohort review ID references unrelated evidence")


def counts(conn):
    result = {}
    for table in (
        "provenance", "source_lists", "software", "serial_claims",
        "media_claims", "libretro_sources", "libretro_records", "libretro_media",
        "exact_media_links", "rejected_size_conflicts",
        "title_review_candidates", "source_review_units",
        "source_review_targets",
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
        ("provenance", 97),
        ("source_lists", EXPECTED["source_lists"]),
        ("software", EXPECTED["software"]),
        ("libretro_sources", EXPECTED["libretro_sources"]),
        ("libretro_records", EXPECTED["libretro_records"]),
        ("libretro_media", EXPECTED["libretro_media"]),
        ("exact_media_links", EXPECTED["links"]),
        ("rejected_size_conflicts", EXPECTED["conflicts"]),
        ("title_review_candidates", EXPECTED["title_review"]),
        ("source_review_units", EXPECTED["review_units"]),
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
    if observed["source_review_targets"] < observed["source_review_units"]:
        raise ValueError("truncated indexed Libretro source-review alternatives")
    if conn.execute(
        """SELECT count(*) FROM source_review_units r
           JOIN software s ON r.mame_list=s.source_list
             AND r.mame_software_ordinal=s.source_ordinal
           WHERE json_extract(r.original_json,'$.mame.original_title') != s.title_literal
             OR r.review_id != json_extract(r.original_json,'$.stable_review_id')"""
    ).fetchone()[0]:
        raise ValueError("source review task differs from original MAME record")
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
          linked_only=False, without_review_leads=False, limit=20,
          offset=0):
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("MAME query offset must be 0..1000000")
    if without_review_leads and (linked_only or libretro_platform is not None):
        raise ValueError("unlinked source filter conflicts with required media matches")
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
    if without_review_leads:
        filters.append(
            "NOT EXISTS (SELECT 1 FROM source_review_units r WHERE "
            "r.mame_list=s.source_list AND r.mame_software_ordinal=s.source_ordinal)"
        )
    sql_from = " FROM software s "
    if filters:
        sql_from += " WHERE " + " AND ".join(filters)
    total = conn.execute("SELECT count(*)" + sql_from, values).fetchone()[0]
    records = conn.execute(
        "SELECT s.source_list,s.source_ordinal,s.original_json" + sql_from
        + " ORDER BY s.source_list,s.source_ordinal LIMIT ? OFFSET ?",
        (*values, limit, offset),
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
        "offset": offset,
        "next_offset": offset + len(hits) if offset + len(hits) < total else None,
        "without_any_cross_provider_review_lead": without_review_leads,
        "records": hits,
        "interpretation": (
            "original-source-records-without-current-cross-provider-review-evidence-not-canonical-game-identities"
            if without_review_leads else
            "original-source-observations-with-review-only-media-links-not-canonical-game-or-release-identities"
        ),
    }



def query_libretro(conn, *, platform=None, title=None, region=None,
                   serial=None, sha1=None, linked_only=False,
                   without_review_leads=False, limit=20, offset=0):
    """Read original Libretro DAT statements, with separately attributable MAME links."""
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("Libretro query offset must be 0..1000000")
    if without_review_leads and linked_only:
        raise ValueError("unlinked Libretro source filter conflicts with linked-only")
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
    if without_review_leads:
        clauses.append(
            "NOT EXISTS (SELECT 1 FROM source_review_targets t WHERE "
            "t.libretro_platform=r.platform "
            "AND t.libretro_software_ordinal=r.source_ordinal)"
        )
    tail = " FROM libretro_records r"
    if clauses:
        tail += " WHERE " + " AND ".join(clauses)
    total = conn.execute("SELECT count(*)" + tail, args).fetchone()[0]
    rows = conn.execute(
        "SELECT r.platform,r.source_ordinal,r.original_json" + tail
        + " ORDER BY r.platform,r.source_ordinal LIMIT ? OFFSET ?",
        (*args, limit, offset),
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
        "without_any_cross_provider_review_lead": without_review_leads,
        "total_filtered_source_observations": total,
        "returned_source_observations": len(hits),
        "offset": offset,
        "next_offset": offset + len(hits) if offset + len(hits) < total else None,
        "records": hits,
        "interpretation": (
            "original-Libretro-records-without-current-MAME-source-review-evidence-not-canonical-identity"
            if without_review_leads else
            "original-CC-BY-SA-source-records-with-optional-CC0-MAME-media-review-evidence-not-canonical-identity"
        ),
    }



def query_review(conn, *, review_id=None, source_list=None, platform=None,
                 title=None, priority_class=None, ambiguous_only=False,
                 evidence_type=None, limit=20, offset=0):
    """Search review tasks using stable IDs, never accepted game identities."""
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("review query offset must be 0..1000000")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("source-review query limit must be 1..200")
    if review_id is not None and not re.fullmatch(r"lgreview:v1:[0-9a-f]{64}", review_id):
        raise ValueError("review ID must be a valid pinned source identifier")
    for value in (source_list, platform, title):
        if value is not None and (not isinstance(value, str)
                                  or not value.strip() or len(value) > 250):
            raise ValueError("invalid bounded source-review filter")
    if priority_class is not None and priority_class not in (
        "multiple-exact-title-source-targets",
        "multiple-media-supported-source-targets",
        "single-exact-title-source-target",
        "single-media-supported-source-target",
    ):
        raise ValueError("unknown source-review classification")
    if evidence_type not in (None, "media", "title"):
        raise ValueError("unknown original evidence type")
    clauses, args = [], []
    if review_id:
        clauses.append("r.review_id=?")
        args.append(review_id)
    if source_list:
        clauses.append("r.mame_list=?")
        args.append(source_list)
    if platform:
        clauses.append(
            "EXISTS (SELECT 1 FROM source_review_targets t "
            "WHERE t.review_id=r.review_id AND t.libretro_platform=?)"
        )
        args.append(platform)
    if title:
        clauses.append(
            "(instr(unicode_casefold(s.title_literal),?)>0 OR "
            "EXISTS (SELECT 1 FROM source_review_targets t "
            "JOIN libretro_records l ON l.platform=t.libretro_platform "
            "AND l.source_ordinal=t.libretro_software_ordinal "
            "WHERE t.review_id=r.review_id "
            "AND instr(unicode_casefold(l.title_literal),?)>0))"
        )
        args.extend((unicode_casefold(title), unicode_casefold(title)))
    if priority_class:
        clauses.append("r.priority_class=?")
        args.append(priority_class)
    if ambiguous_only:
        clauses.append("r.ambiguous=1")
    if evidence_type:
        clauses.append("r.evidence_kind=?")
        args.append(evidence_type)
    tail = (
        " FROM source_review_units r JOIN software s ON "
        "r.mame_list=s.source_list AND r.mame_software_ordinal=s.source_ordinal"
    )
    if clauses:
        tail += " WHERE " + " AND ".join(clauses)
    total = conn.execute("SELECT count(*)" + tail, args).fetchone()[0]
    rows = conn.execute(
        "SELECT r.review_id,r.original_json" + tail
        + " ORDER BY r.mame_list,r.mame_software_ordinal LIMIT ? OFFSET ?",
        (*args, limit, offset),
    ).fetchall()
    returned = []
    for stable_id, original_json in rows:
        alternatives = conn.execute(
            "SELECT original_json FROM source_review_targets "
            "WHERE review_id=? ORDER BY libretro_platform,libretro_software_ordinal",
            (stable_id,),
        ).fetchall()
        unit = json.loads(original_json)
        targets = [json.loads(x[0]) for x in alternatives]
        if targets != unit["candidate_libretro_targets"]:
            raise ValueError("derived review targets differ from pinned evidence")
        returned.append(unit)
    return {
        "source_mode": "disposable-local-stable-source-review-task-index",
        "total_pinned_source_review_units": EXPECTED["review_units"],
        "total_filtered_review_units": total,
        "returned_review_units": len(returned),
        "offset": offset,
        "next_offset": offset + len(returned) if offset + len(returned) < total else None,
        "units": returned,
        "interpretation": (
            "Stable IDs denote pinned source review tasks; no canonical "
            "game, work, edition, release or source identity is accepted."
        ),
    }



def query_both_sources(conn, *, title=None, sha1=None, limit=20, offset=0):
    """Run independent original-source searches without joining work identities."""
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("cross-provider query offset must be 0..1000000")
    if title is None and sha1 is None:
        raise ValueError("cross-provider lookup requires --title or --sha1")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("source query limit must be 1..200")
    if title is not None and (not isinstance(title, str)
                              or not title.strip() or len(title) > 250):
        raise ValueError("invalid cross-provider original title search")
    if sha1 is not None and not re.fullmatch("[0-9a-fA-F]{40}", sha1):
        raise ValueError("cross-provider source SHA-1 requires 40 hex digits")
    mame = query(conn, title=title, media_sha1=sha1, limit=limit, offset=offset)
    libretro = query_libretro(conn, title=title, sha1=sha1, limit=limit,
                             offset=offset)
    return {
        "source_mode": "separate-original-MAME-and-Libretro-provider-lookups",
        "matching_policy": "no-cross-source-work-or-release-identity-merge",
        "offset_per_provider": offset,
        "mame": mame,
        "libretro": libretro,
        "returned_source_observations": (
            mame["returned_source_observations"]
            + libretro["returned_source_observations"]
        ),
        "interpretation": (
            "MAME CC0 and Libretro CC-BY-SA-4.0 observations are independent. "
            "These are source searches, not canonical game, edition, release "
            "or platform records. Equal media SHA-1 and names remain review-only."
        ),
    }


def unsupported_mode_filters(args):
    """Return explicit unsupported filters, never silently ignore user constraints."""
    if args.query:
        fields = ("platform", "region", "review_id", "priority_class",
                  "ambiguous_only", "evidence_type")
    elif args.query_libretro:
        fields = ("list", "publisher", "year", "libretro_platform",
                  "review_id", "priority_class", "ambiguous_only", "evidence_type")
    elif getattr(args, "query_review", False):
        fields = ("publisher", "year", "serial", "sha1",
                  "libretro_platform", "region", "linked_only",
                  "without_review_leads")
    elif getattr(args, "query_all", False):
        fields = (
            "list", "publisher", "year", "serial", "libretro_platform",
            "platform", "region", "linked_only", "without_review_leads",
            "review_id", "priority_class", "ambiguous_only", "evidence_type",
        )
    else:
        fields = (
            "list", "title", "publisher", "year", "serial", "sha1",
            "libretro_platform", "platform", "region", "linked_only",
            "review_id", "priority_class", "ambiguous_only", "evidence_type",
            "without_review_leads",
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
    mode.add_argument("--query-review", action="store_true")
    mode.add_argument("--query-all", action="store_true")
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
    parser.add_argument("--without-review-leads", action="store_true")
    parser.add_argument("--review-id")
    parser.add_argument("--priority-class")
    parser.add_argument("--ambiguous-only", action="store_true")
    parser.add_argument("--evidence-type", choices=["media", "title"])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0,
                        help="matching rows to skip separately for each provider")
    args = parser.parse_args()
    unsupported = unsupported_mode_filters(args)
    if unsupported:
        parser.error(
            "unsupported filters for selected source mode: " + ", ".join(unsupported)
        )
    if (args.build or args.verify or args.summary) and args.offset:
        parser.error("--offset is only supported for source query modes")
    if args.query_all and args.title is None and args.sha1 is None:
        parser.error("--query-all requires --title or --sha1")
    if args.without_review_leads and (
        (args.query_libretro and args.linked_only)
        or (args.query and (args.linked_only or args.libretro_platform is not None))
    ):
        parser.error("--without-review-leads conflicts with required source matches")
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
            elif args.query_review:
                verify(db, ROOT)
                result = query_review(
                    db, review_id=args.review_id, source_list=args.list,
                    platform=args.platform, title=args.title,
                    priority_class=args.priority_class,
                    ambiguous_only=args.ambiguous_only,
                    evidence_type=args.evidence_type, limit=args.limit,
                    offset=args.offset,
                )
            elif args.query_all:
                verify(db, ROOT)
                result = query_both_sources(
                    db, title=args.title, sha1=args.sha1, limit=args.limit,
                    offset=args.offset,
                )
            elif args.query_libretro:
                verify(db, ROOT)
                result = query_libretro(
                    db, platform=args.platform, title=args.title,
                    region=args.region, serial=args.serial, sha1=args.sha1,
                    linked_only=args.linked_only,
                    without_review_leads=args.without_review_leads,
                    limit=args.limit, offset=args.offset,
                )
            else:
                verify(db, ROOT)
                result = query(
                    db, source_list=args.list, title=args.title,
                    publisher=args.publisher, year=args.year, serial=args.serial,
                    media_sha1=args.sha1, libretro_platform=args.libretro_platform,
                    linked_only=args.linked_only,
                    without_review_leads=args.without_review_leads,
                    limit=args.limit, offset=args.offset,
                )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
