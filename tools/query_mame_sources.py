#!/usr/bin/env python3
"""Read-only source search over three independently pinned MAME CC0 cohorts."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from acquire_mame_softlists import ROOT, source_register, verify_one

INDEX_BASE = Path("data/mame/software-observations-v1")
INDEX_BASE_V2 = Path("data/mame/software-observations-v2")
INDEX_BASE_V3 = Path("data/mame/software-observations-v3")
INDEX_BASE_V4 = Path("data/mame/software-observations-v4")
REPORT = Path("reports/mame-software-observations-v1-summary.json")


def read_json(path):
    if path.is_symlink():
        raise ValueError(f"symlink in original MAME source index: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def original_index_rows(root, filename, original, cohort="v1"):
    stem = filename.removesuffix(".xml")
    base = {
        "v1": INDEX_BASE, "v2": INDEX_BASE_V2, "v3": INDEX_BASE_V3,
        "v4": INDEX_BASE_V4,
    }[cohort]
    directory = root / base / stem
    manifest = read_json(directory / "manifest.json")
    rows_path = directory / "observations.jsonl"
    if rows_path.is_symlink():
        raise ValueError("source observation file must not be a symlink")
    raw = rows_path.read_bytes()
    if (
        manifest["schema_version"] != 1
        or manifest["source"] != "MAME"
        or manifest["license"] != "CC0-1.0"
        or manifest["original_xml_sha256"] != original["original_xml_sha256"]
        or manifest["original_source_list"] != original["source_list_name"]
        or manifest["index_path"] != "observations.jsonl"
        or manifest["index_bytes"] != len(raw)
        or manifest["index_sha256"] != hashlib.sha256(raw).hexdigest()
        or manifest["index_rows"] != original["source_software_entries"]
    ):
        raise ValueError(f"MAME original source index is modified: {filename}")
    lines = raw.splitlines()
    if len(lines) != manifest["index_rows"] or (raw and not raw.endswith(b"\n")):
        raise ValueError(f"truncated MAME source index: {filename}")
    for ordinal, line in enumerate(lines, 1):
        row = json.loads(line)
        if (
            row["source"] != "MAME"
            or row["source_list"] != original["source_list_name"]
            or row["original_xml_sha256"] != original["original_xml_sha256"]
            or row["original_software_ordinal"] != ordinal
        ):
            raise ValueError(f"MAME original record identity drifted: {filename}:{ordinal}")
        yield row


def query(root, *, source_list=None, title=None, publisher=None, year=None,
          media_sha1=None, software_name=None,
          without_review_leads=False, cohort="v1-v2", limit=20, offset=0):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("source query limit must be 1..=200")
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("source query offset must be 0..1000000")
    if cohort not in ("v1-v2", "v3", "v4", "all", "all-pinned"):
        raise ValueError("unknown independent CC0 MAME source cohort")
    if without_review_leads and cohort != "v1-v2":
        raise ValueError("review-gap evidence covers only v1-v2 source observations")
    if media_sha1 is not None and not re.fullmatch(r"[a-fA-F0-9]{40}", media_sha1):
        raise ValueError("source media SHA-1 must have forty hex digits")
    if any(value is not None and not value.strip()
           for value in (source_list, title, publisher, year, software_name)):
        raise ValueError("source filters must not be blank")
    active = (
        ("v1", "v2") if cohort == "v1-v2" else
        ("v3",) if cohort == "v3" else
        ("v4",) if cohort == "v4" else
        ("v1", "v2", "v3") if cohort == "all" else
        ("v1", "v2", "v3", "v4")
    )
    registers = [(name, source_register(root, name)) for name in active]
    valid_lists = {
        filename.removesuffix(".xml")
        for _, register in registers for filename in register["files"]
    }
    expected_sources = {"v1-v2": 65, "v3": 4, "v4": 8, "all": 69, "all-pinned": 77}[cohort]
    expected_entries = {"v1-v2": 32953, "v3": 166, "v4": 373, "all": 33119, "all-pinned": 33492}[cohort]
    if len(valid_lists) != expected_sources:
        raise ValueError("incomplete independent MAME source-list inventory")
    if source_list is not None and source_list not in valid_lists:
        raise ValueError(f"unregistered MAME software-list source: {source_list}")
    expected_reports = {
        "v1": (REPORT, 49, 31464),
        "v2": (Path("reports/mame-software-observations-v2-summary.json"), 16, 1489),
        "v3": (Path("reports/mame-software-observations-v3-summary.json"), 4, 166),
        "v4": (Path("reports/mame-software-observations-v4-summary.json"), 8, 373),
    }
    for name in active:
        path, partitions, observations = expected_reports[name]
        source_report = read_json(root / path)
        if (
            source_report["indexed_source_partitions"] != partitions
            or source_report["source_observation_totals"]["software_entries"] != observations
        ):
            raise ValueError(f"original source inventory changed: {name}")
    reviewed_mame_keys = None
    if without_review_leads:
        from query_source_review_units import validate as validate_source_review
        manifest, review_units, _ = validate_source_review(root)
        gap = read_json(root / "reports/source-review-acquisition-gaps-v1.json")
        if (
            gap["schema_version"] != 1
            or gap["source_review_index_sha256"] != manifest["review_index_sha256"]
            or gap["original_source_observation_totals"][
                "original_records_without_any_review_lead"
            ] != 11241
            or gap["original_source_observation_totals"][
                "original_software_entries"
            ] != 32953
        ):
            raise ValueError("source-review gap report is missing or unverified")
        reviewed_mame_keys = {
            (unit["mame"]["source_list"], unit["mame"]["original_software_ordinal"])
            for unit in review_units
        }
        if len(reviewed_mame_keys) != 21712:
            raise ValueError("incomplete original source-review exclusion inventory")
    candidates = []
    matched_count = 0
    search_sha = media_sha1.lower() if media_sha1 else None
    for source_cohort, register in registers:
        for filename in register["files"]:
            if source_list is not None and source_list != filename.removesuffix(".xml"):
                continue
            original = verify_one(root, register, filename)
            for row in original_index_rows(root, filename, original, source_cohort):
                if reviewed_mame_keys is not None and (
                    row["source_list"], row["original_software_ordinal"]
                ) in reviewed_mame_keys:
                    continue
                if title is not None and title.casefold() not in (
                    row["original_title"] or ""
                ).casefold():
                    continue
                if publisher is not None and publisher.casefold() not in (
                    row["original_publisher_literal"] or ""
                ).casefold():
                    continue
                if year is not None and row["original_year_literal"] != year:
                    continue
                if software_name is not None and (
                    row["original_software_attributes"]["name"] != software_name
                ):
                    continue
                if search_sha is not None and not any(
                    media["original_media_attributes"].get("sha1", "").lower() == search_sha
                    for media in row["original_media_claims"]
                ):
                    continue
                matched_count += 1
                if matched_count > offset and len(candidates) < limit:
                    candidates.append(row)
    return {
        "source_mode": "verified-mame-cc0-original-software-records",
        "source_register": f"sources/mame-softlists-{active[0]}.json",
        "additional_source_register": (
            "sources/mame-softlists-v2.json" if "v2" in active else None
        ),
        "all_original_source_registers": [
            f"sources/mame-softlists-{name}.json" for name in active
        ],
        "source_query_cohort": cohort,
        "source_software_entries": expected_entries,
        "original_source_lists": expected_sources,
        "total_filtered_original_records": matched_count,
        "without_any_cross_provider_review_lead": without_review_leads,
        "full_source_review_gap_inventory": 11241 if without_review_leads else None,
        "returned_original_records": len(candidates),
        "offset": offset,
        "next_offset": (
            offset + len(candidates)
            if offset + len(candidates) < matched_count else None
        ),
        "records": candidates,
        "interpretation": (
            "read-only-original-source-claims-without-current-cross-provider-review-leads"
            if without_review_leads else
            "read-only-original-source-claims-not-adjudicated-game-media-or-release-identities"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", dest="source_list")
    parser.add_argument("--title")
    parser.add_argument("--publisher")
    parser.add_argument("--year")
    parser.add_argument("--software-name")
    parser.add_argument("--sha1")
    parser.add_argument("--without-review-leads", action="store_true")
    parser.add_argument("--cohort", choices=["v1-v2", "v3", "v4", "all", "all-pinned"], default="v1-v2")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0,
                        help="filtered original source observations to skip")
    args = parser.parse_args()
    result = query(
        ROOT, source_list=args.source_list, title=args.title,
        publisher=args.publisher, year=args.year,
        software_name=args.software_name, media_sha1=args.sha1,
        without_review_leads=args.without_review_leads,
        cohort=args.cohort, limit=args.limit, offset=args.offset,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
