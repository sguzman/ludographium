#!/usr/bin/env python3
"""Audit source-field coverage and repeated fingerprints without asserting game identity."""
import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = Path("reports/source-coverage-v1.json")
RECORD_FIELDS = ("description", "region", "serial", "releaseyear", "releasemonth", "releaseday")
MEDIA_FIELDS = ("name", "size", "crc32", "md5", "sha1", "serial")


def summarize(bundle):
    if bundle.get("schema_version") != 1 or bundle.get("kind") != "source-observations":
        raise ValueError("unsupported source bundle")
    records = bundle["records"]
    media = [item for row in records for item in row["roms"]]
    if len(records) != bundle["record_count"] or len(media) != bundle["rom_count"]:
        raise ValueError("source bundle record counts disagree")
    sha1 = Counter(item["sha1"] for item in media if item.get("sha1"))
    crc_size = Counter((item["crc32"], item["size"]) for item in media if item.get("crc32"))
    titles = Counter(row["name"] for row in records)
    shared = lambda counts: {
        "groups": sum(1 for count in counts.values() if count > 1),
        "source_occurrences": sum(count for count in counts.values() if count > 1),
    }
    return {
        "platform": bundle["platform"],
        "source_records": len(records),
        "media_entries": len(media),
        "record_field_presence": {
            field: sum(1 for row in records if row.get(field) is not None and row.get(field) != "")
            for field in RECORD_FIELDS
        },
        "media_field_presence": {
            field: sum(1 for item in media if item.get(field) is not None and item.get(field) != "")
            for field in MEDIA_FIELDS
        },
        "complete_date_claims": sum(
            1 for row in records
            if all(row.get(k) for k in ("releaseyear", "releasemonth", "releaseday"))
        ),
        "identical_title_groups": shared(titles),
        "repeated_sha1_groups": shared(sha1),
        "multi_match_crc32_size_groups": shared(crc_size),
    }


def audit(root: Path):
    manifest = json.loads((root / "generated/v1/catalog.json").read_bytes())
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "source-catalog":
        raise ValueError("unsupported source catalog")
    platforms = []
    for entry in manifest["platforms"]:
        platform = entry["platform"]
        if not platform.replace("-", "").isalnum() or entry["artifact_path"] != f"generated/v1/{platform}.json":
            raise ValueError(f"unexpected artifact path: {platform}")
        bundle = json.loads((root / entry["artifact_path"]).read_bytes())
        if bundle.get("platform") != platform or bundle.get("source_revision") != manifest["source_revision"]:
            raise ValueError(f"mismatched platform source: {platform}")
        platforms.append(summarize(bundle))
    return {
        "schema_version": 1,
        "kind": "source-coverage",
        "source_id": manifest["source_id"],
        "source_revision": manifest["source_revision"],
        "explanation": (
            "Counts describe source assertions and repeated source occurrences, "
            "not distinct games, verified release identities, or checksum collisions."
        ),
        "platforms": platforms,
    }


def canonical_bytes(root: Path):
    return (json.dumps(audit(root), ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    expected = canonical_bytes(args.root)
    target = args.root / REPORT_PATH
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)
        print(f"WROTE {target}")
    elif not target.exists() or target.read_bytes() != expected:
        raise SystemExit("FAIL: source coverage report differs from the current catalog")
    else:
        print(f"PASS: {len(audit(args.root)['platforms'])} source coverage reports match the catalog")


if __name__ == "__main__":
    main()
