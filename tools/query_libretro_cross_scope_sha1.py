#!/usr/bin/env python3
"""Read-only query for original cross-scope Libretro SHA-1 source evidence."""
import argparse
import hashlib
import json
import re

from audit_libretro_cross_scope_sha1 import (
    ROOT, INDEX, REPORT, build_expected, normalized_group,
)


def query(root=ROOT, *, platform=None, sha1=None, title=None,
          conflicting_sizes_only=False, minimum_scopes=2, limit=20):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("source evidence query limit must be 1..200")
    if type(minimum_scopes) is not int or not 2 <= minimum_scopes <= 75:
        raise ValueError("minimum independent DAT scopes must be 2..75")
    for value in (platform, title):
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 250
        ):
            raise ValueError("original DAT source filters must be bounded and nonblank")
    if sha1 is not None and (
        not isinstance(sha1, str)
        or re.fullmatch(r"[0-9a-fA-F]{40}", sha1) is None
    ):
        raise ValueError("source SHA-1 must be forty hex digits")
    evidence, report_text = build_expected(root)
    path = root / INDEX
    report_path = root / REPORT
    if (
        not path.is_file() or path.is_symlink() or path.read_bytes() != evidence
        or not report_path.is_file() or report_path.is_symlink()
        or report_path.read_text(encoding="utf-8") != report_text
    ):
        raise ValueError("cross-scope source evidence has changed from pinned originals")
    summary = json.loads(report_text)
    candidates = []
    total = 0
    for line in evidence.splitlines():
        row = json.loads(line)
        if (
            row["schema_version"] != 1
            or row["kind"] != "unresolved-cross-scope-exact-media-sha1-observation"
            or row["source_license"] != "CC-BY-SA-4.0"
            or row["distinct_source_scope_count"] < 2
            or not row["interpretation"].endswith("no-canonical-game-or-platform-identity")
            or row != normalized_group(
                row["original_media_sha1"], row["independent_source_media_claims"]
            )
        ):
            raise ValueError("cross-scope source observation is not reproducible")
        if platform and platform not in row["distinct_source_scopes"]:
            continue
        if sha1 and row["original_media_sha1"] != sha1.lower():
            continue
        if title and not any(
            title.casefold() in claim["source_title"].casefold()
            for claim in row["independent_source_media_claims"]
        ):
            continue
        if conflicting_sizes_only and not row["declared_size_disagreement"]:
            continue
        if row["distinct_source_scope_count"] < minimum_scopes:
            continue
        total += 1
        if len(candidates) < limit:
            candidates.append(row)
    return {
        "source_mode": "original-libretro-cross-scope-media-sha1-evidence",
        "source_licenses": ["CC-BY-SA-4.0"],
        "independent_source_collections": summary["independent_libretro_dat_scopes"],
        "total_cross_scope_fingerprint_groups": summary[
            "sha1_groups_observed_across_independent_scopes"
        ],
        "total_filtered_original_fingerprint_groups": total,
        "returned_fingerprint_groups": len(candidates),
        "original_evidence_sha256": hashlib.sha256(evidence).hexdigest(),
        "groups": candidates,
        "interpretation": (
            "Equal source-reported media SHA1 values across DAT scopes do not "
            "establish accepted games, release identities or platform relationships."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", help="Independent original Libretro DAT scope")
    parser.add_argument("--sha1")
    parser.add_argument("--title")
    parser.add_argument("--conflicting-sizes-only", action="store_true")
    parser.add_argument("--min-scopes", type=int, default=2)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = query(
        ROOT, platform=args.platform, sha1=args.sha1, title=args.title,
        conflicting_sizes_only=args.conflicting_sizes_only,
        minimum_scopes=args.min_scopes, limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
