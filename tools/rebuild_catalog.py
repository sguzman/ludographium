#!/usr/bin/env python3
"""Reconstruct identification indexes and their catalog manifest from archived DATs."""
import argparse
import hashlib
import json
from pathlib import Path

from import_dat import import_dat

ROOT = Path(__file__).resolve().parents[1]


def git_blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def rebuild(root):
    registry = json.loads((root / "sources/libretro-no-intro.json").read_bytes())
    manifest = {
        "schema_version": 1,
        "kind": "source-catalog",
        "source_id": registry["source_id"],
        "source_revision": registry["repository_revision"],
        "license": registry["declared_repository_license"],
        "generated_by": "tools/import_dat.py",
        "platforms": [],
    }
    outputs = {}
    used = set()
    for entry in registry["files"]:
        platform = entry["platform"]
        if platform in used or not platform.isalnum():
            raise ValueError(f"invalid/repeated platform: {platform}")
        used.add(platform)
        path = root / "archive/libretro-no-intro" / f"{platform}.dat"
        dat = path.read_bytes()
        bundle = import_dat(dat, registry, platform)
        output_path = f"generated/v1/{platform}.json"
        raw = canonical(bundle)
        outputs[output_path] = raw
        manifest["platforms"].append({
            "platform": platform,
            "source_records": bundle["record_count"],
            "rom_fingerprints": bundle["rom_count"],
            "source_archive_path": f"archive/libretro-no-intro/{platform}.dat",
            "source_git_blob_sha": entry["git_blob_sha"],
            "artifact_path": output_path,
            "artifact_git_blob_sha": git_blob_sha(raw),
        })
    outputs["generated/v1/catalog.json"] = canonical(manifest)
    return outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    outputs = rebuild(args.root)
    for path, data in outputs.items():
        destination = args.root / path
        if args.write:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        elif not destination.exists() or destination.read_bytes() != data:
            raise SystemExit(f"FAIL: generated catalog differs: {path}")
    print(f"PASS: {len(outputs) - 1} platform source indexes reproducible")


if __name__ == "__main__":
    main()
