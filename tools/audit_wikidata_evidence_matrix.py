#!/usr/bin/env python3
"""Rebuild an offline, per-platform Wikidata source-yield matrix.

All counts are observations in preserved source partitions, never canonical
game/release counts. This script makes no network requests and writes no
changes to original source captures.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("reports/wikidata-source-coverage-matrix-v1.json")
GAPS = Path("reports/wikidata-p400-platform-gaps-v2.json")
FAMILIES = ("text", "localized", "credits", "relations")
EXPECTED_TOTALS = {"localized": 154198, "credits": 58460, "relations": 113204}


def read(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"symbolic link in source manifest path: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def source_registers(root):
    register_paths = ["sources/wikidata-v1.json"] + [
        f"sources/wikidata-platform-expansion-v{version}.json"
        for version in range(1, 9)
    ]
    result = {}
    for version, path in enumerate(register_paths):
        register = read(root, path)
        if register["schema_version"] != 1:
            raise ValueError(f"unsupported Wikidata source register: {path}")
        for row in register["platforms"]:
            platform = row["platform"]
            if not platform.isalnum() or not platform.islower():
                raise ValueError(f"unsafe original platform identifier: {platform}")
            if platform in result:
                raise ValueError(f"duplicate P400 platform across cohorts: {platform}")
            qid = row["wikidata_platform"]
            if not qid.startswith("Q") or not qid[1:].isdigit() or qid[1] == "0":
                raise ValueError(f"invalid P400 source register QID: {platform}")
            result[platform] = {
                "version": version,
                "source_register": path,
                "wikidata_platform": qid,
                "scope_status": (
                    "provisional-provider-query-target"
                    if version == 8 else "registered-provider-query-target"
                ),
            }
    if len(result) != 65:
        raise ValueError(f"expected 65 registered source scopes, got {len(result)}")
    return result


def family_base(family, version):
    if version == 0:
        return {
            "text": "data/wikidata/v1",
            "localized": "data/wikidata/localized-titles-v1",
            "credits": "data/wikidata/properties-v1",
            "relations": "data/wikidata/relations-v1",
        }[family]
    if family == "text":
        return f"data/wikidata/platform-expansion-v{version}"
    cohort = 1 if version <= 4 else 2 if version <= 7 else 3
    return f"data/wikidata/expanded-{family}-v{cohort}"


def build_report(root=ROOT):
    registers = source_registers(root)
    gaps = read(root, GAPS)
    missing = {row["platform"]: row for row in gaps["gaps"]}
    if (
        gaps["libretro_source_collections"] != 75
        or gaps["registered_wikidata_p400_platform_scopes"] != 65
        or len(missing) != 10
        or set(missing).intersection(registers)
    ):
        raise ValueError("source coverage gap inventory is stale or inconsistent")
    baseline = read(root, "data/wikidata/v1/manifest.json")
    originals = {row["platform"]: row for row in baseline["files"]}
    if len(originals) != 16:
        raise ValueError("baseline Wikidata text snapshot has incomplete platform coverage")
    platform_rows = []
    totals = {family: 0 for family in FAMILIES}
    empty_counts = {family: 0 for family in FAMILIES}
    for platform, source in sorted(registers.items()):
        version = source["version"]
        family_rows = {}
        provenance = {}
        for family in FAMILIES:
            if version == 0 and family == "text":
                manifest = originals[platform]
                relative = "data/wikidata/v1/manifest.json"
            else:
                relative = f"{family_base(family, version)}/{platform}/manifest.json"
                manifest = read(root, relative)
                if manifest["platform"] != platform:
                    raise ValueError(f"source manifest scope mismatch: {relative}")
                if manifest["wikidata_platform"] != source["wikidata_platform"]:
                    raise ValueError(f"Wikidata QID mismatch: {relative}")
            count = manifest["source_rows"]
            if not isinstance(count, int) or count < 0:
                raise ValueError(f"invalid source observation count: {relative}")
            family_rows[family] = count
            provenance[family] = relative
            totals[family] += count
            empty_counts[family] += count == 0
        platform_rows.append({
            "platform": platform,
            "wikidata_platform": source["wikidata_platform"],
            "register_cohort": "baseline" if version == 0 else f"v{version}",
            "scope_status": source["scope_status"],
            "source_register": source["source_register"],
            "source_rows": family_rows,
            "source_manifests": provenance,
            "empty_source_families": [
                family for family, count in family_rows.items() if count == 0
            ],
            "all_four_families_empty": all(value == 0 for value in family_rows.values()),
        })
    if totals["localized"] != EXPECTED_TOTALS["localized"] or any(
        totals[key] != EXPECTED_TOTALS[key] for key in ("credits", "relations")
    ):
        raise ValueError(f"source manifest counts diverged from pinned cohort totals: {totals}")
    uncovered = [
        {
            "platform": name,
            "source_label": row["source_label"],
            "review_class": row["review_class"],
            "coverage_status": "no-independent-P400-register",
        }
        for name, row in sorted(missing.items())
    ]
    return {
        "schema_version": 1,
        "kind": "independent-wikidata-source-yield-matrix",
        "source_gap_report": str(GAPS),
        "registered_source_platform_scopes": len(platform_rows),
        "libretro_source_collections": 75,
        "unregistered_libretro_source_collections": len(uncovered),
        "source_family_observation_totals": totals,
        "source_family_zero_row_scopes": empty_counts,
        "all_source_families_empty_scopes": [
            entry["platform"] for entry in platform_rows
            if entry["all_four_families_empty"]
        ],
        "registered_scopes": platform_rows,
        "unregistered_collections": uncovered,
        "interpretation": (
            "Counts represent original attributed source rows within separate P400 "
            "query scopes, not unique games or releases, adjudicated associations, "
            "or completeness of any source. Zero-row queries are scoped provider "
            "noncoverage and are not evidence that a platform has no games."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    target = ROOT / OUTPUT
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            parser.error(f"stale source-coverage report: {OUTPUT} (run --write)")
        print(f"verified {OUTPUT}")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
