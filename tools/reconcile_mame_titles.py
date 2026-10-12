#!/usr/bin/env python3
"""Conservatively identify review-only source title correspondences.

Scope pairs are first grounded in independently pinned equal-SHA1/equal-size
media claims. For MAME entries without any exact media correspondence, only
literal titles equal after removing recognized trailing region/language tags
are proposed. No game, release, translation or platform identity is inferred.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from acquire_mame_softlists import ROOT, source_register, verify_one
from query_mame_sources import original_index_rows
from query_mame_media import INDEX as LINKS_PATH, REPORT as LINKS_REPORT
from build_mame_catalog_sqlite import libretro_original_scopes
from import_dat import import_dat

OUTPUT = Path("data/reconciliation/mame-libretro-title-review-v1/candidates.jsonl")
SUMMARY = Path("reports/mame-libretro-title-review-v1-summary.json")
MIN_DISTINCT_SUPPORT = 3
MAX_CANDIDATES = 200000

REGIONS = {
    "usa", "europe", "japan", "world", "asia", "australia", "brazil",
    "canada", "china", "france", "germany", "italy", "korea", "spain",
    "taiwan", "hong kong", "united kingdom", "netherlands", "sweden",
    "portugal", "russia", "mexico", "poland",
}
LANGUAGES = {
    "en", "ja", "fr", "de", "es", "it", "pt", "ko", "zh", "nl",
    "ru", "sv", "pl", "ar", "he",
}
TRAILING = re.compile(r"\s*\(([^()]*)\)\s*$")


def normalized_title(value):
    if not isinstance(value, str) or not value.strip():
        return None
    original = unicodedata.normalize("NFKC", value).strip()
    while True:
        match = TRAILING.search(original)
        if not match:
            break
        attributes = [part.strip().casefold() for part in match.group(1).split(",")]
        if attributes and all(
            part in REGIONS or part in LANGUAGES
            or re.fullmatch(r"rev(?:ision)?\s+[a-z0-9.]+", part)
            for part in attributes
        ):
            original = original[:match.start()].strip()
        else:
            break
    return " ".join(original.casefold().split()) or None


def source_json(root, path):
    source = root / path
    if source.is_symlink():
        raise ValueError(f"symlink in original source inventory: {path}")
    return json.loads(source.read_text(encoding="utf-8"))


def source_bytes(root, path):
    file = root / path
    if file.is_symlink():
        raise ValueError(f"linked source evidence: {path}")
    return file.read_bytes()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def evidence_scopes(root):
    summary = source_json(root, LINKS_REPORT)
    data = source_bytes(root, LINKS_PATH)
    if (
        summary["schema_version"] != 1
        or summary["mame_software_lists"] != 65
        or summary["libretro_source_platforms"] != 75
        or summary["match_index_path"] != str(LINKS_PATH)
        or len(data) != summary["match_index_bytes"]
        or hashlib.sha256(data).hexdigest() != summary["match_index_sha256"]
    ):
        raise ValueError("source-correspondence evidence changed")
    support = defaultdict(set)
    seen_mame = defaultdict(set)
    for row in data.splitlines():
        link = json.loads(row)
        if (
            link["kind"] != "exact-mame-libretro-media-sha1-source-candidate"
            or not link["size_corroborated"]
            or link["mame"]["source_size_bytes"] != link["libretro"]["media_size_bytes"]
            or not link["interpretation"].startswith("review-only")
        ):
            raise ValueError("non-evidence candidate in original media SHA1 index")
        mame = link["mame"]
        libretro = link["libretro"]
        key = (mame["source_list"], libretro["platform"])
        support[key].add((mame["software_ordinal"], libretro["source_record_ordinal"]))
        seen_mame[mame["source_list"]].add(mame["software_ordinal"])
    if len(data.splitlines()) != summary["exact_sha1_source_candidate_pairs"]:
        raise ValueError("truncated original SHA1 source-candidate records")
    return support, seen_mame, summary


def build_expected(root=ROOT):
    support, seen_mame, evidence = evidence_scopes(root)
    approved = {
        key: len({source_pair[0] for source_pair in value})
        for key, value in support.items()
        if len({source_pair[0] for source_pair in value}) >= MIN_DISTINCT_SUPPORT
    }
    libretro_index = defaultdict(list)
    platform_blobs = {}
    for entry, register, source_path in libretro_original_scopes(root):
        platform = entry["platform"]
        original = source_bytes(root, source_path)
        parsed = import_dat(original, register, platform)
        if entry.get("bytes") is not None and len(original) != entry["bytes"]:
            raise ValueError(f"original source DAT length changed: {platform}")
        platform_blobs[platform] = {
            "original_dat_path": str(source_path),
            "original_git_blob_sha": parsed["source_blob_sha"],
        }
        for row in parsed["records"]:
            key = normalized_title(row["name"])
            if key is not None:
                libretro_index[(platform, key)].append(
                    (row["source_ordinal"], row["name"])
                )
    candidates = []
    mame_observations = 0
    considered_unmatched = 0
    for cohort in ("v1", "v2"):
        registered = source_register(root, cohort)
        for filename in registered["files"]:
            source = verify_one(root, registered, filename)
            list_name = source["source_list_name"]
            targets = sorted(
                (platform, count)
                for (mame, platform), count in approved.items()
                if mame == list_name
            )
            for row in original_index_rows(root, filename, source, cohort):
                mame_observations += 1
                source_ordinal = row["original_software_ordinal"]
                if source_ordinal in seen_mame[list_name]:
                    continue
                considered_unmatched += 1
                key = normalized_title(row["original_title"])
                if not key:
                    continue
                for platform, source_support in targets:
                    for libretro_ordinal, original_title in libretro_index.get((platform, key), []):
                        candidates.append({
                            "schema_version": 1,
                            "kind": "review-only-exact-source-title-correspondence",
                            "normalized_title_key": key,
                            "source_scope_pair_sha1_supported_mame_records": source_support,
                            "mame": {
                                "source_list": list_name,
                                "software_ordinal": source_ordinal,
                                "original_title": row["original_title"],
                                "original_source_xml_sha256": row["original_xml_sha256"],
                                "original_source_xml_path": row["original_xml_path"],
                            },
                            "libretro": {
                                "platform": platform,
                                "source_ordinal": libretro_ordinal,
                                "original_title": original_title,
                                **platform_blobs[platform],
                            },
                            "interpretation": (
                                "review-only-equal-normalized-titles-"
                                "with-scope-corroboration-not-verified-game-or-release-identity"
                            ),
                        })
                        if len(candidates) > MAX_CANDIDATES:
                            raise ValueError("unexpected title-candidate expansion")
    candidates.sort(key=lambda x: (
        x["mame"]["source_list"], x["mame"]["software_ordinal"],
        x["libretro"]["platform"], x["libretro"]["source_ordinal"]
    ))
    raw = ("\n".join(compact(row) for row in candidates)
           + ("\n" if candidates else "")).encode("utf-8")
    scope_details = [
        {
            "mame_source_list": key[0],
            "libretro_source_platform": key[1],
            "distinct_mame_software_records_with_exact_media_evidence": len({
                pair[0] for pair in rows
            }),
            "distinct_media_supported_source_record_pairs": len(rows),
            "eligible_for_title_review": key in approved,
        }
        for key, rows in sorted(support.items())
    ]
    report = {
        "schema_version": 1,
        "kind": "conservative-sha1-grounded-exact-title-review",
        "source_media_evidence_report": str(LINKS_REPORT),
        "source_media_index_sha256": evidence["match_index_sha256"],
        "mame_source_list_count": 65,
        "libretro_source_collection_count": 75,
        "original_mame_source_software_observations": mame_observations,
        "original_mame_software_records_without_any_exact_sha1_match": considered_unmatched,
        "minimum_distinct_mame_media_supported_scope_records": MIN_DISTINCT_SUPPORT,
        "source_scope_pairs_with_media_support": len(scope_details),
        "source_scope_pairs_eligible_for_title_review": len(approved),
        "total_review_only_exact_title_candidates": len(candidates),
        "distinct_mame_software_with_title_candidate": len({
            (row["mame"]["source_list"], row["mame"]["software_ordinal"])
            for row in candidates
        }),
        "candidate_path": str(OUTPUT),
        "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "candidate_bytes": len(raw),
        "source_scope_correspondence_evidence": scope_details,
        "interpretation": (
            "These are review-only exact normalized title correspondences in "
            "source-list pairs grounded in >=3 independent MAME source records "
            "with prior exact SHA1 and size evidence. Only recognized trailing "
            "region/language/revision tags are removed. No title, game, "
            "edition, release, translation or system identity is accepted."
        ),
    }
    if mame_observations != 32953:
        raise ValueError("incomplete original CC0 MAME software-title inventory")
    return raw, json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original, report = build_expected()
    target = ROOT / OUTPUT
    summary = ROOT / SUMMARY
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original)
        summary.write_text(report, encoding="utf-8")
    elif (
        not target.exists() or target.is_symlink() or target.read_bytes() != original
        or not summary.exists() or summary.is_symlink()
        or summary.read_text(encoding="utf-8") != report
    ):
        parser.error("source-only title review artifacts differ from pinned evidence")
    result = json.loads(report)
    print(
        "verified review-only MAME/Libretro source title evidence: "
        f"{result['total_review_only_exact_title_candidates']} candidates from "
        f"{result['source_scope_pairs_eligible_for_title_review']} source-scope pairs"
    )


if __name__ == "__main__":
    main()
