#!/usr/bin/env python3
"""Audit identical original media SHA-1 claims across Libretro source scopes.

Original CC-BY-SA Libretro DAT records, their source ordinals, media sizes and
Git-blob hashes are preserved. Equal fingerprints are not accepted game,
platform, edition or release identities. No game bytes are downloaded.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from reconcile_mame_media import ROOT, read_libretro
from build_expanded_corpus import pinned_manifest

INDEX = Path("data/reconciliation/libretro-cross-scope-sha1-v1/groups.jsonl")
REPORT = Path("reports/libretro-cross-scope-sha1-v1.json")
POLICY = (
    "Identical SHA1 media claims in more than one independent Libretro DAT "
    "scope are source-level fingerprint overlaps only. Such reuse does not "
    "establish matching games, releases, formats, platform compatibility, "
    "or mistaken assignments. Contradictory declared sizes remain unresolved."
)


def compact(item):
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def normalized_group(sha1, claims):
    if len(sha1) != 40 or any(digit not in "0123456789abcdef" for digit in sha1):
        raise ValueError("invalid original media fingerprint")
    ordinals = set()
    size_values = set()
    records = []
    for claim in claims:
        key = (
            claim["platform"],
            claim["source_record_ordinal"],
            claim["source_media_ordinal"],
        )
        if key in ordinals:
            raise ValueError("duplicate source media ordinal in independent DAT inventory")
        ordinals.add(key)
        size = claim["media_size_bytes"]
        if type(size) is not int or size < 0:
            raise ValueError("invalid original Libretro source media size")
        size_values.add(size)
        records.append(claim)
    records.sort(key=lambda c: (
        c["platform"], c["source_record_ordinal"], c["source_media_ordinal"]
    ))
    platforms = sorted({c["platform"] for c in records})
    if len(platforms) < 2:
        raise ValueError("single-platform SHA1 group is not cross-platform evidence")
    return {
        "schema_version": 1,
        "kind": "unresolved-cross-scope-exact-media-sha1-observation",
        "original_media_sha1": sha1,
        "distinct_source_scopes": platforms,
        "distinct_source_scope_count": len(platforms),
        "original_source_media_claim_count": len(records),
        "distinct_declared_media_sizes_bytes": sorted(size_values),
        "declared_size_disagreement": len(size_values) > 1,
        "independent_source_media_claims": records,
        "source_license": "CC-BY-SA-4.0",
        "interpretation": "original-media-fingerprint-overlap-only-no-canonical-game-or-platform-identity",
    }


def build_expected(root=ROOT):
    fingerprint_index, source_totals = read_libretro(root)
    if (
        source_totals["libretro_source_records"] != 117145
        or source_totals["libretro_sha1_claims"] != 117145
    ):
        raise ValueError("Libretro original source inventory changed")
    reused_within_source_scopes = 0
    original_sha1_claims = 0
    cross_scope = []
    observed_scopes = set()
    for sha1, claims in sorted(fingerprint_index.items()):
        original_sha1_claims += len(claims)
        by_scope = Counter(claim["platform"] for claim in claims)
        observed_scopes.update(by_scope)
        reused_within_source_scopes += any(count > 1 for count in by_scope.values())
        if len(by_scope) >= 2:
            cross_scope.append(normalized_group(sha1, claims))
    if original_sha1_claims != source_totals["libretro_sha1_claims"]:
        raise ValueError("source hash-bearing claims were lost in grouping")
    first_register = json.loads((root / "sources/libretro-no-intro.json").read_text(encoding="utf-8"))
    expanded_register = pinned_manifest(root)
    declared_scopes = {
        item["platform"] for item in first_register["files"]
    } | {
        item["platform"] for item in expanded_register["platforms"]
    }
    if len(declared_scopes) != 75 or observed_scopes - declared_scopes:
        raise ValueError("unexpected independent DAT source scope inventory")
    data = ("\n".join(compact(row) for row in cross_scope)
            + ("\n" if cross_scope else "")).encode("utf-8")
    scope_pair_counts = Counter()
    for row in cross_scope:
        platforms = row["distinct_source_scopes"]
        for i, left in enumerate(platforms):
            for right in platforms[i + 1:]:
                scope_pair_counts[(left, right)] += 1
    summary = {
        "schema_version": 1,
        "kind": "attributed-libretro-cross-scope-media-sha1-overlap",
        "source_registers": [
            "sources/libretro-no-intro.json",
            "sources/bulk-expansion-v1.json",
        ],
        "source_license": "CC-BY-SA-4.0",
        "independent_libretro_dat_scopes": len(declared_scopes),
        "source_scopes_with_original_sha1_claims": len(observed_scopes),
        "source_scopes_with_no_sha1_claims": sorted(declared_scopes - observed_scopes),
        "original_sha1_media_claims": original_sha1_claims,
        "distinct_source_sha1_values": len(fingerprint_index),
        "sha1_groups_reused_within_at_least_one_scope": reused_within_source_scopes,
        "sha1_groups_observed_across_independent_scopes": len(cross_scope),
        "source_media_claims_in_cross_scope_groups": sum(
            row["original_source_media_claim_count"] for row in cross_scope
        ),
        "cross_scope_groups_with_declared_size_disagreement": sum(
            row["declared_size_disagreement"] for row in cross_scope
        ),
        "source_scope_pairs_with_sha1_overlap": len(scope_pair_counts),
        "source_scope_pair_evidence": [
            {
                "left_source_scope": left,
                "right_source_scope": right,
                "distinct_shared_original_sha1_observations": count,
            }
            for (left, right), count in sorted(scope_pair_counts.items())
        ],
        "candidate_index_path": str(INDEX),
        "candidate_index_sha256": hashlib.sha256(data).hexdigest(),
        "candidate_index_bytes": len(data),
        "interpretation": POLICY,
    }
    return data, json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source, summary = build_expected()
    destination, report = ROOT / INDEX, ROOT / REPORT
    if args.write:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source)
        report.write_text(summary, encoding="utf-8")
    elif (
        not destination.is_file() or destination.is_symlink()
        or destination.read_bytes() != source
        or not report.is_file() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("cross-scope Libretro original-source evidence is missing or stale")
    value = json.loads(summary)
    print(
        f"verified {value['original_sha1_media_claims']} Libretro source media rows; "
        f"{value['sha1_groups_observed_across_independent_scopes']} cross-scope SHA1 groups"
    )


if __name__ == "__main__":
    main()
