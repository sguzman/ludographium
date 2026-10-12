#!/usr/bin/env python3
"""Read-only search over all 32,953 provenance-verified MAME software records."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from acquire_mame_softlists import ROOT, source_register, verify_one

INDEX_BASE = Path("data/mame/software-observations-v1")
INDEX_BASE_V2 = Path("data/mame/software-observations-v2")
REPORT = Path("reports/mame-software-observations-v1-summary.json")


def read_json(path):
    if path.is_symlink():
        raise ValueError(f"symlink in original MAME source index: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def original_index_rows(root, filename, original, cohort="v1"):
    stem = filename.removesuffix(".xml")
    base = INDEX_BASE if cohort == "v1" else INDEX_BASE_V2
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
          without_review_leads=False, limit=20):
    if not 1 <= limit <= 200:
        raise ValueError("source query limit must be 1..=200")
    if media_sha1 is not None and not re.fullmatch(r"[a-fA-F0-9]{40}", media_sha1):
        raise ValueError("source media SHA-1 must have forty hex digits")
    if any(value is not None and not value.strip()
           for value in (source_list, title, publisher, year, software_name)):
        raise ValueError("source filters must not be blank")
    registers = [
        (cohort, source_register(root, cohort))
        for cohort in ("v1", "v2")
    ]
    valid_lists = {
        filename.removesuffix(".xml")
        for _, register in registers for filename in register["files"]
    }
    if len(valid_lists) != 65:
        raise ValueError("expected 65 independent MAME source lists")
    if source_list is not None and source_list not in valid_lists:
        raise ValueError(f"unregistered MAME software-list source: {source_list}")
    summary = read_json(root / REPORT)
    second = read_json(root / "reports/mame-software-observations-v2-summary.json")
    if (
        summary["indexed_source_partitions"] != 49
        or summary["source_observation_totals"]["software_entries"] != 31464
        or second["indexed_source_partitions"] != 16
        or second["source_observation_totals"]["software_entries"] != 1489
    ):
        raise ValueError("MAME source inventory count changed")
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
    for cohort, register in registers:
        for filename in register["files"]:
            if source_list is not None and source_list != filename.removesuffix(".xml"):
                continue
            original = verify_one(root, register, filename)
            for row in original_index_rows(root, filename, original, cohort):
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
                if len(candidates) < limit:
                    candidates.append(row)
    return {
        "source_mode": "verified-mame-cc0-original-software-records",
        "source_register": "sources/mame-softlists-v1.json",
        "additional_source_register": "sources/mame-softlists-v2.json",
        "source_software_entries": 32953,
        "original_source_lists": 65,
        "total_filtered_original_records": matched_count,
        "without_any_cross_provider_review_lead": without_review_leads,
        "full_source_review_gap_inventory": 11241 if without_review_leads else None,
        "returned_original_records": len(candidates),
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
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = query(
        ROOT, source_list=args.source_list, title=args.title,
        publisher=args.publisher, year=args.year,
        software_name=args.software_name, media_sha1=args.sha1,
        without_review_leads=args.without_review_leads, limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
