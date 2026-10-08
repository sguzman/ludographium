#!/usr/bin/env python3
"""Build or verify the deterministic SHA-256 distribution manifest."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_PATH = Path("generated/v1/distribution.json")


def build_distribution(root: Path):
    catalog = json.loads((root / "generated/v1/catalog.json").read_bytes())
    if catalog.get("schema_version") != 1 or catalog.get("kind") != "source-catalog":
        raise ValueError("unsupported source catalog")
    paths = {"generated/v1/catalog.json"}

    # Portable metadata must carry the original source and licensing evidence.
    # These extra artifacts are optional only for minimal test/legacy catalogs
    # that contain no original source registers.
    base_register = root / "sources/libretro-no-intro.json"
    if base_register.exists():
        if not (root / "METADATA-NOTICE.md").exists():
            raise ValueError("metadata source register requires METADATA-NOTICE.md")
        paths.update(("sources/libretro-no-intro.json", "METADATA-NOTICE.md"))
    for entry in catalog["platforms"]:
        platform = entry["platform"]
        expected = f"generated/v1/{platform}.json"
        if not platform.replace("-", "").isalnum() or entry["artifact_path"] != expected:
            raise ValueError(f"invalid platform artifact path: {platform}")
        if expected in paths:
            raise ValueError(f"duplicate platform: {platform}")
        paths.add(expected)

    # The enrichment index is optional for earlier v1 snapshots. When a
    # source register exists, its platform-normalized claim bundles are published.
    enrichment_registry = root / "sources/libretro-enrichment.json"
    if enrichment_registry.exists():
        paths.add("sources/libretro-enrichment.json")
        enrichment = json.loads(enrichment_registry.read_bytes())
        if enrichment.get("schema_version") != 1:
            raise ValueError("unsupported enrichment source registry")
        if enrichment["repository_revision"] != catalog["source_revision"]:
            raise ValueError("enrichment and base source revisions differ")
        valid_platforms = {p["platform"] for p in catalog["platforms"]}
        for platform in sorted({f["platform"] for f in enrichment["files"]}):
            if platform not in valid_platforms:
                raise ValueError(f"unregistered enrichment platform: {platform}")
            paths.add(f"generated/enrichment-v1/{platform}.json")

    # The curated ledger is a separately validated, source-backed projection.
    if (root / "curated/v1/identities.json").exists():
        paths.add("generated/curated-v1/identities.json")

    artifacts = []
    for path in sorted(paths):
        data = (root / path).read_bytes()
        artifacts.append({
            "path": path,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return {
        "schema_version": 1,
        "kind": "ludographium-distribution",
        "source_id": catalog["source_id"],
        "source_revision": catalog["source_revision"],
        "artifacts": artifacts,
    }


def canonical_bytes(root: Path):
    return (
        json.dumps(build_distribution(root), ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="rebuild distribution manifest")
    group.add_argument("--check", action="store_true", help="check the committed manifest")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    actual = canonical_bytes(args.root)
    path = args.root / DIST_PATH
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(actual)
        print(f"WROTE {path}")
    elif not path.exists() or path.read_bytes() != actual:
        raise SystemExit("FAIL: distribution manifest out of date; rebuild with --write")
    else:
        print(f"PASS: {len(build_distribution(args.root)['artifacts'])} SHA-256 verified distribution artifacts")


if __name__ == "__main__":
    main()
