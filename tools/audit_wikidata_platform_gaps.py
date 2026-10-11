#!/usr/bin/env python3
"""Deterministic cross-source coverage audit; no network, databases, or inferred QIDs."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path("reports/wikidata-p400-platform-gaps-v2.json")
DISTRIBUTION_PARTITIONS = {
    "microsoftxbox360gamesondemand",
    "microsoftxbox360digital",
    "nintendonewnintendo3dsdigital",
    "nintendonintendo3dsdigital",
    "nintendonintendodsdownloadplay",
    "sonyplaystationportablepsn",
    "sonyplaystationportablepsx2psp",
    "sonyplaystationvitapsn",
}
POLICY = (
    "Unregistered source collections are evidence-acquisition backlog, not proof "
    "that Wikidata contains no game records. Distribution partitions must not "
    "be silently equated with hardware-level P400 identifiers or used to merge "
    "game/release identities."
)


def read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def build_report(root=ROOT):
    base_path = "platforms/platforms.json"
    bulk_path = "sources/bulk-expansion-v1.json"
    wikidata_path = "sources/wikidata-v1.json"
    base = read(root, base_path)
    bulk = read(root, bulk_path)
    originals = {}
    for item in base["platforms"]:
        platform = item["id"]
        if platform in originals:
            raise ValueError(f"duplicate original platform: {platform}")
        originals[platform] = item["name"]
    for item in bulk["platforms"]:
        platform = item["platform"]
        if platform in originals:
            raise ValueError(f"duplicate bulk platform: {platform}")
        originals[platform] = item["label"]
    register_paths = [
        wikidata_path,
        *sorted(
            (str(path.relative_to(root)) for path in (root / "sources").glob(
                "wikidata-platform-expansion-v*.json"
            )),
            key=lambda path: int(path.rsplit("-v", 1)[1].removesuffix(".json")),
        ),
    ]
    registered = {}
    for path in register_paths:
        register = read(root, path)
        if register["schema_version"] != 1:
            raise ValueError(f"unknown source register version: {path}")
        for item in register["platforms"]:
            platform = item["platform"]
            if platform in registered:
                raise ValueError(f"duplicate Wikidata platform scope: {platform}")
            if platform not in originals:
                raise ValueError(f"unknown original source platform scope: {platform}")
            registered[platform] = item["wikidata_platform"]
    gaps = [
        {
            "platform": platform,
            "source_label": label,
            "review_class": (
                "distribution-partition"
                if platform in DISTRIBUTION_PARTITIONS
                else "unregistered-platform-or-accessory"
            ),
            "interpretation": (
                "No independently registered Wikidata P400 scope for this "
                "original Libretro source collection"
            ),
        }
        for platform, label in sorted(originals.items())
        if platform not in registered
    ]
    return {
        "schema_version": 1,
        "kind": "independent-wikidata-p400-coverage-gaps",
        "source_registers": [base_path, bulk_path, *register_paths],
        "libretro_source_collections": len(originals),
        "registered_wikidata_p400_platform_scopes": len(registered),
        "unregistered_libretro_source_collections": len(gaps),
        "distribution_partition_research": sum(
            x["review_class"] == "distribution-partition" for x in gaps
        ),
        "platform_or_accessory_research": sum(
            x["review_class"] != "distribution-partition" for x in gaps
        ),
        "gaps": gaps,
        "policy": POLICY,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = json.dumps(build_report(), indent=2, ensure_ascii=False) + "\n"
    path = ROOT / REPORT
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != output:
            parser.error(f"{REPORT} is stale; run with --write")
        print(f"verified {REPORT}")
    else:
        path.write_text(output, encoding="utf-8")
        print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
