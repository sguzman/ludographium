#!/usr/bin/env python3
"""Search reproducible, noncanonical three-provider source coverage by scope."""
import argparse
import json
from pathlib import Path

from audit_three_provider_source_coverage import ROOT, OUTPUT, build_report

COVERAGE_CLASSES = (
    "both-independent-secondary-source-families",
    "wikidata-source-rows-only",
    "mame-exact-media-evidence-only",
    "neither-secondary-source-family-observed",
)


def query(root=ROOT, *, platform=None, coverage_class=None,
          wikidata_registered=None, no_mame_media=False,
          min_source_records=0, limit=20):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("scope query limit must be 1 through 200")
    if type(min_source_records) is not int or not 0 <= min_source_records <= 1000000:
        raise ValueError("source-record lower bound outside supported range")
    if platform is not None and (
        not isinstance(platform, str) or not platform.strip()
        or len(platform) > 100
    ):
        raise ValueError("invalid original Libretro source-scope filter")
    if coverage_class is not None and coverage_class not in COVERAGE_CLASSES:
        raise ValueError("unsupported independent-provider evidence class")
    if wikidata_registered is not None and type(wikidata_registered) is not bool:
        raise ValueError("Wikidata P400 registration filter must be boolean")
    expected = json.dumps(build_report(root), ensure_ascii=False, indent=2) + "\n"
    source_path = root / OUTPUT
    if (
        not source_path.is_file()
        or source_path.is_symlink()
        or source_path.read_text(encoding="utf-8") != expected
    ):
        raise ValueError("three-provider coverage differs from pinned original evidence")
    report = json.loads(expected)
    matches = []
    total = 0
    for row in report["source_collections"]:
        if platform is not None and row["libretro_original_platform_scope"] != platform:
            continue
        if coverage_class is not None and (
            row["secondary_source_evidence_coverage_class"] != coverage_class
        ):
            continue
        if wikidata_registered is not None and (
            (row["wikidata_p400_source_registration"] is not None)
            != wikidata_registered
        ):
            continue
        if no_mame_media and row["source_media_candidate_rows"] != 0:
            continue
        if row["libretro_original_dat_source_records"] < min_source_records:
            continue
        total += 1
        if len(matches) < limit:
            matches.append(row)
    return {
        "source_mode": "verified-three-provider-source-acquisition-coverage",
        "libretro_source_collection_count": 75,
        "wikidata_registered_p400_scope_count": 65,
        "mame_independent_source_list_count": 65,
        "source_evidence_class_counts": report[
            "source_evidence_coverage_class_counts"
        ],
        "total_filtered_original_source_collections": total,
        "returned_source_collections": len(matches),
        "source_collections": matches,
        "interpretation": (
            "Secondary-provider source coverage only: zero matches are not "
            "missing game, release, edition or platform identities."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", help="Original Libretro collection scope")
    parser.add_argument("--class", dest="coverage_class", choices=COVERAGE_CLASSES)
    parser.add_argument("--wikidata-registered", choices=["yes", "no"])
    parser.add_argument("--no-mame-media", action="store_true")
    parser.add_argument("--min-records", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    registered = (
        None if args.wikidata_registered is None
        else args.wikidata_registered == "yes"
    )
    result = query(
        ROOT, platform=args.platform, coverage_class=args.coverage_class,
        wikidata_registered=registered, no_mame_media=args.no_mame_media,
        min_source_records=args.min_records, limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
