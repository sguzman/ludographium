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
V3_INDEX = Path("data/reconciliation/mame-libretro-title-review-v3/candidates.jsonl")
V3_SUMMARY = Path("reports/mame-libretro-title-review-v3-summary.json")


def query_v3(root=ROOT, *, mame_list=None, libretro_platform=None,
             title=None, min_scope_support=3, ambiguous_only=False, limit=20,
             offset=0):
    """The four additional original MAME source lists have a separate index."""
    report_path, index_path = root / V3_SUMMARY, root / V3_INDEX
    if (
        report_path.is_symlink() or index_path.is_symlink()
        or not report_path.is_file() or not index_path.is_file()
    ):
        raise ValueError("third-cohort source title review files are missing or linked")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw = index_path.read_bytes()
    if (
        report["schema_version"] != 1
        or report["kind"] != "additive-third-mame-cohort-title-review"
        or report["original_mame_source_register"] != "sources/mame-softlists-v3.json"
        or report["original_mame_source_lists"] != 4
        or report["original_software_observations"] != 166
        or report["original_software_with_sha1_source_leads"] != 127
        or report["original_software_without_sha1_source_leads"] != 39
        or report["minimum_distinct_mame_sha1_scope_support"] != 3
        or report["candidate_path"] != str(V3_INDEX)
        or report["candidate_sha256"] != hashlib.sha256(raw).hexdigest()
        or report["candidate_bytes"] != len(raw)
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError("third-cohort pinned title-review evidence changed")
    supported = {
        (item["mame_source_list"], item["libretro_original_scope"]):
        item["distinct_mame_source_records_with_prior_sha1_evidence"]
        for item in report["source_scope_support"]
        if item["eligible_for_title_review"]
    }
    if len(supported) != report["eligible_source_scope_pairs"]:
        raise ValueError("unregistered or repeated third-cohort source-scope pair")
    records, alternatives, seen = [], Counter(), set()
    for line, raw_row in enumerate(raw.splitlines(), 1):
        row = json.loads(raw_row)
        mame, libretro = row["mame"], row["libretro"]
        scope = (mame["source_list"], libretro["platform"])
        key = (
            mame["source_list"], mame["original_software_ordinal"],
            libretro["platform"], libretro["original_source_ordinal"],
        )
        if (
            row["schema_version"] != 1
            or row["kind"] != "third-mame-cohort-review-only-exact-title-evidence"
            or row["interpretation"] != (
                "review-only-name-equality-in-media-supported-source-scope-"
                "not-a-verified-game-or-release-identity"
            )
            or mame["source_cohort"] != "v3"
            or supported.get(scope) is None
            or supported[scope] < 3
            or row["scope_pair_distinct_mame_sha1_supported_records"] != supported[scope]
            or type(mame["original_software_ordinal"]) is not int
            or type(libretro["original_source_ordinal"]) is not int
            or min(mame["original_software_ordinal"], libretro["original_source_ordinal"]) <= 0
            or not re.fullmatch("[a-f0-9]{64}", mame["source_xml_sha256"])
            or not re.fullmatch("[a-f0-9]{40}", libretro["original_git_blob_sha"])
            or normalized_title(mame["original_title"]) != row["normalized_title_key"]
            or normalized_title(libretro["original_title"]) != row["normalized_title_key"]
            or key in seen
        ):
            raise ValueError(f"third-cohort review lead {line} failed source verification")
        seen.add(key)
        records.append(row)
        alternatives[(mame["source_list"], mame["original_software_ordinal"])] += 1
    if (
        len(records) != report["original_title_review_candidate_pairs"]
        or len(alternatives) != report["distinct_original_mame_software_with_title_leads"]
    ):
        raise ValueError("truncated third-cohort review evidence")
    matches, results = 0, []
    for row in records:
        mame, libretro = row["mame"], row["libretro"]
        group = alternatives[(mame["source_list"], mame["original_software_ordinal"])]
        if (
            (mame_list and mame_list != mame["source_list"])
            or (libretro_platform and libretro_platform != libretro["platform"])
            or (title and title.casefold() not in mame["original_title"].casefold()
                and title.casefold() not in libretro["original_title"].casefold())
            or row["scope_pair_distinct_mame_sha1_supported_records"] < min_scope_support
            or (ambiguous_only and group <= 1)
        ):
            continue
        matches += 1
        if matches > offset and len(results) < limit:
            results.append({
                **row,
                "source_evidence_cohort": "v3",
                "source_review_alternatives_for_same_mame_record": group,
                "is_ambiguous_among_source_review_candidates": group > 1,
            })
    return {
        "source_mode": "third-mame-cohort-original-exact-title-review-only",
        "original_source_candidate_pairs": len(records),
        "distinct_original_mame_records_with_candidates": len(alternatives),
        "total_filtered_candidate_pairs": matches,
        "returned_candidate_pairs": len(results),
        "offset": offset,
        "next_offset": (
            offset + len(results) if offset + len(results) < matches else None
        ),
        "source_index_sha256": report["candidate_sha256"],
        "pairs": results,
        "interpretation": (
            "Separately verified original third-cohort exact-title leads; even "
            "a single source name match is not a verified game, release, "
            "translation or platform identity."
        ),
    }


def query(root=ROOT, *, mame_list=None, libretro_platform=None, title=None,
          min_scope_support=3, ambiguous_only=False, limit=20,
          cohort="baseline", offset=0):
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("title review offset must be 0..1000000")
    if not 1 <= limit <= 200:
        raise ValueError("review query limit must be 1 through 200")
    if not 3 <= min_scope_support <= 1000000:
        raise ValueError("evidence threshold outside supported range")
    for value in (mame_list, libretro_platform, title):
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 250
        ):
            raise ValueError("blank or unbounded original-source text filter")
    if cohort not in ("baseline", "v3", "combined"):
        raise ValueError("unsupported independent title-review cohort")
    if cohort != "baseline":
        selected = dict(
            mame_list=mame_list, libretro_platform=libretro_platform,
            title=title, min_scope_support=min_scope_support,
            ambiguous_only=ambiguous_only, limit=limit,
        )
        if cohort == "v3":
            return query_v3(root, **selected, offset=offset)
        first = query(root, **selected, cohort="baseline", offset=offset)
        # Count matches before paging, then advance into the independent
        # third cohort only after the baseline filtered results are exhausted.
        v3_offset = max(0, offset - first["total_filtered_candidate_pairs"])
        extra = query_v3(root, **selected, offset=v3_offset)
        merged = [
            {**item, "source_evidence_cohort": "baseline"}
            for item in first["pairs"]
        ] + extra["pairs"]
        pairs = merged[:limit]
        total_filtered = (
            first["total_filtered_candidate_pairs"]
            + extra["total_filtered_candidate_pairs"]
        )
        return {
            "source_mode": "independently-pinned-mame-cross-cohort-title-review",
            "source_cohorts": ["baseline", "v3"],
            "original_source_candidate_pairs": (
                first["original_source_candidate_pairs"]
                + extra["original_source_candidate_pairs"]
            ),
            "distinct_original_mame_records_with_candidates": (
                first["distinct_original_mame_records_with_candidates"]
                + extra["distinct_original_mame_records_with_candidates"]
            ),
            "total_filtered_candidate_pairs": total_filtered,
            "returned_candidate_pairs": len(pairs),
            "offset": offset,
            "next_offset": (
                offset + len(pairs)
                if offset + len(pairs) < total_filtered else None
            ),
            "source_index_sha256": {
                "baseline": first["source_index_sha256"],
                "v3": extra["source_index_sha256"],
            },
            "pairs": pairs,
            "interpretation": (
                "Independent noncanonical original source title leads from "
                "separate 65-list and 4-list cohorts; no accepted game or release."
            ),
        }
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
        if matches > offset and len(filtered) < limit:
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
        "offset": offset,
        "next_offset": (
            offset + len(filtered) if offset + len(filtered) < matches else None
        ),
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
    parser.add_argument("--cohort", choices=("baseline", "v3", "combined"),
                        default="baseline")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0,
                        help="filtered title-review pairs to skip")
    args = parser.parse_args()
    result = query(
        ROOT, mame_list=args.mame_list,
        libretro_platform=args.platform, title=args.title,
        min_scope_support=args.min_scope_support,
        ambiguous_only=args.ambiguous_only, limit=args.limit,
        cohort=args.cohort, offset=args.offset,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
