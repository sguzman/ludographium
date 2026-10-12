#!/usr/bin/env python3
"""Preserve independent fourth-cohort original-source media review tasks.

Every stable ID identifies one MAME original source occurrence. The 70
SHA1-and-byte-size corroborated candidate pairs are review evidence, never
accepted game, work, platform, release or media identities. Older cohorts
retain their original review identifiers and ledgers unchanged.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT
from build_source_review_units import original_review_id, compact
from reconcile_mame_v4_media import (
    INDEX as MEDIA_INDEX, REPORT as MEDIA_REPORT,
    build_expected as rebuild_v4_media,
)

OUTPUT = Path("data/reconciliation/source-review-units-v4/units.jsonl")
REPORT = Path("reports/source-review-units-v4-summary.json")
PRIOR = Path("reports/source-review-units-v3-summary.json")


def build_expected(root=ROOT):
    outputs, summary_text = rebuild_v4_media(root)
    media_raw = outputs[0]
    if (
        (root / MEDIA_INDEX).is_symlink()
        or (root / MEDIA_REPORT).is_symlink()
        or (root / MEDIA_INDEX).read_bytes() != media_raw
        or (root / MEDIA_REPORT).read_text(encoding="utf-8") != summary_text
    ):
        raise ValueError("fourth-cohort review tasks require exact pinned media evidence")
    parent = json.loads((root / PRIOR).read_text(encoding="utf-8"))
    if (
        parent["additional_original_review_units"] != 133
        or parent["cumulative_separate_source_review_units"] != 21845
    ):
        raise ValueError("prior independently pinned review task inventory changed")
    report = json.loads(summary_text)
    if (
        report["source_corroborated_media_candidate_pairs"] != 70
        or report["distinct_mame_software_with_corroborated_media_leads"] != 70
        or report["distinct_libretro_records_with_corroborated_media_leads"] != 70
        or report["corroborated_candidate_sha256"] != hashlib.sha256(media_raw).hexdigest()
    ):
        raise ValueError("fourth-cohort independently corroborated evidence changed")
    grouped = {}
    for line, raw in enumerate(media_raw.splitlines(), 1):
        pair = json.loads(raw)
        mame, libretro = pair["mame"], pair["libretro"]
        source_key = (mame["source_list"], mame["original_software_ordinal"])
        target_key = (libretro["platform"], libretro["original_source_ordinal"])
        if (
            pair["schema_version"] != 1
            or pair["source_cohort"] != "v4"
            or pair["kind"] != "fourth-cohort-corroborated-media-review-candidate"
            or not pair["size_corroborated"]
            or mame["original_declared_size_bytes"] is None
            or mame["original_declared_size_bytes"] != libretro["original_media_size_bytes"]
            or not pair["interpretation"].startswith("review-only-")
        ):
            raise ValueError(f"invalid fourth-cohort corroborated source pair: {line}")
        source = {
            "source_cohort": "v4",
            "source_list": mame["source_list"],
            "original_software_ordinal": mame["original_software_ordinal"],
            "original_title": mame["original_title"],
            "original_xml_sha256": mame["source_xml_sha256"],
            "source_license": "CC0-1.0",
        }
        target = {
            "platform": libretro["platform"],
            "original_source_ordinal": libretro["original_source_ordinal"],
            "original_title": libretro["original_title"],
            "original_git_blob_sha": libretro["original_git_blob_sha"],
            "source_license": "CC-BY-SA-4.0",
            "has_equal_sha1_and_size_evidence": True,
            "has_exact_normalized_title_review_evidence": False,
        }
        group = grouped.setdefault(source_key, {
            "mame": source, "targets": {}, "media_ordinals": []
        })
        if group["mame"] != source or (
            target_key in group["targets"] and group["targets"][target_key] != target
        ):
            raise ValueError("original source review occurrence or target was rewritten")
        group["targets"][target_key] = target
        group["media_ordinals"].append(line)
    units = []
    classes, ambiguity = Counter(), Counter()
    for key, group in sorted(grouped.items()):
        mame = group["mame"]
        targets = [group["targets"][key] for key in sorted(group["targets"])]
        if not targets or not group["media_ordinals"]:
            raise ValueError("a review unit lacks independent original source evidence")
        ambiguous = len(targets) > 1
        category = (
            "multiple-media-supported-source-targets" if ambiguous else
            "single-media-supported-source-target"
        )
        classes[category] += 1
        ambiguity["ambiguous_source_units" if ambiguous else "single_target_source_units"] += 1
        units.append({
            "schema_version": 1,
            "kind": "original-source-review-unit",
            "stable_review_id": original_review_id(
                mame["source_list"], mame["original_xml_sha256"],
                mame["original_software_ordinal"],
            ),
            "mame": mame,
            "candidate_libretro_targets": targets,
            "distinct_candidate_libretro_target_count": len(targets),
            "multiple_source_target_alternatives": ambiguous,
            "media_evidence_jsonl_source_ordinals": group["media_ordinals"],
            "title_evidence_jsonl_source_ordinals": [],
            "source_review_priority_class": category,
            "review_status": "unreviewed-original-evidence",
            "interpretation": "review-task-only-not-accepted-game-or-release-identity",
        })
    ids = [unit["stable_review_id"] for unit in units]
    if (
        len(units) != 70 or len(set(ids)) != 70
        or sum(len(unit["media_evidence_jsonl_source_ordinals"]) for unit in units) != 70
    ):
        raise ValueError("original fourth-cohort source review tasks were omitted or duplicated")
    raw = ("\n".join(compact(item) for item in units) + "\n").encode("utf-8")
    summary = {
        "schema_version": 1,
        "kind": "additive-fourth-mame-cohort-stable-source-review-queue",
        "mame_source_cohort": "v4",
        "prior_original_source_review_report": str(PRIOR),
        "unchanged_prior_source_review_units": 21845,
        "source_media_report": str(MEDIA_REPORT),
        "source_media_index_sha256": report["corroborated_candidate_sha256"],
        "original_media_candidate_pairs": 70,
        "additional_original_review_units": len(units),
        "cumulative_separate_source_review_units": 21845 + len(units),
        "source_review_priority_class_counts": dict(sorted(classes.items())),
        "source_review_ambiguity_counts": dict(sorted(ambiguity.items())),
        "review_index_path": str(OUTPUT),
        "review_index_sha256": hashlib.sha256(raw).hexdigest(),
        "review_index_bytes": len(raw),
        "interpretation": (
            "Independent fourth-cohort SHA1 and declared-size source evidence is "
            "organized as stable source-observation review tasks only. No game, "
            "release, edition, platform, media or cross-provider identity is accepted. "
            "All earlier source review IDs and original evidence remain unchanged."
        ),
    }
    return raw, json.dumps(summary, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw, summary = build_expected()
    path, report = ROOT / OUTPUT, ROOT / REPORT
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        report.write_text(summary, encoding="utf-8")
    elif (
        not path.is_file() or path.is_symlink() or path.read_bytes() != raw
        or not report.is_file() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("fourth-cohort source-only stable review tasks are missing or modified")
    info = json.loads(summary)
    print(
        "verified", info["additional_original_review_units"],
        "fourth-cohort stable original source review tasks"
    )


if __name__ == "__main__":
    main()
