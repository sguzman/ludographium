#!/usr/bin/env python3
"""Validate manually curated game/release/build identities against source evidence."""
import argparse
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("curated/v1/identities.json")
KINDS = {"works": "w", "releases": "r", "builds": "b"}
REQUIRED = {
    "works": {"id", "preferred_title", "rationale", "evidence"},
    "releases": {"id", "work_id", "platform", "release_label", "rationale", "evidence"},
    "builds": {"id", "release_id", "build_label", "rationale", "evidence"},
}
REF_KEYS = {"source_id", "source_revision", "source_path", "source_blob_sha", "source_ordinal"}


def is_id(value, kind):
    if not isinstance(value, str) or not value.startswith(f"ldg:{kind}:"):
        return False
    raw = value[len(f"ldg:{kind}:"):]
    try:
        parsed = uuid.UUID(raw)
    except (ValueError, AttributeError):
        return False
    return parsed.version == 4 and str(parsed) == raw


def evidence_key(ref):
    if not isinstance(ref, dict) or set(ref) != REF_KEYS:
        raise ValueError("evidence must be an exact source occurrence locator")
    for key in REF_KEYS - {"source_ordinal"}:
        if not isinstance(ref[key], str) or not ref[key]:
            raise ValueError(f"evidence {key} must be a non-empty string")
    ordinal = ref["source_ordinal"]
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
        raise ValueError("evidence source_ordinal must be positive")
    return tuple(ref[key] for key in (
        "source_id", "source_revision", "source_path", "source_blob_sha", "source_ordinal"
    ))


def available_sources(root):
    """Read registered observations, not guess from source names or filenames."""
    catalog = json.loads((root / "generated/v1/catalog.json").read_bytes())
    refs = set()
    for item in catalog["platforms"]:
        bundle = json.loads((root / item["artifact_path"]).read_bytes())
        for row in bundle["records"]:
            refs.add((
                bundle["source_id"], bundle["source_revision"],
                bundle["source_path"], bundle["source_blob_sha"], row["source_ordinal"]
            ))
        path = root / f"generated/enrichment-v1/{item['platform']}.json"
        if path.exists():
            enriched = json.loads(path.read_bytes())
            for claim in enriched["claims"]:
                refs.add((
                    enriched["source_id"], enriched["source_revision"],
                    claim["source_path"], claim["source_blob_sha"], claim["source_ordinal"]
                ))
    return refs


def validate_ledger(ledger, platform_ids, available):
    if ledger.get("schema_version") != 1 or ledger.get("kind") != "curated-identity-ledger":
        raise ValueError("unsupported identity-ledger version/kind")
    if set(ledger) != {"schema_version", "kind", "works", "releases", "builds"}:
        raise ValueError("unexpected identity-ledger top-level fields")
    all_ids = set()
    indexed = {}
    counts = {}
    for section, kind in KINDS.items():
        rows = ledger[section]
        if not isinstance(rows, list):
            raise ValueError(f"{section} must be an array")
        indexed[section] = {}
        for item in rows:
            if not isinstance(item, dict) or set(item) != REQUIRED[section]:
                raise ValueError(f"invalid {section} record fields")
            identity = item["id"]
            if not is_id(identity, kind) or identity in all_ids:
                raise ValueError(f"invalid or duplicated stable identity: {identity}")
            all_ids.add(identity)
            indexed[section][identity] = item
            label_key = {"works": "preferred_title", "releases": "release_label",
                         "builds": "build_label"}[section]
            if not isinstance(item[label_key], str) or not item[label_key].strip():
                raise ValueError(f"{identity} requires a display label")
            if not isinstance(item["rationale"], str) or not item["rationale"].strip():
                raise ValueError(f"{identity} requires a curation rationale")
            evidence = item["evidence"]
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(f"{identity} requires attributed evidence")
            keys = [evidence_key(ref) for ref in evidence]
            if len(keys) != len(set(keys)):
                raise ValueError(f"{identity} repeats evidence")
            if any(key not in available for key in keys):
                raise ValueError(f"{identity} references an unknown source occurrence")
        counts[section] = len(rows)
    for item in ledger["releases"]:
        if item["work_id"] not in indexed["works"]:
            raise ValueError(f"{item['id']} references an unknown work")
        if item["platform"] not in platform_ids:
            raise ValueError(f"{item['id']} uses an unknown platform")
    for item in ledger["builds"]:
        if item["release_id"] not in indexed["releases"]:
            raise ValueError(f"{item['id']} references an unknown release")
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--mint-id", choices=("work", "release", "build"))
    args = p.parse_args()
    if args.mint_id:
        kind = {"work": "w", "release": "r", "build": "b"}[args.mint_id]
        print(f"ldg:{kind}:{uuid.uuid4()}")
        return
    ledger = json.loads((args.root / LEDGER).read_bytes())
    platforms = json.loads((args.root / "platforms/platforms.json").read_bytes())
    counts = validate_ledger(ledger, {p["id"] for p in platforms["platforms"]},
                             available_sources(args.root))
    print("PASS: curated identity ledger validated " +
          ", ".join(f"{key}={count}" for key, count in counts.items()))


if __name__ == "__main__":
    main()
