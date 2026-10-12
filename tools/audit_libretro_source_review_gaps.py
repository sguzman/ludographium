#!/usr/bin/env python3
"""Audit Libretro original DAT records with and without cross-provider review leads.

This is a source-corpus coverage diagnostic, not an estimate of missing games.
Records are checked against their original Git-blob-pinned DAT, and MAME title
or media evidence remains an unadjudicated alternative, never an identity join.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from acquire_mame_softlists import ROOT
from build_mame_catalog_sqlite import libretro_original_scopes, source_bytes
from import_dat import import_dat
from query_source_review_units import validate as validate_review_units
from query_mame_media import REPORT as MEDIA_REPORT

OUTPUT = Path("reports/libretro-source-review-acquisition-gaps-v1.json")
SUMMARY = Path("reports/source-review-units-v1-summary.json")
INTERPRETATION = (
    "Each count represents independently pinned Libretro DAT source records. "
    "A current cross-provider review lead is evidence only, not a verified "
    "same-game, same-platform, same-release, same-media or regional identity. "
    "Unlinked original source records are NOT missing games or proof of source "
    "incompleteness; they identify candidates for broader independent "
    "provider acquisition."
)
STATUSES = ("media-only", "title-only", "both-media-and-title", "no-review-lead")


def evidence_status(media, title):
    if media and title:
        return "both-media-and-title"
    if media:
        return "media-only"
    if title:
        return "title-only"
    return "no-review-lead"


def load_source_json(root, path):
    return json.loads(source_bytes(root, path))


def build_report(root=ROOT):
    manifest, review_units, _ = validate_review_units(root)
    media_report = load_source_json(root, MEDIA_REPORT)
    if (
        manifest["source_review_units"] != 21712
        or media_report["exact_sha1_source_candidate_pairs"] != 19025
        or media_report["distinct_matched_libretro_records"] != 18856
    ):
        raise ValueError("original cross-provider review inventory changed")
    target_flags = defaultdict(lambda: {"media": False, "title": False})
    target_snapshots = {}
    target_titles = {}
    candidate_target_references = Counter()
    ambiguous_target_references = Counter()
    for unit in review_units:
        if unit["review_status"] != "unreviewed-original-evidence":
            raise ValueError("a review task was silently marked accepted")
        for target in unit["candidate_libretro_targets"]:
            platform, ordinal = target["platform"], target["original_source_ordinal"]
            key = (platform, ordinal)
            if (
                not target["has_equal_sha1_and_size_evidence"]
                and not target["has_exact_normalized_title_review_evidence"]
            ):
                raise ValueError(f"empty Libretro original source evidence: {key}")
            if key in target_snapshots and (
                target_snapshots[key] != target["original_git_blob_sha"]
                or target_titles[key] != target["original_title"]
            ):
                raise ValueError(f"original Libretro source title changed: {key}")
            target_snapshots[key] = target["original_git_blob_sha"]
            target_titles[key] = target["original_title"]
            target_flags[key]["media"] |= target["has_equal_sha1_and_size_evidence"]
            target_flags[key]["title"] |= target["has_exact_normalized_title_review_evidence"]
            candidate_target_references[key] += 1
            if unit["multiple_source_target_alternatives"]:
                ambiguous_target_references[key] += 1

    grouped = []
    source_count = 0
    scope_ids = set()
    media_record_keys = set()
    seen_records = set()
    for entry, register, relative in libretro_original_scopes(root):
        platform = entry["platform"]
        if platform in scope_ids:
            raise ValueError(f"duplicate original Libretro scope: {platform}")
        scope_ids.add(platform)
        parsed = import_dat(source_bytes(root, relative), register, platform)
        if (
            parsed["source_license"] != "CC-BY-SA-4.0"
            or parsed["record_count"] != len(parsed["records"])
            or parsed["source_blob_sha"] != entry["git_blob_sha"]
            or (entry.get("bytes") is not None
                and len(source_bytes(root, relative)) != entry["bytes"])
        ):
            raise ValueError(f"original Libretro DAT source changed: {platform}")
        stats = Counter()
        for record in parsed["records"]:
            key = (platform, record["source_ordinal"])
            if key in seen_records:
                raise ValueError(f"duplicate source record ordinal: {key}")
            seen_records.add(key)
            if key in target_snapshots:
                if (
                    target_snapshots[key] != parsed["source_blob_sha"]
                    or target_titles[key] != record["name"]
                ):
                    raise ValueError(f"review evidence differs from pinned DAT: {key}")
            flags = target_flags.get(key, {"media": False, "title": False})
            status = evidence_status(flags["media"], flags["title"])
            stats[status] += 1
            stats["original_dat_records"] += 1
            if flags["media"]:
                media_record_keys.add(key)
            if key in ambiguous_target_references:
                stats["records_with_ambiguous_mame_source_review"] += 1
            if candidate_target_references[key] > 1:
                stats["records_referenced_by_multiple_mame_review_units"] += 1
        if stats["original_dat_records"] != parsed["record_count"]:
            raise ValueError(f"incomplete original source collection: {platform}")
        source_count += stats["original_dat_records"]
        grouped.append({
            "source_platform": platform,
            "source_dat_path": str(relative),
            "original_git_blob_sha": parsed["source_blob_sha"],
            "source_license": parsed["source_license"],
            "original_dat_version": parsed["dat_version"],
            "original_dat_records": stats["original_dat_records"],
            "records_with_exact_media_only_leads": stats["media-only"],
            "records_with_conservative_title_only_leads": stats["title-only"],
            "records_with_both_media_and_title_leads": stats["both-media-and-title"],
            "records_with_no_cross_provider_review_lead": stats["no-review-lead"],
            "records_with_ambiguous_mame_source_review":
                stats["records_with_ambiguous_mame_source_review"],
            "records_referenced_by_multiple_mame_review_units":
                stats["records_referenced_by_multiple_mame_review_units"],
        })
    if set(target_snapshots) - seen_records:
        raise ValueError("review queue refers to nonexistent Libretro source records")
    if len(media_record_keys) != media_report["distinct_matched_libretro_records"]:
        raise ValueError("cross-source SHA-1 review coverage changed")
    if len(scope_ids) != 75 or source_count != 117145:
        raise ValueError("incomplete original 75-scope Libretro inventory")
    totals = {
        "original_dat_records": source_count,
        "exact_media_only_source_records": sum(
            item["records_with_exact_media_only_leads"] for item in grouped
        ),
        "conservative_title_only_source_records": sum(
            item["records_with_conservative_title_only_leads"] for item in grouped
        ),
        "records_with_both_media_and_title_leads": sum(
            item["records_with_both_media_and_title_leads"] for item in grouped
        ),
        "original_records_without_any_review_lead": sum(
            item["records_with_no_cross_provider_review_lead"] for item in grouped
        ),
        "original_records_with_any_review_lead": len(target_snapshots),
    }
    if (
        sum(totals[key] for key in (
            "exact_media_only_source_records",
            "conservative_title_only_source_records",
            "records_with_both_media_and_title_leads",
            "original_records_without_any_review_lead"
        )) != source_count
        or (totals["exact_media_only_source_records"]
            + totals["records_with_both_media_and_title_leads"]
            != media_report["distinct_matched_libretro_records"])
        or (totals["original_records_with_any_review_lead"]
            + totals["original_records_without_any_review_lead"] != source_count)
    ):
        raise ValueError("original Libretro evidence statuses overlap or are incomplete")
    ranked = sorted(
        grouped,
        key=lambda x: (-x["records_with_no_cross_provider_review_lead"],
                       x["source_platform"]),
    )
    return {
        "schema_version": 1,
        "kind": "pinned-libretro-source-record-review-acquisition-backlog",
        "original_review_units_manifest": str(SUMMARY),
        "original_review_units_sha256": manifest["review_index_sha256"],
        "original_media_evidence_sha256": media_report["match_index_sha256"],
        "libretro_source_collections": len(grouped),
        "mame_source_lists": 65,
        "original_source_record_totals": totals,
        "libretro_platforms_with_no_source_review_evidence": [
            item["source_platform"] for item in ranked
            if item["original_dat_records"]
            and item["records_with_no_cross_provider_review_lead"]
            == item["original_dat_records"]
        ],
        "libretro_collections_ranked_by_no_review_evidence": ranked,
        "interpretation": INTERPRETATION,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    path = ROOT / OUTPUT
    if args.write:
        path.write_text(value, encoding="utf-8")
    elif path.is_symlink() or not path.exists() or path.read_text(encoding="utf-8") != value:
        parser.error("missing or stale original Libretro review-gap report")
    result = json.loads(value)
    print(
        f"verified {result['libretro_source_collections']} independently pinned "
        f"Libretro collections; "
        f"{result['original_source_record_totals']['original_records_without_any_review_lead']} "
        "original records without a cross-source review lead"
    )


if __name__ == "__main__":
    main()
