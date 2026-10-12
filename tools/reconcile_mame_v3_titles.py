#!/usr/bin/env python3
"""Additive, noncanonical title-review leads for third MAME CC0 accession.

No earlier 65-list title review files are modified. The four new source lists
are compared only with original Libretro DAT scopes independently corroborated
by SHA1-and-equal-size source observations; exact normalized names never
establish accepted game, release, translation, or platform identity.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT, source_register, verify_one
from query_mame_sources import original_index_rows
from build_mame_catalog_sqlite import libretro_original_scopes
from import_dat import import_dat
from reconcile_mame_titles import normalized_title
from reconcile_mame_v3_media import REPORT as MEDIA_REPORT, OUTPUT as MEDIA_INDEX

OUTPUT = Path("data/reconciliation/mame-libretro-title-review-v3/candidates.jsonl")
SUMMARY = Path("reports/mame-libretro-title-review-v3-summary.json")
INTERPRETATION = (
    "Third-cohort exact normalized title leads only, in source-scope pairs "
    "supported by at least three independent SHA1-and-equal-size MAME source "
    "records. All candidate alternatives remain unreviewed; no accepted game, "
    "release, edition, region, translation or platform identities are inferred."
)


def raw_bytes(root, relative):
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or linked original source evidence: {relative}")
    return path.read_bytes()


def compact(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def evidence(root):
    summary = json.loads(raw_bytes(root, MEDIA_REPORT))
    raw = raw_bytes(root, MEDIA_INDEX)
    if (
        summary["schema_version"] != 1
        or summary["kind"] != "separate-third-cohort-exact-original-media-source-candidates"
        or summary["mame_source_register"] != "sources/mame-softlists-v3.json"
        or summary["source_media_sha1_candidate_pairs"] != 127
        or summary["mame_original_source_lists"] != 4
        or summary["mame_original_software_observations"] != 166
        or summary["candidate_path"] != str(MEDIA_INDEX)
        or summary["candidate_bytes"] != len(raw)
        or summary["candidate_sha256"] != hashlib.sha256(raw).hexdigest()
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError("pinned third-cohort media evidence changed")
    linked = set()
    scopes = defaultdict(set)
    seen = 0
    for row in raw.splitlines():
        claim = json.loads(row)
        if (
            claim["kind"] != "review-only-v3-mame-libretro-exact-media-sha1-candidate"
            or not claim["size_corroborated"]
            or claim["mame"]["original_declared_size_bytes"] !=
            claim["libretro"]["original_media_size_bytes"]
        ):
            raise ValueError("unverified third-cohort media scope correspondence")
        mame = claim["mame"]
        libretro = claim["libretro"]
        item = (mame["source_list"], mame["software_ordinal"])
        linked.add(item)
        scopes[(mame["source_list"], libretro["platform"])].add(item)
        seen += 1
    if (
        seen != 127
        or len(linked) != summary["independent_mame_software_with_candidates"]
    ):
        raise ValueError("incomplete independent third-cohort SHA1 evidence")
    return summary, linked, {key: len(value) for key, value in scopes.items()}


def build_expected(root=ROOT):
    media, sha1_linked, support = evidence(root)
    registered = source_register(root, "v3")
    if len(registered["files"]) != 4:
        raise ValueError("third MAME source accession is incomplete")
    eligible = {
        key: score for key, score in support.items() if score >= 3
    }
    needed_platforms = {platform for _, platform in eligible}
    libretro_index = defaultdict(list)
    for entry, source_register_data, path in libretro_original_scopes(root):
        platform = entry["platform"]
        if platform not in needed_platforms:
            continue
        raw = raw_bytes(root, path)
        parsed = import_dat(raw, source_register_data, platform)
        if entry.get("bytes") is not None and entry["bytes"] != len(raw):
            raise ValueError(f"changed original Libretro DAT length: {platform}")
        for row in parsed["records"]:
            key = normalized_title(row["name"])
            if key:
                libretro_index[(platform, key)].append({
                    "original_source_ordinal": row["source_ordinal"],
                    "original_title": row["name"],
                    "original_dat_path": str(path),
                    "original_git_blob_sha": parsed["source_blob_sha"],
                })
    observations = 0
    unlinked_observations = 0
    rows = []
    for filename in registered["files"]:
        original = verify_one(root, registered, filename)
        scope = original["source_list_name"]
        platform_targets = sorted(
            (platform, count)
            for (mame_scope, platform), count in eligible.items()
            if mame_scope == scope
        )
        for entry in original_index_rows(root, filename, original, "v3"):
            observations += 1
            ordinal = entry["original_software_ordinal"]
            if entry["original_xml_sha256"] != original["original_xml_sha256"]:
                raise ValueError("original source projection no longer agrees with XML")
            if (scope, ordinal) in sha1_linked:
                continue
            unlinked_observations += 1
            title = entry["original_title"]
            key = normalized_title(title)
            if not key:
                continue
            for platform, support_count in platform_targets:
                for other in libretro_index.get((platform, key), []):
                    rows.append({
                        "schema_version": 1,
                        "kind": "third-mame-cohort-review-only-exact-title-evidence",
                        "normalized_title_key": key,
                        "scope_pair_distinct_mame_sha1_supported_records": support_count,
                        "mame": {
                            "source_cohort": "v3",
                            "source_list": scope,
                            "original_software_ordinal": ordinal,
                            "original_title": title,
                            "source_xml_sha256": original["original_xml_sha256"],
                            "original_xml_path": entry["original_xml_path"],
                        },
                        "libretro": {
                            "platform": platform,
                            **other,
                        },
                        "interpretation": (
                            "review-only-name-equality-in-media-supported-source-scope-"
                            "not-a-verified-game-or-release-identity"
                        ),
                    })
    rows.sort(key=lambda r: (
        r["mame"]["source_list"],
        r["mame"]["original_software_ordinal"],
        r["libretro"]["platform"],
        r["libretro"]["original_source_ordinal"],
    ))
    pairs = ("\n".join(compact(row) for row in rows)
             + ("\n" if rows else "")).encode("utf-8")
    report = {
        "schema_version": 1,
        "kind": "additive-third-mame-cohort-title-review",
        "original_mame_source_register": "sources/mame-softlists-v3.json",
        "prior_title_cohort": "reports/mame-libretro-title-review-v1-summary.json",
        "source_media_report": str(MEDIA_REPORT),
        "source_media_index_sha256": media["candidate_sha256"],
        "original_mame_source_lists": 4,
        "original_software_observations": observations,
        "original_software_with_sha1_source_leads": len(sha1_linked),
        "original_software_without_sha1_source_leads": unlinked_observations,
        "source_scope_pairs_with_sha1_support": len(support),
        "eligible_source_scope_pairs": len(eligible),
        "minimum_distinct_mame_sha1_scope_support": 3,
        "original_title_review_candidate_pairs": len(rows),
        "distinct_original_mame_software_with_title_leads": len({
            (r["mame"]["source_list"], r["mame"]["original_software_ordinal"])
            for r in rows
        }),
        "source_scope_support": [
            {
                "mame_source_list": key[0],
                "libretro_original_scope": key[1],
                "distinct_mame_source_records_with_prior_sha1_evidence": count,
                "eligible_for_title_review": key in eligible,
            }
            for key, count in sorted(support.items())
        ],
        "candidate_path": str(OUTPUT),
        "candidate_sha256": hashlib.sha256(pairs).hexdigest(),
        "candidate_bytes": len(pairs),
        "interpretation": INTERPRETATION,
    }
    if observations != 166 or len(sha1_linked) != 127 or unlinked_observations != 39:
        raise ValueError("third accession source observation census changed")
    return pairs, json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows, summary = build_expected()
    path, report = ROOT / OUTPUT, ROOT / SUMMARY
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rows)
        report.write_text(summary, encoding="utf-8")
    elif (
        not path.is_file() or path.is_symlink() or path.read_bytes() != rows
        or not report.is_file() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("additive v3 title-review evidence was modified or not built")
    parsed = json.loads(summary)
    print(
        "verified", parsed["original_title_review_candidate_pairs"],
        "third-cohort review-only exact title pairs against",
        parsed["eligible_source_scope_pairs"], "independently supported scopes"
    )


if __name__ == "__main__":
    main()
