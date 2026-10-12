#!/usr/bin/env python3
"""Audit untouched MAME source observations with no cross-provider review lead.

Source review gaps are missing *evidence correspondence*, never missing games.
All 65 CC0 software lists and 75 Libretro source scopes remain independent.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from acquire_mame_softlists import ROOT, source_register, verify_one
from query_mame_sources import original_index_rows
from query_source_review_units import validate as validate_review_units
from build_source_review_units import MEDIA_INDEX, TITLE_INDEX

OUTPUT = Path("reports/source-review-acquisition-gaps-v1.json")
INTERPRETATION = (
    "Unlinked means no original MAME record has any pinned exact SHA-1/size "
    "match or SHA1-supported exact-title source-review candidate. It does not "
    "imply an absent game, unrecognized release, rejected identity, or a "
    "complete upstream inventory. This is an independent-provider "
    "bulk-acquisition priority diagnostic only."
)


def build_report(root=ROOT):
    manifest, review_units, _ = validate_review_units(root)
    counts = defaultdict(Counter)
    original = {}
    titles = {}
    seen_ordinals = set()
    target_scope_units = defaultdict(set)
    for unit in review_units:
        source = unit["mame"]
        source_list = source["source_list"]
        ordinal = source["original_software_ordinal"]
        key = (source_list, ordinal)
        if key in seen_ordinals:
            raise ValueError("source review task duplicated original MAME record")
        seen_ordinals.add(key)
        if source_list in original and original[source_list] != source["original_xml_sha256"]:
            raise ValueError("different source snapshots silently share a source list")
        original[source_list] = source["original_xml_sha256"]
        evidence = (
            "media" if unit["media_evidence_jsonl_source_ordinals"] else "title"
        )
        if evidence == "title" and not unit["title_evidence_jsonl_source_ordinals"]:
            raise ValueError("review unit has no verifiable source evidence")
        counts[source_list][evidence] += 1
        if unit["multiple_source_target_alternatives"]:
            counts[source_list]["ambiguous"] += 1
        titles[key] = source["original_title"]
        for target in unit["candidate_libretro_targets"]:
            target_scope_units[target["platform"]].add(key)
    listed = []
    source_entries = 0
    for cohort in ("v1", "v2"):
        register = source_register(root, cohort)
        for filename in register["files"]:
            details = verify_one(root, register, filename)
            list_name = details["source_list_name"]
            if list_name in {row["source_list"] for row in listed}:
                raise ValueError("MAME source list repeated across independent cohorts")
            present_review = counts[list_name]
            if (
                list_name in original
                and original[list_name] != details["original_xml_sha256"]
            ):
                raise ValueError("source-review snapshot differs from original XML")
            original_count = 0
            without_leads = 0
            for row in original_index_rows(root, filename, details, cohort):
                source_entries += 1
                original_count += 1
                key = (list_name, row["original_software_ordinal"])
                if key in seen_ordinals:
                    if titles[key] != row["original_title"]:
                        raise ValueError("review evidence original title changed")
                else:
                    without_leads += 1
            if original_count != details["source_software_entries"]:
                raise ValueError(f"original MAME source count incomplete: {list_name}")
            media = present_review["media"]
            title = present_review["title"]
            if media + title + without_leads != original_count:
                raise ValueError(f"review gap counts overlap: {list_name}")
            listed.append({
                "source_list": list_name,
                "source_cohort": cohort,
                "original_xml_sha256": details["original_xml_sha256"],
                "original_source_software_entries": original_count,
                "records_with_exact_media_sha1_evidence": media,
                "records_with_conservative_title_only_leads": title,
                "records_with_no_cross_provider_review_lead": without_leads,
                "ambiguous_review_units": present_review["ambiguous"],
                "has_any_review_evidence": bool(media or title),
            })
    listed.sort(key=lambda item: item["source_list"])
    totals = {
        "original_software_entries": source_entries,
        "exact_media_supported_original_records": sum(
            item["records_with_exact_media_sha1_evidence"] for item in listed
        ),
        "conservative_title_only_original_records": sum(
            item["records_with_conservative_title_only_leads"] for item in listed
        ),
        "original_records_without_any_review_lead": sum(
            item["records_with_no_cross_provider_review_lead"] for item in listed
        ),
        "ambiguous_original_review_units": sum(
            item["ambiguous_review_units"] for item in listed
        ),
    }
    if (
        len(listed) != 65
        or totals["original_software_entries"] != 32953
        or totals["exact_media_supported_original_records"] != 19013
        or totals["conservative_title_only_original_records"] != 2699
        or totals["original_records_without_any_review_lead"] != 11241
        or totals["ambiguous_original_review_units"] != 2042
        or totals["exact_media_supported_original_records"] +
        totals["conservative_title_only_original_records"] !=
        manifest["source_review_units"]
    ):
        raise ValueError(f"stale 65-scope source-review coverage inventory: {totals}")
    source_platforms = sorted({
        item["platform"]
        for unit in review_units
        for item in unit["candidate_libretro_targets"]
    })
    return {
        "schema_version": 1,
        "kind": "provenance-verified-bulk-acquisition-source-review-gaps",
        "source_review_manifest": "reports/source-review-units-v1-summary.json",
        "source_review_index_sha256": manifest["review_index_sha256"],
        "original_media_evidence_jsonl_path": str(MEDIA_INDEX),
        "original_title_evidence_jsonl_path": str(TITLE_INDEX),
        "independent_mame_source_lists": len(listed),
        "independent_libretro_source_collections": 75,
        "original_source_observation_totals": totals,
        "mame_lists_without_any_cross_provider_review_leads": [
            item["source_list"] for item in listed
            if not item["has_any_review_evidence"]
        ],
        "libretro_source_scopes_with_review_leads": source_platforms,
        "libretro_source_scopes_with_review_leads_count": len(source_platforms),
        "mame_source_lists_sorted_by_unlinked_source_records": sorted(
            listed,
            key=lambda item: (
                -item["records_with_no_cross_provider_review_lead"],
                item["source_list"],
            ),
        ),
        "interpretation": INTERPRETATION,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build_report(), indent=2, ensure_ascii=False) + "\n"
    path = ROOT / OUTPUT
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    elif path.is_symlink() or not path.exists() or path.read_text(encoding="utf-8") != text:
        parser.error("source-review acquisition gap report is missing or stale")
    summary = json.loads(text)
    print(
        "verified independent original-source review acquisition coverage: "
        f"{summary['original_source_observation_totals']['original_records_without_any_review_lead']} "
        "source records without cross-provider evidence"
    )


if __name__ == "__main__":
    main()
