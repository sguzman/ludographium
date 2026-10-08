#!/usr/bin/env python3
"""Resolve locally stored game metadata by exact fingerprint, with source evidence."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from lookup import find_matches, find_title_matches

ROOT = Path(__file__).resolve().parents[1]


def checked_artifact(root: Path, distribution, path):
    entries = [a for a in distribution["artifacts"] if a["path"] == path]
    if len(entries) != 1:
        raise ValueError(f"missing or repeated artifact in manifest: {path}")
    raw = (root / path).read_bytes()
    entry = entries[0]
    if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(f"artifact digest/size mismatch: {path}")
    return json.loads(raw)


def join_claims(matches, claims):
    """Attach only source-validated matches, keeping disputed CRC claims separate."""
    attached = defaultdict(list)
    unresolved = defaultdict(list)
    for claim in claims:
        status = claim["resolution"]["status"]
        info = {
            "field": claim["field"],
            "value": claim["value"],
            "source_comment": claim["source_comment"],
            "source_path": claim["source_path"],
            "source_blob_sha": claim["source_blob_sha"],
            "source_ordinal": claim["source_ordinal"],
            "status": status,
        }
        if status == "matched":
            ordinal = claim["resolution"]["base_source_ordinal"]
            if not isinstance(ordinal, int) or ordinal < 1:
                raise ValueError("matched claim must reference a valid source ordinal")
            attached[(ordinal, claim["crc32"])].append(info)
        else:
            unresolved[claim["crc32"]].append(info)

    result = []
    for match in matches:
        ordinal = match["source"]["ordinal"]
        crc32 = match["rom"].get("crc32")
        result.append({
            **match,
            "metadata_claims": attached[(ordinal, crc32)],
            "unresolved_source_claims": unresolved[crc32],
        })
    return result


def lookup(root, platform, *, sha1=None, crc32=None, size=None, title=None, limit=50):
    if platform not in {"snes", "gb", "gbc", "gba", "nes", "nds"}:
        raise ValueError("unsupported platform")
    distribution = json.loads((root / "generated/v1/distribution.json").read_bytes())
    if distribution.get("schema_version") != 1 or distribution.get("kind") != "ludographium-distribution":
        raise ValueError("unsupported distribution manifest")
    base = checked_artifact(root, distribution, f"generated/v1/{platform}.json")
    enriched = checked_artifact(root, distribution, f"generated/enrichment-v1/{platform}.json")
    if (base.get("platform") != platform or enriched.get("platform") != platform
            or enriched.get("base_source_revision") != base.get("source_revision")
            or enriched.get("base_source_id") != base.get("source_id")):
        raise ValueError("source and enrichment snapshot mismatch")
    if base["source_revision"] != distribution["source_revision"]:
        raise ValueError("distribution revision mismatch")
    if title is not None:
        if sha1 is not None or crc32 is not None or size is not None:
            raise ValueError("title discovery must not be combined with hashes or size")
        found = find_title_matches(base, title, limit=limit)
        expanded = join_claims(found["matches"], enriched["claims"])
        return {
            "query_kind": "source-title-substring",
            "total_source_records": found["total_source_records"],
            "match_count": len(expanded),
            "matches": expanded,
        }
    if limit != 50:
        raise ValueError("limit only applies to title discovery")
    matches = find_matches(base, sha1=sha1, crc32=crc32, size=size)
    expanded = join_claims(matches, enriched["claims"])
    return {"match_count": len(expanded), "matches": expanded}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--platform", choices=("snes", "gb", "gbc", "gba", "nes", "nds"), required=True)
    p.add_argument("--root", type=Path, default=ROOT)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--sha1")
    g.add_argument("--crc32")
    g.add_argument("--title")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--size", type=int)
    a = p.parse_args()
    result = lookup(a.root, a.platform, sha1=a.sha1, crc32=a.crc32, size=a.size,
                    title=a.title, limit=a.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
