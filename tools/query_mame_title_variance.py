#!/usr/bin/env python3
"""Read-only search for display-name differences on equal-media SHA-1 evidence.

Source SHA-256, original one-based evidence row and separate provider titles
are retained. Results do not establish errors, identities or release joins.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from audit_mame_title_variance import (
    ROOT, OUTPUT, REPORT, classification, build_expected,
)

KINDS = (
    "one-title-contained-in-another",
    "different-normalized-titles",
    "missing-source-title",
)


def query(root=ROOT, *, mame_list=None, libretro_platform=None, title=None,
          media_sha1=None, variance_class=None, source_row=None, limit=20):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("variance query limit must be 1 through 200")
    if variance_class is not None and variance_class not in KINDS:
        raise ValueError("unrecognized original-source display-name variance class")
    if source_row is not None and (
        type(source_row) is not int or source_row <= 0 or source_row > 19025
    ):
        raise ValueError("source media-evidence row is outside the pinned corpus")
    for value in (mame_list, libretro_platform, title):
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 250
        ):
            raise ValueError("source variance filters must be bounded and nonblank")
    if media_sha1 is not None and (
        not isinstance(media_sha1, str)
        or re.fullmatch(r"[0-9a-fA-F]{40}", media_sha1) is None
    ):
        raise ValueError("media SHA-1 must contain exactly forty hex digits")
    path, report_path = root / OUTPUT, root / REPORT
    if path.is_symlink() or report_path.is_symlink():
        raise ValueError("symlinked original source variance evidence")
    # Reproduce the entire projection from separately SHA-pinned media input.
    # This includes original title comparisons and source row coordinates.
    expected_raw, expected_report = build_expected(root)
    observed_raw = path.read_bytes()
    observed_summary = report_path.read_bytes()
    if observed_raw != expected_raw or observed_summary != expected_report.encode("utf-8"):
        raise ValueError("source variance evidence cannot be reproduced from pinned input")
    report = json.loads(expected_report)
    filtered, total = [], 0
    for line in observed_raw.splitlines():
        row = json.loads(line)
        mame, libretro = row["mame"], row["libretro"]
        if (
            row["schema_version"] != 1
            or row["kind"] != "source-name-variance-on-equal-sha1-media-claims"
            or row["variance_class"] not in KINDS
            or row["variance_class"] != classification(
                mame["original_title"], libretro["original_title"]
            )
            or not row["interpretation"].startswith("review-only-")
        ):
            raise ValueError("malformed name-variance evidence cannot be searched")
        if mame_list is not None and mame["source_list"] != mame_list:
            continue
        if libretro_platform is not None and libretro["platform"] != libretro_platform:
            continue
        if title is not None and not (
            title.casefold() in (mame["original_title"] or "").casefold()
            or title.casefold() in (libretro["original_title"] or "").casefold()
        ):
            continue
        if media_sha1 is not None and row["source_media_sha1"] != media_sha1.lower():
            continue
        if variance_class is not None and row["variance_class"] != variance_class:
            continue
        if source_row is not None and row["source_media_evidence_row"] != source_row:
            continue
        total += 1
        if len(filtered) < limit:
            filtered.append(row)
    return {
        "source_mode": "attributed-media-sha1-source-title-variance-review",
        "original_media_evidence_rows": report["input_media_sha1_evidence_rows"],
        "total_original_name_variances": report["display_name_variance_rows"],
        "total_filtered_name_variances": total,
        "returned_name_variances": len(filtered),
        "original_media_evidence_sha256": report["input_media_sha1_index_sha256"],
        "title_variance_index_sha256": hashlib.sha256(observed_raw).hexdigest(),
        "records": filtered,
        "interpretation": (
            "Source-literal name differences only. Matching media hashes and "
            "different titles do not prove or disprove a game/release identity."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mame-list")
    parser.add_argument("--platform", help="Libretro original source collection")
    parser.add_argument("--title")
    parser.add_argument("--sha1")
    parser.add_argument("--class", dest="variance_class", choices=KINDS)
    parser.add_argument("--source-row", type=int)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = query(
        ROOT, mame_list=args.mame_list, libretro_platform=args.platform,
        title=args.title, media_sha1=args.sha1,
        variance_class=args.variance_class, source_row=args.source_row,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
