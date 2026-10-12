#!/usr/bin/env python3
"""Source-only coverage planning from pinned MAME/Libretro SHA-1 overlaps.

No games, editions or platforms are inferred equivalent. Missing digest overlap
can result from distinct dumps, ROM-header variations, disc images, split chips
or provider coverage; it is never interpreted as an absent game.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT
from reconcile_mame_media import read_libretro
from build_expanded_corpus import pinned_manifest

LINKS = Path("data/reconciliation/mame-libretro-sha1-v1/links.jsonl")
SOURCE_REPORT = Path("reports/mame-libretro-media-sha1-v1-summary.json")
MAME_REPORT = Path("reports/mame-softlists-v1-summary.json")
MAME_REPORT_V2 = Path("reports/mame-softlists-v2-summary.json")
OUTPUT = Path("reports/mame-libretro-source-coverage-v1.json")
POLICY = (
    "These are independent source-row overlap diagnostics, not a count of "
    "missing games, unverified editions or canonical platform identities. "
    "No matching media digest may reflect different formats, dump headers, "
    "split chips, optical discs or distinct provider inventories."
)


def read_json(path):
    if path.is_symlink():
        raise ValueError(f"symbolic link in source evidence: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(root=ROOT):
    match_summary = read_json(root / SOURCE_REPORT)
    mame_summary = read_json(root / MAME_REPORT)
    mame_summary_v2 = read_json(root / MAME_REPORT_V2)
    target = root / LINKS
    if target.is_symlink():
        raise ValueError("symlinked cross-source media index")
    raw = target.read_bytes()
    if (
        match_summary["schema_version"] != 1
        or match_summary["match_index_path"] != str(LINKS)
        or match_summary["match_index_bytes"] != len(raw)
        or match_summary["match_index_sha256"] != hashlib.sha256(raw).hexdigest()
        or match_summary["mame_software_lists"] != 65
        or match_summary["libretro_source_platforms"] != 75
        or mame_summary["software_list_partitions"] != 49
        or mame_summary_v2["software_list_partitions"] != 16
    ):
        raise ValueError("pinned source summary or media correspondence digest mismatch")
    index, libretro_totals = read_libretro(root)
    original_by_scope = defaultdict(set)
    for observations in index.values():
        for claim in observations:
            original_by_scope[claim["platform"]].add(claim["source_record_ordinal"])
    original_registers = read_json(root / "sources/libretro-no-intro.json")
    extended_register = pinned_manifest(root)
    declared_scopes = {
        entry["platform"] for entry in original_registers["files"]
    } | {
        entry["platform"] for entry in extended_register["platforms"]
    }
    if len(declared_scopes) != 75 or set(original_by_scope) - declared_scopes:
        raise ValueError("registered Libretro inventory is incomplete")
    for platform in declared_scopes:
        original_by_scope[platform]  # Empty original DAT sources remain explicit.
    mame_by_source = {
        item["source_list_name"]: item
        for item in [
            *mame_summary["partitions"],
            *mame_summary_v2["partitions"],
        ]
    }
    if len(mame_by_source) != 65:
        raise ValueError("repeated or incomplete independent MAME source scope")
    links_count = 0
    matched_mame = defaultdict(set)
    matched_libretro = defaultdict(set)
    candidate_mame = Counter()
    candidate_libretro = Counter()
    for raw_row in raw.splitlines():
        link = json.loads(raw_row)
        if (
            link["schema_version"] != 1
            or link["kind"] != "exact-mame-libretro-media-sha1-source-candidate"
            or link["interpretation"] !=
            "review-only-identical-media-sha1-not-verified-game-release-or-platform-identity"
            or not link["size_corroborated"]
            or link["mame"]["source_size_bytes"] != link["libretro"]["media_size_bytes"]
        ):
            raise ValueError("source link contains unsupported identity inference")
        original_list = link["mame"]["source_list"]
        original_ordinal = link["mame"]["software_ordinal"]
        libretro_scope = link["libretro"]["platform"]
        libretro_ordinal = link["libretro"]["source_record_ordinal"]
        if (
            original_list not in mame_by_source
            or not 1 <= original_ordinal <= mame_by_source[original_list]["source_software_entries"]
            or libretro_ordinal not in original_by_scope[libretro_scope]
        ):
            raise ValueError("source link refers to an unknown original observation")
        matched_mame[original_list].add(original_ordinal)
        matched_libretro[libretro_scope].add(libretro_ordinal)
        candidate_mame[original_list] += 1
        candidate_libretro[libretro_scope] += 1
        links_count += 1
    if (
        links_count != match_summary["exact_sha1_source_candidate_pairs"]
        or sum(len(s) for s in matched_mame.values()) !=
        match_summary["distinct_matched_mame_software_records"]
        or sum(len(s) for s in matched_libretro.values()) !=
        match_summary["distinct_matched_libretro_records"]
    ):
        raise ValueError("source-matched record counts diverge from pinned exact SHA-1 report")
    mame = [
        {
            "source_list": name,
            "original_software_records": row["source_software_entries"],
            "records_with_exact_media_sha1_overlap": len(matched_mame[name]),
            "records_without_exact_media_sha1_overlap": (
                row["source_software_entries"] - len(matched_mame[name])
            ),
            "original_cross_source_candidate_pairs": candidate_mame[name],
            "original_source_sha256": row["source_sha256"],
        }
        for name, row in sorted(mame_by_source.items())
    ]
    libretro = [
        {
            "source_platform": name,
            "original_dat_records": len(original_by_scope[name]),
            "records_with_exact_media_sha1_overlap": len(matched_libretro[name]),
            "records_without_exact_media_sha1_overlap": (
                len(original_by_scope[name]) - len(matched_libretro[name])
            ),
            "original_cross_source_candidate_pairs": candidate_libretro[name],
        }
        for name in sorted(original_by_scope)
    ]
    mame_totals = {
        "original_software_records": sum(row["original_software_records"] for row in mame),
        "records_with_exact_media_sha1_overlap": sum(
            row["records_with_exact_media_sha1_overlap"] for row in mame
        ),
        "records_without_exact_media_sha1_overlap": sum(
            row["records_without_exact_media_sha1_overlap"] for row in mame
        ),
    }
    libretro_total = {
        "original_dat_records": sum(row["original_dat_records"] for row in libretro),
        "records_with_exact_media_sha1_overlap": sum(
            row["records_with_exact_media_sha1_overlap"] for row in libretro
        ),
        "records_without_exact_media_sha1_overlap": sum(
            row["records_without_exact_media_sha1_overlap"] for row in libretro
        ),
    }
    if (
        mame_totals["original_software_records"] != 32953
        or libretro_total["original_dat_records"] != libretro_totals["libretro_source_records"]
    ):
        raise ValueError("original source inventory changed")
    return {
        "schema_version": 1,
        "kind": "source-only-mame-libretro-exact-sha1-gap-analysis",
        "source_media_report": str(SOURCE_REPORT),
        "source_media_sha256": match_summary["match_index_sha256"],
        "mame_source_lists": len(mame),
        "libretro_source_collections": len(libretro),
        "exact_media_sha1_candidate_pairs": links_count,
        "mame_source_observation_totals": mame_totals,
        "libretro_source_observation_totals": libretro_total,
        "mame_lists_with_no_media_overlap": [
            row["source_list"] for row in mame
            if not row["records_with_exact_media_sha1_overlap"]
        ],
        "libretro_scopes_with_no_media_overlap": [
            row["source_platform"] for row in libretro
            if not row["records_with_exact_media_sha1_overlap"]
        ],
        "mame_source_lists": mame,
        "libretro_source_scopes": libretro,
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
    elif target.is_symlink() or not target.exists() or target.read_text(encoding="utf-8") != text:
        parser.error("pinned SHA-1 source-coverage report is missing or stale")
    print(f"verified pinned {OUTPUT}")


if __name__ == "__main__":
    main()
