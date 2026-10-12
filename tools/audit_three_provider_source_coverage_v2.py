#!/usr/bin/env python3
"""Add the pinned third MAME source wave to the independent provider coverage map.

The older 65-list report remains immutable. New source lists are related to
Libretro scopes only by exact media SHA1/equal declared-size evidence; this
report cannot assert platform, edition, work, or game identity.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT
from audit_three_provider_source_coverage import (
    OUTPUT as PREVIOUS_REPORT, build_report as build_original,
    source_coverage_class,
)
from reconcile_mame_v3_media import (
    OUTPUT as THIRD_LINKS, REPORT as THIRD_REPORT,
    build_expected as build_third,
)

REPORT = Path("reports/three-provider-source-coverage-v2.json")
POLICY = (
    "Source-only incremental third-cohort MAME evidence added without modifying "
    "the preceding 65-list provider map. Cross-source MAME/Libretro media SHA1 "
    "and size equality is only a review candidate, never an accepted game, "
    "platform, work, release, or edition identity. No Wikidata registration "
    "or zero-result query is interpreted as proof of absent games."
)


def build_report(root=ROOT):
    old = build_original(root)
    expected_old_text = json.dumps(old, ensure_ascii=False, indent=2) + "\n"
    previous = root / PREVIOUS_REPORT
    if previous.is_symlink() or previous.read_text(encoding="utf-8") != expected_old_text:
        raise ValueError("first coverage report has changed from pinned original evidence")
    raw_v3, rejected_v3, report_v3 = build_third(root)
    third = json.loads(report_v3)
    path, conflict_path, report_path = (
        root / THIRD_LINKS,
        root / Path("data/reconciliation/mame-libretro-sha1-v3/size-disagreements.jsonl"),
        root / THIRD_REPORT,
    )
    if (
        third["schema_version"] != 1
        or third["kind"] != "separate-third-cohort-exact-original-media-source-candidates"
        or third["mame_original_source_lists"] != 4
        or third["mame_original_software_observations"] != 166
        or third["mame_original_sha1_claims"] != 199
        or third["independent_libretro_dat_collections"] != 75
        or third["candidate_sha256"] != hashlib.sha256(raw_v3).hexdigest()
        or third["candidate_bytes"] != len(raw_v3)
        or third["rejected_size_conflicts_sha256"] != hashlib.sha256(rejected_v3).hexdigest()
        or path.is_symlink() or path.read_bytes() != raw_v3
        or conflict_path.is_symlink() or conflict_path.read_bytes() != rejected_v3
        or report_path.is_symlink()
        or report_path.read_text(encoding="utf-8") != report_v3
    ):
        raise ValueError("third MAME cohort source-evidence report is missing or stale")
    by_scope = defaultdict(Counter)
    by_scope_mame_records = defaultdict(set)
    by_scope_libretro_records = defaultdict(set)
    for line in raw_v3.splitlines():
        claim = json.loads(line)
        mame, libretro = claim["mame"], claim["libretro"]
        if (
            claim["schema_version"] != 1
            or claim["kind"] != "review-only-v3-mame-libretro-exact-media-sha1-candidate"
            or not claim["size_corroborated"]
            or mame["original_declared_size_bytes"] != libretro["original_media_size_bytes"]
        ):
            raise ValueError("unreviewed size-unconfirmed evidence cannot contribute coverage")
        pair = (libretro["platform"], mame["source_list"])
        by_scope[pair[0]][pair[1]] += 1
        by_scope_mame_records[pair].add(mame["software_ordinal"])
        by_scope_libretro_records[pair].add(libretro["source_record_ordinal"])
    previous_classes = Counter(
        row["secondary_source_evidence_coverage_class"]
        for row in old["source_collections"]
    )
    upgraded, current_classes = [], Counter()
    changed = []
    totals_v3 = 0
    for existing in old["source_collections"]:
        platform = existing["libretro_original_platform_scope"]
        additions = [
            {
                "mame_original_source_list": list_id,
                "exact_media_sha1_source_candidate_rows": count,
                "distinct_mame_source_software_records": len(
                    by_scope_mame_records[(platform, list_id)]
                ),
                "distinct_libretro_source_records": len(
                    by_scope_libretro_records[(platform, list_id)]
                ),
                "relationship_basis": "equal-original-media-sha1-and-declared-size-only",
                "source_cohort": "mame-v3",
            }
            for list_id, count in sorted(by_scope[platform].items())
        ]
        original_links = existing["source_media_candidate_rows"]
        extra_links = sum(x["exact_media_sha1_source_candidate_rows"] for x in additions)
        totals_v3 += extra_links
        has_secondary_wikidata_rows = existing[
            "wikidata_registered_platform_has_any_source_rows"
        ]
        current_class = source_coverage_class(
            has_secondary_wikidata_rows, original_links + extra_links > 0
        )
        if current_class != existing["secondary_source_evidence_coverage_class"]:
            changed.append({
                "libretro_original_platform_scope": platform,
                "previous_source_coverage_class": existing[
                    "secondary_source_evidence_coverage_class"
                ],
                "updated_source_coverage_class": current_class,
                "additional_original_media_evidence_rows": extra_links,
            })
        upgraded.append({
            **existing,
            "additional_mame_v3_original_media_source_lists": additions,
            "additional_mame_v3_media_evidence_rows": extra_links,
            "all_mame_source_evidence_rows": original_links + extra_links,
            "updated_source_evidence_coverage_class": current_class,
        })
        current_classes[current_class] += 1
    if (
        len(upgraded) != 75
        or totals_v3 != third["source_media_sha1_candidate_pairs"]
        or sum(x["all_mame_source_evidence_rows"] for x in upgraded)
           != 19025 + third["source_media_sha1_candidate_pairs"]
        or sum(current_classes.values()) != 75
    ):
        raise ValueError("incremental third-cohort platform coverage is incomplete")
    return {
        "schema_version": 2,
        "kind": "independent-three-provider-source-acquisition-coverage",
        "preceding_65_mame_list_report": str(PREVIOUS_REPORT),
        "preceding_report_sha256": hashlib.sha256(
            expected_old_text.encode("utf-8")
        ).hexdigest(),
        "supplemental_mame_v3_source_report": str(THIRD_REPORT),
        "supplemental_mame_v3_source_index_sha256": third["candidate_sha256"],
        "libretro_original_source_collections": 75,
        "wikidata_registered_p400_scopes": 65,
        "mame_original_source_lists": 69,
        "mame_original_software_observations": 33119,
        "libretro_original_dat_records": 117145,
        "previous_media_sha1_source_candidate_pairs": 19025,
        "new_mame_v3_media_sha1_source_candidate_pairs": totals_v3,
        "total_separate_evidence_pair_observations": 19025 + totals_v3,
        "previous_secondary_source_coverage_classes": dict(sorted(previous_classes.items())),
        "updated_secondary_source_coverage_classes": dict(sorted(current_classes.items())),
        "original_source_scopes_gaining_secondary_evidence": changed,
        "original_libretro_collection_scope_rows": upgraded,
        "interpretation": POLICY,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    argspec = parser.add_mutually_exclusive_group(required=True)
    argspec.add_argument("--write", action="store_true")
    argspec.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    target = ROOT / REPORT
    if args.write:
        target.write_text(text, encoding="utf-8")
    elif not target.is_file() or target.is_symlink() or target.read_text(encoding="utf-8") != text:
        parser.error("incremental source-evidence coverage report differs from original claims")
    report = json.loads(text)
    print(
        f"verified {report['mame_original_source_lists']} MAME source lists; "
        f"{len(report['original_source_scopes_gaining_secondary_evidence'])} original "
        "Libretro source scopes gained evidence"
    )


if __name__ == "__main__":
    main()
