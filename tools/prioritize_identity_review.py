#!/usr/bin/env python3
"""Prioritize *review-only* source revision candidates with field-DAT coverage.

Coverage indicates which pinned field DATs describe each exact media image.
It does NOT establish that revisions share a canonical game or release, and
it never publishes an inferred identity or modifies any data.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from triage_identities import build_report as build_revision_report

ROOT = Path(__file__).resolve().parents[1]
STATUSES = ("uncurated", "partially-curated", "already-curated", "conflicting-curation")


def locator_tuple(ref):
    return (
        ref["source_id"], ref["source_revision"], ref["source_path"],
        ref["source_blob_sha"], ref["source_ordinal"],
    )


def curation_status(group, ledger):
    ownership = defaultdict(set)
    for release in ledger["releases"]:
        for ref in release["evidence"]:
            ownership[locator_tuple(ref)].add(release["id"])
    observed = [
        ownership.get(locator_tuple(member["evidence"]), set())
        for member in group["members"]
    ]
    if not any(observed):
        return "uncurated"
    if not all(observed):
        return "partially-curated"
    if len(set.intersection(*observed)) == 1 and all(len(ids) == 1 for ids in observed):
        return "already-curated"
    return "conflicting-curation"


def compare_platform(base, enriched, groups, ledger):
    if base["platform"] != enriched["platform"]:
        raise ValueError("incompatible source platforms")
    if (base["source_revision"] != enriched["base_source_revision"]
            or base["source_id"] != enriched["base_source_id"]):
        raise ValueError("incompatible base source and field-DAT revisions")
    by_ordinal = {row["source_ordinal"]: row for row in base["records"]}
    if len(by_ordinal) != len(base["records"]):
        raise ValueError("duplicate base record ordinal")
    claims = defaultdict(list)
    for claim in enriched["claims"]:
        resolution = claim["resolution"]
        if resolution["status"] != "matched":
            continue
        ordinal = resolution["base_source_ordinal"]
        record = by_ordinal.get(ordinal)
        if record is None or record["name"] != claim["source_comment"]:
            raise ValueError("matched claim has drifted from base source title")
        if not any(rom.get("crc32") == claim["crc32"] for rom in record["roms"]):
            raise ValueError("matched claim CRC32 is absent from source record")
        claims[(ordinal, claim["crc32"])].append(claim)

    result = []
    for group in groups:
        members = []
        for member in group["members"]:
            ordinal = member["evidence"]["source_ordinal"]
            record = by_ordinal.get(ordinal)
            if record is None or record["name"] != member["source_title"]:
                raise ValueError("revision candidate has stale base source evidence")
            media = [
                rom for rom in record["roms"]
                if rom.get("sha1", "").upper() == member["sha1"]
                and rom["size"] == member["size"]
            ]
            if len(media) != 1:
                raise ValueError("candidate image is missing or nonunique in base source")
            claim_refs = []
            if media[0].get("crc32"):
                for claim in claims[(ordinal, media[0]["crc32"])]:
                    claim_refs.append({
                        "field": claim["field"],
                        "value": claim["value"],
                        "source": {
                            "source_id": enriched["source_id"],
                            "source_revision": enriched["source_revision"],
                            "source_path": claim["source_path"],
                            "source_blob_sha": claim["source_blob_sha"],
                            "source_ordinal": claim["source_ordinal"],
                        },
                    })
            claim_refs.sort(key=lambda c: (
                c["field"], c["value"] or "", c["source"]["source_path"],
                c["source"]["source_ordinal"],
            ))
            members.append({
                **member,
                "field_claim_count": len(claim_refs),
                "field_names": sorted({ref["field"] for ref in claim_refs}),
                "bibliographic_claims": claim_refs,
            })
        shared = set(members[0]["field_names"])
        for member in members[1:]:
            shared.intersection_update(member["field_names"])
        disagreements = []
        for field in sorted(shared):
            per_member = [
                tuple(sorted({c["value"] for c in row["bibliographic_claims"] if c["field"] == field}))
                for row in members
            ]
            if len(set(per_member)) > 1:
                disagreements.append(field)
        result.append({
            "platform": group["platform"],
            "edition_label": group["edition_label"],
            "evidence_status": "review-only",
            "curation_status": curation_status(group, ledger),
            "shared_field_names": sorted(shared),
            "fields_with_different_source_values": disagreements,
            "member_count": len(members),
            "members": members,
        })
    return result


def build_report(root):
    basic = build_revision_report(root)
    ledger = json.loads((root / "curated/v1/identities.json").read_bytes())
    base_catalog = json.loads((root / "generated/v1/catalog.json").read_bytes())
    artifact_paths = {row["platform"]: row["artifact_path"] for row in base_catalog["platforms"]}
    groups = []
    for platform in basic["platforms"]:
        platform_id = platform["platform"]
        base = json.loads((root / artifact_paths[platform_id]).read_bytes())
        enriched = json.loads((root / f"generated/enrichment-v1/{platform_id}.json").read_bytes())
        groups.extend(compare_platform(base, enriched, platform["candidates"], ledger))
    # Highest bibliographic field coverage first, not identity confidence.
    groups.sort(key=lambda row: (
        -len(row["shared_field_names"]),
        -sum(member["field_claim_count"] for member in row["members"]),
        row["platform"], row["edition_label"].casefold(), row["edition_label"],
    ))
    return {
        "schema_version": 1,
        "kind": "revision-bibliographic-evidence-review",
        "base_source_revision": basic["source_revision"],
        "interpretation": (
            "Ordering reflects availability of matched field-DAT claims, NOT "
            "confidence in common work/release identity. Never merge automatically."
        ),
        "status_counts": dict(sorted(Counter(row["curation_status"] for row in groups).items())),
        "review_group_count": len(groups),
        "groups": groups,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--review", action="store_true")
    mode.add_argument("--export", type=Path)
    parser.add_argument("--platform")
    parser.add_argument("--status", choices=STATUSES)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if (args.platform or args.status or args.limit != 20) and not args.review:
        parser.error("filters are only valid with --review")
    if args.review and not 1 <= args.limit <= 100:
        parser.error("--limit must be in 1..100")
    report = build_report(args.root)
    if args.platform and args.platform not in {g["platform"] for g in report["groups"]}:
        parser.error("platform has no reviewed revision candidates")
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(
            json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"WROTE {args.export}")
    elif args.verify:
        if report["review_group_count"] < 1 or not any(
            group["shared_field_names"] for group in report["groups"]
        ):
            raise SystemExit("FAIL: revision review lacks evidence-linked field claims")
        if sum(report["status_counts"].values()) != report["review_group_count"]:
            raise SystemExit("FAIL: revision review count mismatch")
        if any(group["evidence_status"] != "review-only" for group in report["groups"]):
            raise SystemExit("FAIL: review candidate was incorrectly promoted")
        print(f"PASS: {report['review_group_count']} revision leads with source-field provenance")
    elif args.summary:
        print(json.dumps({
            "review_group_count": report["review_group_count"],
            "status_counts": report["status_counts"],
            "with_shared_claim_fields": sum(bool(group["shared_field_names"]) for group in report["groups"]),
        }, indent=2))
    else:
        groups = [
            g for g in report["groups"]
            if (args.platform is None or g["platform"] == args.platform)
            and (args.status is None or g["curation_status"] == args.status)
        ]
        print(json.dumps({
            "matching_groups": len(groups),
            "displayed": groups[:args.limit],
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
