#!/usr/bin/env python3
"""Validate and reproduce the portable curated game/release/build identity export."""
import argparse
import json
from pathlib import Path

from validate_curated import available_sources, validate_ledger

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("curated/v1/identities.json")
OUTPUT = Path("generated/curated-v1/identities.json")


def canonical_bytes(root):
    ledger = json.loads((root / SOURCE).read_bytes())
    platforms = json.loads((root / "platforms/platforms.json").read_bytes())
    validate_ledger(ledger, {p["id"] for p in platforms["platforms"]}, available_sources(root))
    return (json.dumps(ledger, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    data = canonical_bytes(args.root)
    path = args.root / OUTPUT
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"WROTE {path} ({len(data)} bytes)")
    elif not path.exists() or path.read_bytes() != data:
        raise SystemExit("FAIL: curated distribution differs from validated source ledger")
    else:
        print("PASS: curated source identity export is reproducible")


if __name__ == "__main__":
    main()
