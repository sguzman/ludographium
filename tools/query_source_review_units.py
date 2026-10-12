#!/usr/bin/env python3
"""Query verified, noncanonical, stable-ID original-source review units.

All source observations are pinned by SHA-256. Review IDs identify source
evidence tasks, not games, releases, translations or accepted identities.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from build_source_review_units import (
    ROOT, OUTPUT, SUMMARY, MEDIA_INDEX, MEDIA_REPORT,
    TITLE_INDEX, TITLE_REPORT, original_review_id,
)
from build_source_review_units_v3 import (
    OUTPUT as V3_OUTPUT, REPORT as V3_REPORT,
    MEDIA_INDEX as V3_MEDIA_INDEX, TITLE_INDEX as V3_TITLE_INDEX,
    build_expected as build_v3_review_expected,
)

CLASSES = (
    "multiple-exact-title-source-targets",
    "multiple-media-supported-source-targets",
    "single-exact-title-source-target",
    "single-media-supported-source-target",
)
REVIEW_ID = re.compile(r"lgreview:v1:[0-9a-f]{64}\Z")


def source_bytes(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"linked original review source: {relative}")
    return path.read_bytes()


def read_json(root, relative):
    return json.loads(source_bytes(root, relative))


def checked_evidence(root, report_path, index_path, sha_field, size_field, count_field):
    manifest = read_json(root, report_path)
    raw = source_bytes(root, index_path)
    if (
        manifest["schema_version"] != 1
        or manifest[sha_field] != hashlib.sha256(raw).hexdigest()
        or manifest[size_field] != len(raw)
        or manifest[count_field] != len(raw.splitlines())
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError(f"modified pinned original review evidence: {index_path}")
    return manifest, raw


def validate(root=ROOT):
    manifest, raw = checked_evidence(
        root, SUMMARY, OUTPUT, "review_index_sha256",
        "review_index_bytes", "source_review_units"
    )
    media_manifest, media_raw = checked_evidence(
        root, MEDIA_REPORT, MEDIA_INDEX, "match_index_sha256",
        "match_index_bytes", "exact_sha1_source_candidate_pairs"
    )
    title_manifest, title_raw = checked_evidence(
        root, TITLE_REPORT, TITLE_INDEX, "candidate_sha256",
        "candidate_bytes", "total_review_only_exact_title_candidates"
    )
    if (
        manifest["kind"] != "stable-source-observation-review-unit-queue"
        or manifest["review_index_path"] != str(OUTPUT)
        or manifest["source_media_index_sha256"] != media_manifest["match_index_sha256"]
        or manifest["source_title_index_sha256"] != title_manifest["candidate_sha256"]
        or manifest["media_candidate_rows"] != 19025
        or manifest["title_candidate_rows"] != 6825
        or manifest["source_review_units"] != 21712
    ):
        raise ValueError("unrecognized review-unit source evidence version")
    unit_rows = []
    ids = set()
    seen_mame = set()
    media_ordinals = set()
    title_ordinals = set()
    classes = Counter()
    ambiguity = Counter()
    for source_line, line in enumerate(raw.splitlines(), 1):
        row = json.loads(line)
        mame = row["mame"]
        candidates = row["candidate_libretro_targets"]
        targets = [
            (target["platform"], target["original_source_ordinal"])
            for target in candidates
        ]
        media_rows = row["media_evidence_jsonl_source_ordinals"]
        title_rows = row["title_evidence_jsonl_source_ordinals"]
        stable_id = original_review_id(
            mame["source_list"], mame["original_xml_sha256"],
            mame["original_software_ordinal"]
        )
        if (
            row["schema_version"] != 1
            or row["kind"] != "original-source-review-unit"
            or row["stable_review_id"] != stable_id
            or row["review_status"] != "unreviewed-original-evidence"
            or row["interpretation"] != "review-task-only-not-accepted-game-or-release-identity"
            or mame["source_license"] != "CC0-1.0"
            or len(candidates) == 0
            or len(set(targets)) != len(targets)
            or targets != sorted(targets)
            or any(target["source_license"] != "CC-BY-SA-4.0" for target in candidates)
            or len(candidates) != row["distinct_candidate_libretro_target_count"]
            or (len(candidates) > 1) != row["multiple_source_target_alternatives"]
            or bool(media_rows) == bool(title_rows)
            or not isinstance(media_rows, list)
            or not isinstance(title_rows, list)
            or any(type(n) is not int or n < 1 or n > 19025 for n in media_rows)
            or any(type(n) is not int or n < 1 or n > 6825 for n in title_rows)
        ):
            raise ValueError(f"invalid original source review unit row {source_line}")
        ambiguous = len(targets) > 1
        derived_class = (
            "multiple-media-supported-source-targets" if media_rows and ambiguous
            else "single-media-supported-source-target" if media_rows
            else "multiple-exact-title-source-targets" if ambiguous
            else "single-exact-title-source-target"
        )
        if row["source_review_priority_class"] != derived_class:
            raise ValueError(f"incorrect source-review class: {source_line}")
        if stable_id in ids or (
            mame["source_list"], mame["original_software_ordinal"]
        ) in seen_mame:
            raise ValueError("duplicate stable source review identity")
        ids.add(stable_id)
        seen_mame.add((mame["source_list"], mame["original_software_ordinal"]))
        for n in media_rows:
            if n in media_ordinals:
                raise ValueError("duplicate original media evidence ordinal")
            media_ordinals.add(n)
        for n in title_rows:
            if n in title_ordinals:
                raise ValueError("duplicate original title evidence ordinal")
            title_ordinals.add(n)
        classes[derived_class] += 1
        ambiguity["ambiguous_source_units" if ambiguous else "single_target_source_units"] += 1
        unit_rows.append(row)
    if (
        classes != manifest["source_review_priority_class_counts"]
        or ambiguity != manifest["source_review_ambiguity_counts"]
        or len(media_ordinals) != manifest["media_candidate_rows"]
        or len(title_ordinals) != manifest["title_candidate_rows"]
        or len(media_raw.splitlines()) != len(media_ordinals)
        or len(title_raw.splitlines()) != len(title_ordinals)
    ):
        raise ValueError("source evidence rows were omitted or miscategorized")
    return manifest, unit_rows, (media_raw, title_raw)


def validate_v3(root=ROOT):
    """Re-derive every independent third-cohort unit from original pinned rows."""
    expected_raw, expected_summary = build_v3_review_expected(root)
    pinned_raw = source_bytes(root, V3_OUTPUT)
    pinned_summary = source_bytes(root, V3_REPORT).decode("utf-8")
    if pinned_raw != expected_raw or pinned_summary != expected_summary:
        raise ValueError("additive third-cohort review queue differs from pinned originals")
    report = json.loads(expected_summary)
    if (
        report["schema_version"] != 1
        or report["kind"] != "additive-third-mame-cohort-stable-source-review-queue"
        or report["unchanged_prior_source_review_units"] != 21712
        or report["additional_original_review_units"] != 133
        or report["cumulative_separate_source_review_units"] != 21845
        or report["review_index_path"] != str(V3_OUTPUT)
    ):
        raise ValueError("unsupported additive original source review queue")
    records = [json.loads(line) for line in expected_raw.splitlines()]
    return report, records, (
        source_bytes(root, V3_MEDIA_INDEX),
        source_bytes(root, V3_TITLE_INDEX),
    )


def query(root=ROOT, *, review_id=None, mame_list=None,
          libretro_platform=None, title=None, priority_class=None,
          ambiguous_only=False, evidence_type=None, include_evidence=False,
          limit=20, cohort="baseline"):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("review search limit must be 1..200")
    if review_id is not None and not REVIEW_ID.fullmatch(review_id):
        raise ValueError("review ID is not an original source-stable identifier")
    for value in (mame_list, libretro_platform, title):
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 250
        ):
            raise ValueError("source review text filters must be bounded and nonblank")
    if priority_class is not None and priority_class not in CLASSES:
        raise ValueError("unrecognized source review priority class")
    if evidence_type not in (None, "media", "title"):
        raise ValueError("source evidence type must be media or title")
    if cohort not in ("baseline", "v3", "combined"):
        raise ValueError("unsupported independently pinned review source cohort")
    if cohort == "combined":
        selected = dict(
            review_id=review_id, mame_list=mame_list,
            libretro_platform=libretro_platform, title=title,
            priority_class=priority_class, ambiguous_only=ambiguous_only,
            evidence_type=evidence_type, include_evidence=include_evidence,
            limit=limit,
        )
        older = query(root, **selected, cohort="baseline")
        newer = query(root, **selected, cohort="v3")
        combined = (
            [{**row, "source_evidence_cohort": "baseline"} for row in older["units"]]
            + [{**row, "source_evidence_cohort": "v3"} for row in newer["units"]]
        )[:limit]
        return {
            "source_mode": "separate-original-source-review-cohort-aggregation",
            "source_cohorts": ["baseline", "v3"],
            "total_pinned_source_review_units": (
                older["total_pinned_source_review_units"]
                + newer["total_pinned_source_review_units"]
            ),
            "total_filtered_source_review_units": (
                older["total_filtered_source_review_units"]
                + newer["total_filtered_source_review_units"]
            ),
            "returned_source_review_units": len(combined),
            "review_index_sha256": {
                "baseline": older["review_index_sha256"],
                "v3": newer["review_index_sha256"],
            },
            "units": combined,
            "interpretation": (
                "Independent stable source review tasks, never canonical game, "
                "work, release or cross-provider identities."
            ),
        }
    summary, records, raw_evidence = (
        validate(root) if cohort == "baseline" else validate_v3(root)
    )
    matched, returned = 0, []
    media_lines = title_lines = None
    for row in records:
        mame = row["mame"]
        if review_id and row["stable_review_id"] != review_id:
            continue
        if mame_list and mame["source_list"] != mame_list:
            continue
        if libretro_platform and not any(
            target["platform"] == libretro_platform
            for target in row["candidate_libretro_targets"]
        ):
            continue
        if title and (
            title.casefold() not in mame["original_title"].casefold()
            and not any(
                title.casefold() in target["original_title"].casefold()
                for target in row["candidate_libretro_targets"]
            )
        ):
            continue
        if priority_class and row["source_review_priority_class"] != priority_class:
            continue
        if ambiguous_only and not row["multiple_source_target_alternatives"]:
            continue
        if evidence_type == "media" and not row["media_evidence_jsonl_source_ordinals"]:
            continue
        if evidence_type == "title" and not row["title_evidence_jsonl_source_ordinals"]:
            continue
        matched += 1
        if len(returned) >= limit:
            continue
        projected = dict(row)
        if include_evidence:
            if media_lines is None:
                media_lines = raw_evidence[0].splitlines()
                title_lines = raw_evidence[1].splitlines()
            projected["original_media_evidence"] = [
                json.loads(media_lines[ordinal - 1])
                for ordinal in row["media_evidence_jsonl_source_ordinals"]
            ]
            projected["original_title_evidence"] = [
                json.loads(title_lines[ordinal - 1])
                for ordinal in row["title_evidence_jsonl_source_ordinals"]
            ]
        returned.append(projected)
    return {
        "source_mode": (
            "verified-noncanonical-original-source-review-units"
            if cohort == "baseline" else
            "verified-additive-third-cohort-noncanonical-source-review-units"
        ),
        "total_pinned_source_review_units": (
            summary["source_review_units"] if cohort == "baseline"
            else summary["additional_original_review_units"]
        ),
        "total_filtered_source_review_units": matched,
        "returned_source_review_units": len(returned),
        "review_index_sha256": summary["review_index_sha256"],
        "units": returned,
        "interpretation": (
            "Stable identifiers refer to original source evidence review tasks "
            "only, not accepted games or cross-provider identities."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-id")
    parser.add_argument("--mame-list")
    parser.add_argument("--platform", help="Libretro original source scope")
    parser.add_argument("--title")
    parser.add_argument("--priority-class", choices=CLASSES)
    parser.add_argument("--ambiguous-only", action="store_true")
    parser.add_argument("--evidence-type", choices=["media", "title"])
    parser.add_argument("--include-evidence", action="store_true")
    parser.add_argument("--cohort", choices=("baseline", "v3", "combined"),
                        default="baseline")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = query(
        ROOT, review_id=args.review_id, mame_list=args.mame_list,
        libretro_platform=args.platform, title=args.title,
        priority_class=args.priority_class, ambiguous_only=args.ambiguous_only,
        evidence_type=args.evidence_type, include_evidence=args.include_evidence,
        cohort=args.cohort, limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
