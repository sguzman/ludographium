#!/usr/bin/env python3
"""Validate manually curated game/release/build identities against source evidence."""
import argparse
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("curated/v1/identities.json")
KINDS = {"works": "w", "releases": "r", "builds": "b"}
REQUIRED = {
    "works": {"id", "preferred_title", "rationale", "evidence"},
    "releases": {"id", "work_id", "platform", "release_label", "rationale", "evidence"},
    "builds": {"id", "release_id", "build_label", "rationale", "evidence", "media"},
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
    refs = {}
    for item in catalog["platforms"]:
        platform = item["platform"]
        bundle = json.loads((root / item["artifact_path"]).read_bytes())
        for row in bundle["records"]:
            key = (
                bundle["source_id"], bundle["source_revision"],
                bundle["source_path"], bundle["source_blob_sha"], row["source_ordinal"]
            )
            if key in refs:
                raise ValueError("repeated source occurrence locator")
            refs[key] = {
                "platform": platform,
                "media": {(m["sha1"], m["size"]) for m in row["roms"] if m.get("sha1")},
            }
        path = root / f"generated/enrichment-v1/{platform}.json"
        if path.exists():
            enriched = json.loads(path.read_bytes())
            for claim in enriched["claims"]:
                key = (
                    enriched["source_id"], enriched["source_revision"],
                    claim["source_path"], claim["source_blob_sha"], claim["source_ordinal"]
                )
                if key in refs:
                    raise ValueError("repeated enrichment occurrence locator")
                refs[key] = {"platform": platform, "media": set()}
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
    # A single source occurrence cannot prove two competing *curated*
    # work or publication identities. These owners must be explicit and
    # disjoint; unresolved ambiguity stays in the review queue instead.
    for section in ("works", "releases"):
        owners = {}
        for item in ledger[section]:
            for ref in item["evidence"]:
                key = evidence_key(ref)
                previous = owners.setdefault(key, item["id"])
                if previous != item["id"]:
                    raise ValueError(
                        f"source occurrence belongs to competing curated {section}: "
                        f"{previous} and {item['id']}"
                    )

    for item in ledger["releases"]:
        work = indexed["works"].get(item["work_id"])
        if work is None:
            raise ValueError(f"{item['id']} references an unknown work")
        if item["platform"] not in platform_ids:
            raise ValueError(f"{item['id']} uses an unknown platform")
        # A release is a *subset* of its parent work's explicitly cited
        # source observations. Never infer this bridge from a title alone.
        work_evidence = {evidence_key(ref) for ref in work["evidence"]}
        if not {evidence_key(ref) for ref in item["evidence"]}.issubset(work_evidence):
            raise ValueError(f"{item['id']} has evidence not cited by its work")
        if any(available[evidence_key(ref)]["platform"] != item["platform"]
               for ref in item["evidence"]):
            raise ValueError(f"{item['id']} cites another platform's media as a release")

    used_media = set()
    for item in ledger["builds"]:
        release = indexed["releases"].get(item["release_id"])
        if release is None:
            raise ValueError(f"{item['id']} references an unknown release")
        # Builds must be supported by specific observations of their
        # parent release; matching the platform or title alone is not enough.
        release_evidence = {evidence_key(ref) for ref in release["evidence"]}
        if not {evidence_key(ref) for ref in item["evidence"]}.issubset(release_evidence):
            raise ValueError(f"{item['id']} has evidence not cited by its release")
        media = item["media"]
        if (not isinstance(media, dict) or set(media) != {"sha1", "size"}
                or not isinstance(media["sha1"], str)
                or re.fullmatch(r"[A-F0-9]{40}", media["sha1"]) is None
                or not isinstance(media["size"], int) or isinstance(media["size"], bool)
                or media["size"] <= 0):
            raise ValueError(f"{item['id']} requires an exact SHA-1 and byte size")
        fingerprint = (media["sha1"], media["size"])
        if not any(available[evidence_key(ref)]["platform"] == release["platform"]
                   and fingerprint in available[evidence_key(ref)]["media"]
                   for ref in item["evidence"]):
            raise ValueError(f"{item['id']} media fingerprint is absent from its cited source")
        scoped = (release["platform"], *fingerprint)
        if scoped in used_media:
            raise ValueError(f"{item['id']} repeats an already curated media identity")
        used_media.add(scoped)
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
