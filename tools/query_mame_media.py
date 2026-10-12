#!/usr/bin/env python3
"""Search distinct pinned SHA-1 media-evidence cohorts without identity joins.

The original 65-MAME-list result format remains the default and unchanged.
Use --cohort v3 or combined for the separately pinned 4-list acquisition.
Every result remains source-only; exact SHA1 and size do not establish a game.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path("reports/mame-libretro-media-sha1-v1-summary.json")
INDEX = Path("data/reconciliation/mame-libretro-sha1-v1/links.jsonl")
V3_REPORT = Path("reports/mame-libretro-sha1-v3-summary.json")
V3_INDEX = Path("data/reconciliation/mame-libretro-sha1-v3/links.jsonl")
POLICY = "review-only-media-sha1-byte-evidence-not-verified-game-release-platform-identity"
SHA1 = re.compile(r"[a-f0-9]{40}\Z")


def verified_rows(root, *, source):
    if source == "baseline":
        report_path, index_path = REPORT, INDEX
    elif source == "v3":
        report_path, index_path = V3_REPORT, V3_INDEX
    else:
        raise ValueError("unsupported independently pinned media source cohort")
    path = root / report_path
    data_path = root / index_path
    if (
        path.is_symlink() or data_path.is_symlink()
        or not path.is_file() or not data_path.is_file()
    ):
        raise ValueError("missing or linked original media-evidence source")
    report = json.loads(path.read_text(encoding="utf-8"))
    raw = data_path.read_bytes()
    if source == "baseline":
        expected = report["exact_sha1_source_candidate_pairs"]
        digest = report["match_index_sha256"]
        byte_count = report["match_index_bytes"]
        manifest_ok = (
            report["schema_version"] == 1
            and report["kind"] == "independent-cross-source-media-sha1-exact-match-review"
            and report["mame_software_lists"] == 65
            and report["libretro_source_platforms"] == 75
            and report["match_index_path"] == str(index_path)
        )
    else:
        expected = report["source_media_sha1_candidate_pairs"]
        digest = report["candidate_sha256"]
        byte_count = report["candidate_bytes"]
        manifest_ok = (
            report["schema_version"] == 1
            and report["kind"] == "separate-third-cohort-exact-original-media-source-candidates"
            and report["mame_source_register"] == "sources/mame-softlists-v3.json"
            and report["mame_original_source_lists"] == 4
            and report["mame_original_software_observations"] == 166
            and report["independent_libretro_dat_collections"] == 75
            and report["candidate_pairs_with_corroborated_size"] == expected
            and report["candidate_path"] == str(index_path)
            and report["mame_source_license"] == "CC0-1.0"
            and report["libretro_source_license"] == "CC-BY-SA-4.0"
        )
    if (
        not manifest_ok
        or digest != hashlib.sha256(raw).hexdigest()
        or byte_count != len(raw)
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError(f"pinned {source} media candidate evidence has changed")
    rows = []
    for ordinal, line in enumerate(raw.splitlines(), 1):
        item = json.loads(line)
        mame, libretro = item["mame"], item["libretro"]
        if source == "baseline":
            valid = (
                item["schema_version"] == 1
                and item["kind"] == "exact-mame-libretro-media-sha1-source-candidate"
                and item["size_corroborated"]
                and mame["source_size_bytes"] == libretro["media_size_bytes"]
                and SHA1.fullmatch(item["media_sha1"]) is not None
                and item["interpretation"].startswith("review-only")
            )
        else:
            valid = (
                item["schema_version"] == 1
                and item["kind"] == "review-only-v3-mame-libretro-exact-media-sha1-candidate"
                and item["size_corroborated"]
                and mame["original_declared_size_bytes"] == (
                    libretro["original_media_size_bytes"]
                )
                and SHA1.fullmatch(item["original_media_sha1"]) is not None
                and item["interpretation"] == (
                    "review-only-source-sha1-candidate-"
                    "not-accepted-game-or-release-identity"
                )
                and mame["source_manifest_path"].startswith("data/mame/softlists-v3/")
                and libretro["source_dat_path"].startswith("archive/libretro-")
            )
        if not valid:
            raise ValueError(f"invalid original {source} media source row {ordinal}")
        rows.append(item)
    if len(rows) != expected:
        raise ValueError(f"incomplete original {source} media observation inventory")
    return report, rows


def query(root=ROOT, *, sha1=None, libretro_platform=None, mame_list=None,
          title=None, limit=20, cohort="baseline", offset=0):
    if not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be 1..=200")
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("offset must be 0..1000000")
    if cohort not in ("baseline", "v3", "combined"):
        raise ValueError("cohort must be baseline, v3 or combined")
    if sha1 is not None and not re.fullmatch(r"[a-fA-F0-9]{40}", sha1):
        raise ValueError("SHA-1 requires 40 hex digits")
    if any(
        text is not None and (
            not isinstance(text, str) or not text.strip() or len(text) > 250
        )
        for text in (libretro_platform, mame_list, title)
    ):
        raise ValueError("blank or unbounded text filter")
    chosen = ("baseline", "v3") if cohort == "combined" else (cohort,)
    registries = [(*verified_rows(root, source=source), source) for source in chosen]
    needle = sha1.lower() if sha1 else None
    total = 0
    results = []
    for report, rows, source in registries:
        for row in rows:
            mame, libretro = row["mame"], row["libretro"]
            digest = row["media_sha1"] if source == "baseline" else row["original_media_sha1"]
            mame_title = mame["original_title"]
            libretro_title = (
                libretro["source_title"]
                if source == "baseline" else libretro["original_title"]
            )
            if (
                (needle and digest != needle)
                or (libretro_platform and libretro["platform"] != libretro_platform)
                or (mame_list and mame["source_list"] != mame_list)
                or (title and title.casefold() not in mame_title.casefold()
                    and title.casefold() not in libretro_title.casefold())
            ):
                continue
            total += 1
            if total > offset and len(results) < limit:
                # Preserve the original source claim fields. Cohort annotation
                # is additive and only used in non-legacy query modes.
                results.append(row if cohort == "baseline" else {
                    **row, "source_evidence_cohort": source,
                })
    total_all = sum(len(rows) for _, rows, _ in registries)
    digest_info = {
        source: (
            report["match_index_sha256"] if source == "baseline"
            else report["candidate_sha256"]
        )
        for report, _, source in registries
    }
    return {
        "source_mode": (
            "verified-original-cross-source-media-sha1-candidates"
            if cohort == "baseline" else
            "verified-independent-cohort-cross-source-media-sha1-candidates"
        ),
        "total_original_candidate_pairs": total_all,
        "total_filtered_candidate_pairs": total,
        "returned_candidate_pairs": len(results),
        "offset": offset,
        "next_offset": (
            offset + len(results)
            if offset + len(results) < total else None
        ),
        "source_digest_sha256": (
            digest_info["baseline"] if cohort == "baseline"
            else digest_info["v3"] if cohort == "v3"
            else digest_info
        ),
        **({
            "source_cohorts": list(chosen),
            "independent_mame_source_lists": 65 if cohort == "baseline" else (
                4 if cohort == "v3" else 69
            ),
        } if cohort != "baseline" else {}),
        "pairs": results,
        "interpretation": POLICY,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha1")
    parser.add_argument("--platform")
    parser.add_argument("--mame-list")
    parser.add_argument("--title")
    parser.add_argument("--cohort", choices=("baseline", "v3", "combined"),
                        default="baseline")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0,
                        help="filtered evidence pairs to skip (stable cohort order)")
    args = parser.parse_args()
    print(json.dumps(query(
        ROOT, sha1=args.sha1, libretro_platform=args.platform,
        mame_list=args.mame_list, title=args.title, cohort=args.cohort,
        limit=args.limit, offset=args.offset,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
