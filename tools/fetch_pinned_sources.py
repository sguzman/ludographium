#!/usr/bin/env python3
"""Retrieve registered immutable metadata DAT sources, with Git blob verification."""
import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def source_path(entry, collection):
    platform = entry["platform"]
    if not platform.isalnum() or platform.lower() != platform:
        raise ValueError("invalid platform ID")
    if collection == "base":
        return Path("archive/libretro-no-intro") / f"{platform}.dat"
    field = entry["field"]
    if not re.fullmatch(r"[a-z][a-z0-9_]*", field):
        raise ValueError("invalid field identifier")
    return Path("archive/libretro-enrichment") / platform / f"{field}.dat"


def pinned_url(registry, entry):
    revision = registry["repository_revision"]
    path = PurePosixPath(entry["source_path"])
    if (
        len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision)
        or path.is_absolute() or ".." in path.parts
        or not entry["source_path"].startswith("metadat/")
    ):
        raise ValueError("invalid pinned revision or source path")
    repository = registry["repository"]
    if repository != "https://github.com/libretro/libretro-database":
        raise ValueError("unsupported original source repository")
    return f"https://raw.githubusercontent.com/libretro/libretro-database/{revision}/{quote(entry['source_path'])}"


def accession(root, registry_path, collection):
    registry = json.loads((root / registry_path).read_bytes())
    checked = 0
    fetched = 0
    for entry in registry["files"]:
        destination = root / source_path(entry, collection)
        if destination.exists():
            data = destination.read_bytes()
        else:
            with urlopen(pinned_url(registry, entry), timeout=90) as response:
                data = response.read()
            fetched += 1
        digest = git_blob_sha(data)
        if digest != entry["git_blob_sha"]:
            raise ValueError(f"registered Git blob mismatch at {destination}: {digest}")
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        checked += 1
    return checked, fetched


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args()
    for source, kind in [
        ("sources/libretro-no-intro.json", "base"),
        ("sources/libretro-enrichment.json", "enrichment"),
    ]:
        checked, fetched = accession(args.root, source, kind)
        print(f"{kind}: {checked} registered source files verified; {fetched} retrieved")


if __name__ == "__main__":
    main()
