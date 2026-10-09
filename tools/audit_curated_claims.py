#!/usr/bin/env python3
"""Audit curated media against separate pinned bibliographic source claims.

This produces a *review-only* evidence report. A metadata claim that happens
to align with a cited ROM is not independent verification of a game identity.
No attribution, source observation, or curated record is modified.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from validate_curated import available_sources, evidence_key, validate_ledger

ROOT = Path(__file__).resolve().parents[1]


def _source_locator(source, claim):
    return {
        "source_id": source["source_id"],
        "source_revision": source["source_revision"],
        "source_path": claim["source_path"],
        "source_blob_sha": claim["source_blob_sha"],
        "source_ordinal": claim["source_ordinal"],
    }


def audit_platform(base, enriched, builds):
    """Return exact, source-attributed field claims for curated build media."""
    if base["platform"] != enriched["platform"]:
        raise ValueError("base and enrichment platforms differ")
    if (base["source_revision"] != enriched["base_source_revision"]
            or base["source_id"] != enriched["base_source_id"]):
        raise ValueError("base and enrichment source identities differ")

    records = {}
    for record in base["records"]:
        ordinal = record["source_ordinal"]
        if ordinal in records:
            raise ValueError("duplicate source observation ordinal")
        records[ordinal] = record

    by_ordinal_crc = defaultdict(list)
    for claim in enriched["claims"]:
        resolution = claim["resolution"]
        if resolution["status"] != "matched":
            continue
        ordinal = resolution["base_source_ordinal"]
        record = records.get(ordinal)
        if record is None or claim["source_comment"] != record["name"]:
            raise ValueError("resolved claim no longer matches source title")
        if not any(rom.get("crc32") == claim["crc32"] for rom in record["roms"]):
            raise ValueError("resolved claim CRC32 differs from source media")
        by_ordinal_crc[(ordinal, claim["crc32"])].append(claim)

    result = []
    for build in builds:
        media = build["media"]
        occurrences = []
        evidence = []
        for ref in build["evidence"]:
            ordinal = ref["source_ordinal"]
            record = records.get(ordinal)
            if record is None:
                raise ValueError(f"missing cited source occurrence: {build['id']}")
            if (ref["source_id"] != base["source_id"]
                    or ref["source_revision"] != base["source_revision"]
                    or ref["source_path"] != base["source_path"]
                    or ref["source_blob_sha"] != base["source_blob_sha"]):
                raise ValueError(f"source locator mismatch: {build['id']}")
            images = [
                rom for rom in record["roms"]
                if rom.get("sha1") == media["sha1"] and rom["size"] == media["size"]
            ]
            if not images:
                raise ValueError(f"build media absent from cited occurrence: {build['id']}")
            occurrences.append(ordinal)
            for rom in images:
                if not rom.get("crc32"):
                    continue
                for claim in by_ordinal_crc[(ordinal, rom["crc32"])]:
                    evidence.append({
                        "field": claim["field"],
                        "value": claim["value"],
                        "base_source_ordinal": ordinal,
                        "base_media_crc32": rom["crc32"],
                        "source": _source_locator(enriched, claim),
                    })
        evidence.sort(key=lambda c: (
            c["field"], c["value"] or "", c["base_source_ordinal"],
            c["source"]["source_path"], c["source"]["source_ordinal"],
        ))
        result.append({
            "build_id": build["id"],
            "release_id": build["release_id"],
            "sha1": media["sha1"],
            "size": media["size"],
            "base_source_ordinals": sorted(occurrences),
            "matched_claim_count": len(evidence),
            "matched_fields": sorted({e["field"] for e in evidence}),
            "source_claims": evidence,
        })
    return result


def build_report(root):
    ledger = json.loads((root / "curated/v1/identities.json").read_bytes())
    registry = json.loads((root / "platforms/platforms.json").read_bytes())
    validate_ledger(
        ledger, {p["id"] for p in registry["platforms"]}, available_sources(root)
    )
    source_manifest = json.loads((root / "generated/v1/catalog.json").read_bytes())
    source_paths = {p["platform"]: p["artifact_path"] for p in source_manifest["platforms"]}
    releases = {release["id"]: release for release in ledger["releases"]}
    works = {work["id"]: work for work in ledger["works"]}
    by_platform = defaultdict(list)
    for build in ledger["builds"]:
        by_platform[releases[build["release_id"]]["platform"]].append(build)

    builds = []
    for platform in sorted(by_platform):
        base = json.loads((root / source_paths[platform]).read_bytes())
        enriched = json.loads((root / f"generated/enrichment-v1/{platform}.json").read_bytes())
        for entry in audit_platform(base, enriched, by_platform[platform]):
            release = releases[entry["release_id"]]
            work = works[release["work_id"]]
            builds.append({
                "work_id": work["id"],
                "work_title": work["preferred_title"],
                "release_label": release["release_label"],
                "platform": platform,
                **entry,
            })
    builds.sort(key=lambda item: (item["platform"], item["work_title"], item["release_label"], item["build_id"]))
    return {
        "schema_version": 1,
        "kind": "curated-cross-source-claim-audit",
        "base_source_revision": source_manifest["source_revision"],
        "interpretation": (
            "Bibliographic DAT assertions attached to exact source observations. "
            "Their agreement with a base record does not verify work/release identity."
        ),
        "curated_build_count": len(builds),
        "builds_with_matched_claims": sum(bool(b["source_claims"]) for b in builds),
        "matched_claim_count": sum(b["matched_claim_count"] for b in builds),
        "builds": builds,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--export", type=Path)
    args = parser.parse_args()
    data = build_report(args.root)
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        print(f"WROTE {args.export}")
    else:
        summary = {key: data[key] for key in (
            "base_source_revision", "curated_build_count",
            "builds_with_matched_claims", "matched_claim_count"
        )}
        if args.verify:
            if data["curated_build_count"] == 0:
                raise SystemExit("FAIL: no curated media to audit")
            if not data["builds_with_matched_claims"]:
                raise SystemExit("FAIL: no independent bibliographic field claims found")
            for entry in data["builds"]:
                if entry["matched_claim_count"] != len(entry["source_claims"]):
                    raise SystemExit("FAIL: claim count is inconsistent")
            print("PASS: evidence-backed curated bibliographic claim audit")
        print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
