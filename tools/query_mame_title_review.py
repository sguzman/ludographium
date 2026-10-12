#!/usr/bin/env python3
"""Read-only search for conservatively grounded, ambiguous title-review leads."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from reconcile_mame_titles import normalized_title

ROOT = Path(__file__).resolve().parents[1]
INDEX = Path("data/reconciliation/mame-libretro-title-review-v1/candidates.jsonl")
SUMMARY = Path("reports/mame-libretro-title-review-v1-summary.json")


def query(root=ROOT, *, mame_list=None, libretro_platform=None, title=None,
          min_scope_support=3, ambiguous_only=False, limit=20):
    if not 1 <= limit <= 200:
        raise ValueError("review query limit must be 1 through 200")
    if not 3 <= min_scope_support <= 1000000:
        raise ValueError("evidence threshold outside supported range")
    for value in (mame_list, libretro_platform, title):
        if value is not None and (not value.strip() or len(value) > 250):
            raise ValueError("blank or unbounded original-source text filter")
    report_path, index_path = root / SUMMARY, root / INDEX
    if report_path.is_symlink() or index_path.is_symlink():
        raise ValueError("untrusted symlink in title review evidence")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw = index_path.read_bytes()
    if (
        report["schema_version"] != 1
        or report["kind"] != "conservative-sha1-grounded-exact-title-review"
        or report["source_scope_pairs_eligible_for_title_review"] > report["source_scope_pairs_with_media_support"]
        or report["minimum_distinct_mame_media_supported_scope_records"] != 3
        or report["candidate_path"] != str(INDEX)
        or report["candidate_sha256"] != hashlib.sha256(raw).hexdigest()
        or report["candidate_bytes"] != len(raw)
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError("altered or unregistered title-review evidence")
    eligible_scopes = {
        (item["mame_source_list"], item["libretro_source_platform"]):
        item["distinct_mame_software_records_with_exact_media_evidence"]
        for item in report["source_scope_correspondence_evidence"]
        if item["eligible_for_title_review"]
    }
    if len(eligible_scopes) != report["source_scope_pairs_eligible_for_title_review"]:
        raise ValueError("duplicate or absent supported source scopes")
    groups = Counter()
    unique_pairs = set()
    accepted_rows = []
    for ordinal, line in enumerate(raw.splitlines(), 1):
        row = json.loads(line)
        mame, libretro = row["mame"], row["libretro"]
        scope_key = (mame["source_list"], libretro["platform"])
        pair_key = (
            mame["source_list"], mame["software_ordinal"],
            libretro["platform"], libretro["source_ordinal"],
        )
        if (
            row["schema_version"] != 1
            or row["kind"] != "review-only-exact-source-title-correspondence"
            or row["interpretation"] != (
                "review-only-equal-normalized-titles-with-scope-corroboration-"
                "not-verified-game-or-release-identity"
            )
            or eligible_scopes.get(scope_key) is None
            or eligible_scopes[scope_key] < 3
            or row["source_scope_pair_sha1_supported_mame_records"] != (
                eligible_scopes[scope_key]
            )
            or type(mame["software_ordinal"]) is not int
            or type(libretro["source_ordinal"]) is not int
            or mame["software_ordinal"] <= 0
            or libretro["source_ordinal"] <= 0
            or not re.fullmatch("[a-f0-9]{64}", mame["original_source_xml_sha256"])
            or not re.fullmatch("[a-f0-9]{40}", libretro["original_git_blob_sha"])
            or normalized_title(mame["original_title"]) != row["normalized_title_key"]
            or normalized_title(libretro["original_title"]) != row["normalized_title_key"]
            or pair_key in unique_pairs
        ):
            raise ValueError(
                f"title-review lead {ordinal} violates pinned source evidence"
            )
        unique_pairs.add(pair_key)
        group_key = (mame["source_list"], mame["software_ordinal"])
        groups[group_key] += 1
        accepted_rows.append(row)
    if (
        len(accepted_rows) != report["total_review_only_exact_title_candidates"]
        or len(groups) != report["distinct_mame_software_with_title_candidate"]
    ):
        raise ValueError("title-review source observation inventory is incomplete")
    filtered = []
    matches = 0
    for row in accepted_rows:
        mame, libretro = row["mame"], row["libretro"]
        count = groups[(mame["source_list"], mame["software_ordinal"])]
        if mame_list and mame["source_list"] != mame_list:
            continue
        if libretro_platform and libretro["platform"] != libretro_platform:
            continue
        if title and (
            title.casefold() not in mame["original_title"].casefold()
            and title.casefold() not in libretro["original_title"].casefold()
        ):
            continue
        if row["source_scope_pair_sha1_supported_mame_records"] < min_scope_support:
            continue
        if ambiguous_only and count <= 1:
            continue
        matches += 1
        if len(filtered) < limit:
            filtered.append({
                **row,
                "source_review_alternatives_for_same_mame_record": count,
                "is_ambiguous_among_source_review_candidates": count > 1,
            })
    return {
        "source_mode": "pinned-conservative-exact-title-cross-source-review",
        "original_source_candidate_pairs": len(accepted_rows),
        "distinct_original_mame_records_with_candidates": len(groups),
        "total_filtered_candidate_pairs": matches,
        "returned_candidate_pairs": len(filtered),
        "source_index_sha256": report["candidate_sha256"],
        "minimum_original_media_supported_scope_records": (
            report["minimum_distinct_mame_media_supported_scope_records"]
        ),
        "eligible_source_scope_pairs": len(eligible_scopes),
        "pairs": filtered,
        "interpretation": (
            "Each pair is an unadjudicated exact-title lead grounded in "
            "prior media-supported source scopes; even a unique candidate "
            "is not a verified game, release, translation or platform identity."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mame-list")
    parser.add_argument("--platform", help="original Libretro source collection")
    parser.add_argument("--title")
    parser.add_argument("--min-scope-support", type=int, default=3)
    parser.add_argument("--ambiguous-only", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = query(
        ROOT, mame_list=args.mame_list,
        libretro_platform=args.platform, title=args.title,
        min_scope_support=args.min_scope_support,
        ambiguous_only=args.ambiguous_only, limit=args.limit,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
