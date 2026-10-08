#!/usr/bin/env python3
"""Produce a deterministic, integrity-checked, metadata-only runtime archive.

Consumers may extract the archive anywhere and open it as a Ludographium root.
Original DAT snapshots, game binaries, code, and development tools are excluded.
"""
import argparse
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("generated/v1/distribution.json")
SAFE = re.compile(r"^generated/(?:v1|enrichment-v1)/[a-z0-9._-]+\.json$")


def runtime_files(root):
    raw_manifest = (root / MANIFEST).read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get("kind") != "ludographium-distribution" or manifest.get("schema_version") != 1:
        raise ValueError("invalid runtime distribution manifest")
    artifacts = manifest["artifacts"]
    paths = [entry["path"] for entry in artifacts]
    if len(paths) != len(set(paths)) or not paths or "generated/v1/catalog.json" not in paths:
        raise ValueError("duplicate or incomplete runtime distribution")
    files = {MANIFEST.as_posix(): raw_manifest}
    for artifact in artifacts:
        path = artifact["path"]
        if not SAFE.fullmatch(path):
            raise ValueError(f"unsafe runtime artifact path: {path}")
        contents = (root / path).read_bytes()
        if len(contents) != artifact["bytes"] or hashlib.sha256(contents).hexdigest() != artifact["sha256"]:
            raise ValueError(f"runtime artifact checksum/size mismatch: {path}")
        files[path] = contents
    return dict(sorted(files.items()))


def build_archive(root):
    files = runtime_files(root)
    tar_data = BytesIO()
    with tarfile.open(fileobj=tar_data, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, contents in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(contents)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, BytesIO(contents))
    gz_data = BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_data, compresslevel=9, mtime=0) as gz:
        gz.write(tar_data.getvalue())
    return gz_data.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--build", type=Path, metavar="ARCHIVE")
    selection.add_argument("--verify", type=Path, metavar="ARCHIVE")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    expected = build_archive(args.root)
    target = args.build or args.verify
    if args.build:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)
        print(f"BUILT {target}: {len(expected)} bytes, SHA-256 {hashlib.sha256(expected).hexdigest()}")
    elif not target.exists() or target.read_bytes() != expected:
        raise SystemExit("FAIL: runtime archive is not a deterministic build of the committed metadata")
    else:
        print(f"PASS: runtime archive reproducible; SHA-256 {hashlib.sha256(expected).hexdigest()}")


if __name__ == "__main__":
    main()
