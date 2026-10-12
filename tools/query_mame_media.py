#!/usr/bin/env python3
"""Search verified exact SHA-1 cross-source media candidates, never game identities."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path("reports/mame-libretro-media-sha1-v1-summary.json")
INDEX = Path("data/reconciliation/mame-libretro-sha1-v1/links.jsonl")
POLICY = "review-only-media-sha1-byte-evidence-not-verified-game-release-platform-identity"


def query(root, *, sha1=None, libretro_platform=None, mame_list=None,
          title=None, limit=20):
    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1..=200")
    if sha1 is not None and not re.fullmatch(r"[a-fA-F0-9]{40}", sha1):
        raise ValueError("SHA-1 requires 40 hex digits")
    if any(text is not None and not text.strip()
           for text in (libretro_platform, mame_list, title)):
        raise ValueError("blank text filter")
    report_path = root / REPORT
    data_path = root / INDEX
    if report_path.is_symlink() or data_path.is_symlink():
        raise ValueError("source evidence index must not be a symlink")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    raw = data_path.read_bytes()
    if (
        report["schema_version"] != 1
        or report["kind"] != "independent-cross-source-media-sha1-exact-match-review"
        or report["mame_software_lists"] != 65
        or report["libretro_source_platforms"] != 75
        or report["match_index_path"] != str(INDEX)
        or report["match_index_sha256"] != hashlib.sha256(raw).hexdigest()
        or report["match_index_bytes"] != len(raw)
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError("original source comparison integrity check failed")
    expected = report["exact_sha1_source_candidate_pairs"]
    needle = sha1.lower() if sha1 else None
    total = 0
    inspected = 0
    results = []
    for line in raw.splitlines():
        record = json.loads(line)
        inspected += 1
        if (
            record["schema_version"] != 1
            or record["kind"] != "exact-mame-libretro-media-sha1-source-candidate"
            or not record["size_corroborated"]
            or record["mame"]["source_size_bytes"] != record["libretro"]["media_size_bytes"]
            or not re.fullmatch(r"[a-f0-9]{40}", record["media_sha1"])
            or not record["interpretation"].startswith("review-only")
        ):
            raise ValueError(f"invalid source media candidate at row {inspected}")
        if needle and record["media_sha1"] != needle:
            continue
        if libretro_platform and record["libretro"]["platform"] != libretro_platform:
            continue
        if mame_list and record["mame"]["source_list"] != mame_list:
            continue
        if title and title.casefold() not in (
            record["mame"]["original_title"] or ""
        ).casefold() and title.casefold() not in (
            record["libretro"]["source_title"] or ""
        ).casefold():
            continue
        total += 1
        if len(results) < limit:
            results.append(record)
    if inspected != expected:
        raise ValueError("original media candidate inventory was truncated")
    return {
        "source_mode": "verified-original-cross-source-media-sha1-candidates",
        "total_original_candidate_pairs": expected,
        "total_filtered_candidate_pairs": total,
        "returned_candidate_pairs": len(results),
        "source_digest_sha256": report["match_index_sha256"],
        "pairs": results,
        "interpretation": POLICY,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha1")
    parser.add_argument("--platform")
    parser.add_argument("--mame-list")
    parser.add_argument("--title")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(query(
        ROOT, sha1=args.sha1, libretro_platform=args.platform,
        mame_list=args.mame_list, title=args.title, limit=args.limit,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
