#!/usr/bin/env python3
"""Cross-tabulate independently pinned Libretro, MAME, Wikidata evidence.

P400 register IDs are explicit source labels; MAME software lists are related
to Libretro source scopes only by verified equal-SHA1/byte-size media claims.
This is an acquisition-coverage index, not accepted platform or game identities.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT

WIKIDATA = Path("reports/wikidata-source-coverage-matrix-v1.json")
MAME_COVERAGE = Path("reports/mame-libretro-source-coverage-v1.json")
MEDIA_REPORT = Path("reports/mame-libretro-media-sha1-v1-summary.json")
MEDIA_INDEX = Path("data/reconciliation/mame-libretro-sha1-v1/links.jsonl")
OUTPUT = Path("reports/three-provider-source-coverage-v1.json")
EVIDENCE_FAMILIES = ("text", "localized", "credits", "relations")
POLICY = (
    "Libretro DAT records, Wikidata P400 scopes and MAME software lists are "
    "independent sources. Wikidata QIDs come from explicit source registrations. "
    "A MAME list appears as related evidence only when original SHA1 and size "
    "claims overlap with Libretro; neither platform identity nor individual "
    "game/work/release identity is inferred from the overlap. Zero-row "
    "comparisons show provider-query noncoverage, not absent games."
)


def read_bytes(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"source coverage symlink not accepted: {relative}")
    return path.read_bytes()


def read_json(root, path):
    return json.loads(read_bytes(root, path))


def source_coverage_class(has_wikidata_data, has_mame_media):
    if has_wikidata_data and has_mame_media:
        return "both-independent-secondary-source-families"
    if has_wikidata_data:
        return "wikidata-source-rows-only"
    if has_mame_media:
        return "mame-exact-media-evidence-only"
    return "neither-secondary-source-family-observed"


def build_report(root=ROOT):
    wd = read_json(root, WIKIDATA)
    mc = read_json(root, MAME_COVERAGE)
    media_report = read_json(root, MEDIA_REPORT)
    media_raw = read_bytes(root, MEDIA_INDEX)
    if (
        wd["schema_version"] != 1
        or wd["kind"] != "independent-wikidata-source-yield-matrix"
        or wd["registered_source_platform_scopes"] != 65
        or wd["libretro_source_collections"] != 75
        or mc["schema_version"] != 1
        or mc["kind"] != "source-only-mame-libretro-exact-sha1-gap-analysis"
        or mc["libretro_source_collections"] != 75
        or mc["mame_source_list_count"] != 65
        or media_report["mame_software_lists"] != 65
        or media_report["libretro_source_platforms"] != 75
        or media_report["exact_sha1_source_candidate_pairs"] != 19025
        or media_report["match_index_path"] != str(MEDIA_INDEX)
        or media_report["match_index_bytes"] != len(media_raw)
        or media_report["match_index_sha256"] != hashlib.sha256(media_raw).hexdigest()
        or mc["source_media_sha256"] != media_report["match_index_sha256"]
        or (media_raw and not media_raw.endswith(b"\n"))
    ):
        raise ValueError("independent provider registers or source-evidence hashes changed")
    source_wd = {row["platform"]: row for row in wd["registered_scopes"]}
    source_lib = {row["source_platform"]: row for row in mc["libretro_source_scopes"]}
    source_mame = {row["source_list"]: row for row in mc["mame_source_lists"]}
    if len(source_wd) != 65 or len(source_lib) != 75 or len(source_mame) != 65:
        raise ValueError("duplicate or missing pinned source scope")
    if set(source_wd) - set(source_lib):
        raise ValueError("Wikidata query scopes are not registered Libretro source collections")
    if len(wd["unregistered_collections"]) != 10 or {
        row["platform"] for row in wd["unregistered_collections"]
    } != set(source_lib) - set(source_wd):
        raise ValueError("Wikidata noncoverage register is stale")
    pairs = defaultdict(Counter)
    distinct_mame = defaultdict(set)
    distinct_libretro = defaultdict(set)
    inspected = 0
    for line in media_raw.splitlines():
        source = json.loads(line)
        mame, libretro = source["mame"], source["libretro"]
        scope = libretro["platform"]
        list_id = mame["source_list"]
        if (
            source["schema_version"] != 1
            or source["kind"] != "exact-mame-libretro-media-sha1-source-candidate"
            or not source["size_corroborated"]
            or mame["source_size_bytes"] != libretro["media_size_bytes"]
            or scope not in source_lib or list_id not in source_mame
        ):
            raise ValueError(f"unverified MAME/Libretro source pair at row {inspected+1}")
        pairs[scope][list_id] += 1
        distinct_mame[(scope, list_id)].add(mame["software_ordinal"])
        distinct_libretro[(scope, list_id)].add(libretro["source_record_ordinal"])
        inspected += 1
    if inspected != 19025:
        raise ValueError("incomplete original source media overlap index")
    result = []
    for platform, row in sorted(source_lib.items()):
        wd_row = source_wd.get(platform)
        fields = (
            dict(wd_row["source_rows"])
            if wd_row is not None
            else {family: 0 for family in EVIDENCE_FAMILIES}
        )
        if set(fields) != set(EVIDENCE_FAMILIES):
            raise ValueError(f"unexpected Wikidata source claim properties for {platform}")
        has_wikidata_data = any(count > 0 for count in fields.values())
        related = [
            {
                "mame_original_source_list": list_id,
                "exact_media_sha1_source_candidate_rows": number,
                "distinct_mame_source_software_records": len(distinct_mame[(platform,list_id)]),
                "distinct_libretro_source_records": len(distinct_libretro[(platform,list_id)]),
                "relationship_basis": "equal-original-media-sha1-and-declared-size-only",
            }
            for list_id, number in sorted(pairs[platform].items())
        ]
        original_links = sum(pair["exact_media_sha1_source_candidate_rows"] for pair in related)
        if (
            original_links != row["original_cross_source_candidate_pairs"]
            or (bool(original_links) != bool(row["records_with_exact_media_sha1_overlap"]))
        ):
            raise ValueError(f"Libretro evidence row counts conflict: {platform}")
        result.append({
            "libretro_original_platform_scope": platform,
            "libretro_original_dat_source_records": row["original_dat_records"],
            "libretro_original_records_with_media_overlap": row[
                "records_with_exact_media_sha1_overlap"
            ],
            "wikidata_p400_source_registration": (
                {
                    "qid": wd_row["wikidata_platform"],
                    "register_cohort": wd_row["register_cohort"],
                    "scope_status": wd_row["scope_status"],
                    "source_register": wd_row["source_register"],
                    "source_family_rows": fields,
                    "source_manifests": wd_row["source_manifests"],
                }
                if wd_row is not None else None
            ),
            "wikidata_registered_platform_has_any_source_rows": has_wikidata_data,
            "mame_source_list_media_evidence": related,
            "related_mame_source_list_count": len(related),
            "source_media_candidate_rows": original_links,
            "secondary_source_evidence_coverage_class": source_coverage_class(
                has_wikidata_data, original_links > 0
            ),
        })
    totals = Counter(
        entry["secondary_source_evidence_coverage_class"] for entry in result
    )
    if (
        len(result) != 75
        or sum(row["libretro_original_dat_source_records"] for row in result) != 117145
        or sum(row["source_media_candidate_rows"] for row in result) != 19025
        or sum(bool(row["wikidata_p400_source_registration"]) for row in result) != 65
    ):
        raise ValueError("tri-provider source coverage did not reconcile")
    return {
        "schema_version": 1,
        "kind": "independent-three-provider-source-acquisition-coverage",
        "source_registers_and_reports": {
            "wikidata_yield_report": str(WIKIDATA),
            "mame_libretro_source_coverage": str(MAME_COVERAGE),
            "media_sha1_source_report": str(MEDIA_REPORT),
            "media_sha1_index_sha256": media_report["match_index_sha256"],
        },
        "libretro_source_collection_count": 75,
        "mame_independent_source_list_count": 65,
        "wikidata_registered_p400_scope_count": 65,
        "wikidata_unregistered_p400_scope_count": 10,
        "original_libretro_dat_records": 117145,
        "cross_provider_media_sha1_evidence_rows": inspected,
        "source_evidence_coverage_class_counts": dict(sorted(totals.items())),
        "no_current_secondary_source_family_observations": [
            row["libretro_original_platform_scope"] for row in result
            if row["secondary_source_evidence_coverage_class"]
            == "neither-secondary-source-family-observed"
        ],
        "source_collections": result,
        "interpretation": POLICY,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    target = ROOT / OUTPUT
    if args.write:
        target.write_text(text, encoding="utf-8")
    elif not target.is_file() or target.is_symlink() or target.read_text(encoding="utf-8") != text:
        parser.error("three-provider source acquisition report is missing or stale")
    print(f"verified all 75 independent original platform source coverage rows")


if __name__ == "__main__":
    main()
