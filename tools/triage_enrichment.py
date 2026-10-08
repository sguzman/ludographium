#!/usr/bin/env python3
"""Deterministic review queue of unresolved bibliographic source observations.

Candidates are provided for human research; no candidate is an approved join
or verified identity, and this tool never alters imported metadata.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = Path("reports/reconciliation-queue-v1.json")
STATUSES = ("comment_mismatch", "ambiguous_crc", "missing_comment", "missing_value", "unmatched_crc")


def review_platform(base, enriched, sample_limit=8):
    if base["platform"] != enriched["platform"] or base["source_revision"] != enriched["base_source_revision"]:
        raise ValueError("incompatible source revisions or platforms")
    by_crc = defaultdict(list)
    for record in base["records"]:
        for media in record["roms"]:
            if media.get("crc32"):
                by_crc[media["crc32"]].append({
                    "base_source_ordinal": record["source_ordinal"],
                    "source_title": record["name"],
                    "sha1": media.get("sha1"),
                    "size": media.get("size"),
                })
    grouped = {}
    for claim in enriched["claims"]:
        resolution = claim["resolution"]
        if resolution["status"] == "matched":
            continue
        status = resolution["status"]
        if status not in STATUSES or resolution["base_source_ordinal"] is not None:
            raise ValueError("unexpected unresolved claim resolution")
        key = (status, claim["crc32"], claim["source_comment"])
        if key not in grouped:
            grouped[key] = {
                "status": status,
                "crc32": claim["crc32"],
                "source_title_comment": claim["source_comment"],
                "candidate_base_records": by_crc.get(claim["crc32"], []),
                "source_claims": [],
            }
        grouped[key]["source_claims"].append({
            "field": claim["field"],
            "value": claim["value"],
            "source_id": enriched["source_id"],
            "source_revision": enriched["source_revision"],
            "source_path": claim["source_path"],
            "source_blob_sha": claim["source_blob_sha"],
            "source_ordinal": claim["source_ordinal"],
        })

    counts = {status: {"claim_count": 0, "distinct_review_groups": 0} for status in STATUSES}
    for entry in grouped.values():
        row = counts[entry["status"]]
        row["claim_count"] += len(entry["source_claims"])
        row["distinct_review_groups"] += 1
    groups = sorted(grouped.values(), key=lambda row: (
        STATUSES.index(row["status"]), row["crc32"], row["source_title_comment"] or ""
    ))
    samples = []
    for status in STATUSES:
        samples.extend(group for group in groups if group["status"] == status) if sample_limit is None else None
        if sample_limit is not None:
            samples.extend(group for group in groups if group["status"] == status][:sample_limit])
    return {
        "platform": base["platform"],
        "source_claims": sum(value["claim_count"] for value in counts.values()),
        "review_groups": len(grouped),
        "statuses": counts,
        "samples": samples,
    }


def build_report(root, sample_limit=8):
    manifest = json.loads((root / "generated/v1/catalog.json").read_bytes())
    platforms = []
    for registration in manifest["platforms"]:
        platform = registration["platform"]
        base = json.loads((root / registration["artifact_path"]).read_bytes())
        enriched = json.loads((root / f"generated/enrichment-v1/{platform}.json").read_bytes())
        platforms.append(review_platform(base, enriched, sample_limit=sample_limit))
    return {
        "schema_version": 1,
        "kind": "source-claim-reconciliation-review",
        "source_revision": manifest["source_revision"],
        "interpretation": "Review candidates only. Same CRC32 or similar titles do not establish a canonical game, release, or build identity.",
        "platforms": platforms,
    }


def canonical_bytes(root):
    return (json.dumps(build_report(root), ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--review", action="store_true")
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--platform", help="platform filter for --review")
    p.add_argument("--status", choices=STATUSES, help="resolution filter for --review")
    p.add_argument("--crc32", help="8-character checksum filter for --review")
    p.add_argument("--limit", type=int, default=25, help="max review groups (1..100)")
    args = p.parse_args()
    if args.review:
        if not 1 <= args.limit <= 100:
            p.error("--limit must be in 1..100")
        if args.crc32 and (len(args.crc32) != 8 or
                           any(c not in "0123456789abcdefABCDEF" for c in args.crc32)):
            p.error("--crc32 requires eight hexadecimal characters")
        value = build_report(args.root, sample_limit=None)
        rows = [g for plat in value["platforms"] for g in plat["samples"]
                if (args.platform is None or args.platform == plat["platform"])
                and (args.status is None or args.status == g["status"])
                and (args.crc32 is None or args.crc32.upper() == g["crc32"])]
        # Include the platform because source locators are platform scoped.
        matches = [{**g, "platform": p["platform"]}
                   for p in value["platforms"]
                   for g in p["samples"]
                   if (args.platform is None or args.platform == p["platform"])
                   and (args.status is None or args.status == g["status"])
                   and (args.crc32 is None or args.crc32.upper() == g["crc32"])]
        print(json.dumps({"matching_groups": len(matches), "displayed": matches[:args.limit]},
                         ensure_ascii=False, indent=2))
        return
    if args.platform or args.status or args.crc32 or args.limit != 25:
        p.error("filters only apply to --review")
    data = canonical_bytes(args.root)
    target = args.root / REPORT
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"WROTE {target}")
    elif not target.exists() or target.read_bytes() != data:
        raise SystemExit("FAIL: reconciliation review queue differs from source observations")
    else:
        value = json.loads(data)
        print(f"PASS: review queue for {len(value['platforms'])} platforms")


if __name__ == "__main__":
    main()
