#!/usr/bin/env python3
"""Search original blob-pinned Libretro DAT observations without SQLite.

The 75 original source partitions remain licensed and attributed separately.
A missing cross-provider review lead is NOT a missing game or release.
"""
import argparse
import json
import re
import unicodedata

from acquire_mame_softlists import ROOT
from build_mame_catalog_sqlite import libretro_original_scopes, source_bytes
from import_dat import import_dat
from query_source_review_units import validate as validate_review_units

ORIGINAL_GAP_REPORT = "reports/libretro-source-review-acquisition-gaps-v1.json"
SHA1 = re.compile(r"[0-9a-fA-F]{40}\Z")


def fold(value):
    return unicodedata.normalize("NFKC", value or "").casefold()


def query(root=ROOT, *, platform=None, title=None, region=None, serial=None,
          sha1=None, without_review_leads=False, limit=20):
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("source result limit must be 1..200")
    for field, value in (
        ("platform", platform), ("title", title), ("region", region),
        ("serial", serial)
    ):
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 250
        ):
            raise ValueError(f"unsupported Libretro source filter: {field}")
    if sha1 is not None and (
        not isinstance(sha1, str) or not SHA1.fullmatch(sha1)
    ):
        raise ValueError("source media SHA-1 requires exactly 40 hex digits")
    scopes = libretro_original_scopes(root)
    by_platform = {entry["platform"]: (entry, source, path)
                   for entry, source, path in scopes}
    if len(scopes) != 75 or len(by_platform) != 75:
        raise ValueError("incomplete or repeated original Libretro source register")
    if platform is not None and platform not in by_platform:
        raise ValueError(f"unregistered Libretro source platform: {platform}")
    excluded = set()
    if without_review_leads:
        manifest, units, _ = validate_review_units(root)
        gap = json.loads(
            source_bytes(root, ORIGINAL_GAP_REPORT).decode("utf-8")
        )
        if (
            gap["schema_version"] != 1
            or gap["kind"] != "pinned-libretro-source-record-review-acquisition-backlog"
            or gap["libretro_source_collections"] != 75
            or gap["original_review_units_sha256"] != manifest["review_index_sha256"]
            or gap["original_source_record_totals"]["original_dat_records"] != 117145
        ):
            raise ValueError("original Libretro review-gap inventory is stale")
        excluded = {
            (target["platform"], target["original_source_ordinal"])
            for unit in units for target in unit["candidate_libretro_targets"]
        }
    returned = []
    total_matches = 0
    total_scanned = 0
    selected_scopes = [by_platform[platform]] if platform else [
        by_platform[name] for name in sorted(by_platform)
    ]
    for entry, source, path in selected_scopes:
        raw = source_bytes(root, path)
        if entry.get("bytes") is not None and len(raw) != entry["bytes"]:
            raise ValueError(f"original Libretro DAT source byte length changed: {path}")
        parsed = import_dat(raw, source, entry["platform"])
        if (
            parsed["platform"] != entry["platform"]
            or parsed["source_blob_sha"] != entry["git_blob_sha"]
            or parsed["source_license"] != "CC-BY-SA-4.0"
        ):
            raise ValueError(f"original source rights or fingerprint drift: {path}")
        for record in parsed["records"]:
            total_scanned += 1
            key = (entry["platform"], record["source_ordinal"])
            if without_review_leads and key in excluded:
                continue
            if title and fold(title) not in fold(record["name"]):
                continue
            if region and record.get("region") != region:
                continue
            if serial and record.get("serial") != serial:
                continue
            if sha1 and not any(
                m.get("sha1", "").casefold() == sha1.casefold()
                for m in record["roms"]
            ):
                continue
            total_matches += 1
            if len(returned) < limit:
                returned.append({
                    "original_source_record": record,
                    "source_platform": parsed["platform"],
                    "original_dat_path": str(path),
                    "original_git_blob_sha": parsed["source_blob_sha"],
                    "source_revision": parsed["source_revision"],
                    "source_license": parsed["source_license"],
                    "no_current_cross_provider_review_lead": (
                        True if without_review_leads else None
                    ),
                })
    return {
        "schema_version": 1,
        "source_mode": "direct-blob-verified-original-Libretro-DAT-search",
        "registered_source_platform_scopes": len(scopes),
        "scanned_original_source_records": total_scanned,
        "source_scopes_scanned": len(selected_scopes),
        "total_filtered_original_source_records": total_matches,
        "returned_original_source_records": len(returned),
        "without_review_leads": without_review_leads,
        "records": returned,
        "interpretation": (
            "Original CC-BY-SA-4.0 Libretro source observations only. "
            "No game, release, region or media identity is accepted, and "
            "a missing cross-provider review lead is never a missing game."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform")
    parser.add_argument("--title")
    parser.add_argument("--region")
    parser.add_argument("--serial")
    parser.add_argument("--sha1")
    parser.add_argument("--without-review-leads", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    result = query(
        ROOT, platform=args.platform, title=args.title, region=args.region,
        serial=args.serial, sha1=args.sha1,
        without_review_leads=args.without_review_leads, limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
