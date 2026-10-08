#!/usr/bin/env python3
"""Reproducible audit of attributed bibliographic claims and unresolved joins."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("reports/enrichment-coverage-v1.json")
FIELDS = ("developer", "publisher", "releaseyear", "releasemonth", "genre")
STATUSES = (
    "matched", "comment_mismatch", "missing_comment", "missing_value",
    "unmatched_crc", "ambiguous_crc",
)


def summarize(bundle, base, fields=None):
    if bundle.get("schema_version") != 1 or bundle.get("kind") != "source-enrichment-claims":
        raise ValueError("unsupported enrichment bundle")
    if base.get("source_revision") != bundle.get("base_source_revision"):
        raise ValueError("enrichment and base source revisions differ")
    claims = bundle["claims"]
    if len(claims) != bundle["claim_count"]:
        raise ValueError("claim counts disagree")
    all_counts = Counter(c["resolution"]["status"] for c in claims)
    if dict(all_counts) != bundle["resolution_counts"]:
        raise ValueError("resolution counts disagree")
    if set(all_counts) - set(STATUSES):
        raise ValueError("unknown resolution status")
    by_field = {}
    matched_records = set()
    conflicting = defaultdict(set)
    fields = fields or (*FIELDS, *sorted({c["field"] for c in claims} - set(FIELDS)))
    for field in fields:
        field_claims = [c for c in claims if c["field"] == field]
        counts = Counter(c["resolution"]["status"] for c in field_claims)
        target_records = set()
        for claim in field_claims:
            resolution = claim["resolution"]
            if resolution["status"] == "matched":
                ordinal = resolution["base_source_ordinal"]
                if not isinstance(ordinal, int) or ordinal < 1 or ordinal > len(base["records"]):
                    raise ValueError("invalid claimed source ordinal")
                target_records.add(ordinal)
                matched_records.add(ordinal)
                conflicting[(ordinal, field)].add(claim["value"])
        by_field[field] = {
            "claims": len(field_claims),
            "resolution_counts": {key: counts[key] for key in STATUSES if counts[key]},
            "matched_base_records": len(target_records),
        }
    mismatches = [
        {"base_source_ordinal": ordinal, "field": field, "values": sorted(values)}
        for (ordinal, field), values in conflicting.items() if len(values) > 1
    ]
    mismatches.sort(key=lambda item: (item["base_source_ordinal"], item["field"]))
    return {
        "platform": bundle["platform"],
        "base_source_records": len(base["records"]),
        "source_claims": len(claims),
        "matched_base_records_any_field": len(matched_records),
        "resolution_counts": {key: all_counts[key] for key in STATUSES if all_counts[key]},
        "fields": by_field,
        "different_values_for_one_field": len(mismatches),
        "conflict_samples": mismatches[:12],
    }


def report(root):
    source = json.loads((root / "sources/libretro-enrichment.json").read_bytes())
    fields = (*FIELDS, *sorted({f["field"] for f in source["files"]} - set(FIELDS)))
    platforms = []
    for platform in sorted({f["platform"] for f in source["files"]}):
        base = json.loads((root / f"generated/v1/{platform}.json").read_bytes())
        bundle = json.loads((root / f"generated/enrichment-v1/{platform}.json").read_bytes())
        if bundle["source_revision"] != source["repository_revision"] or base["platform"] != platform:
            raise ValueError("source mismatch")
        platforms.append(summarize(bundle, base, fields=fields))
    totals = Counter()
    for p in platforms:
        totals.update(p["resolution_counts"])
    return {
        "schema_version": 1,
        "kind": "enrichment-coverage",
        "source_id": source["source_id"],
        "source_revision": source["repository_revision"],
        "interpretation": "Source observations only. Matches require unique CRC32 and identical upstream title; they are not independently verified credits, dates, genres, or canonical game identities.",
        "total_claims": sum(p["source_claims"] for p in platforms),
        "resolution_counts": {key: totals[key] for key in STATUSES if totals[key]},
        "platforms": platforms,
    }


def canonical_bytes(root):
    return (json.dumps(report(root), ensure_ascii=False, separators=(",", ":")) + "\n").encode()


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
        print(f"WROTE {path}")
    elif not path.exists() or path.read_bytes() != data:
        raise SystemExit("FAIL: enrichment coverage report differs from indexed claims")
    else:
        result = report(args.root)
        print(f"PASS: {result['total_claims']} source claims in {len(result['platforms'])} platform collections")


if __name__ == "__main__":
    main()
