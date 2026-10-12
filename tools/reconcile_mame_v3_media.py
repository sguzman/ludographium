#!/usr/bin/env python3
"""Reconcile four additional pinned MAME CC0 lists without altering the v1/v2 index.

Source-only equal SHA1/equal-byte-size pairs are candidates; rejected declared
size disagreements remain separately pinned. Neither case establishes games,
releases, editions, platform equivalence or ownership of source claims.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT, source_register, verify_one
from query_mame_sources import original_index_rows
from reconcile_mame_media import read_libretro, valid_sha1, mame_size

OUTPUT = Path("data/reconciliation/mame-libretro-sha1-v3/links.jsonl")
CONFLICTS = Path("data/reconciliation/mame-libretro-sha1-v3/size-disagreements.jsonl")
REPORT = Path("reports/mame-libretro-sha1-v3-summary.json")
POLICY = (
    "Four original MAME CC0 software-list sources were compared against "
    "75 separately attributed Libretro CC-BY-SA DAT scopes. Equal media "
    "SHA1 and byte-size assertions are independent source candidates, "
    "not accepted game, work, release, edition or platform identities. "
    "Conflicting declared media sizes remain separate and unresolved. "
    "Earlier v1/v2 MAME source correspondence is unchanged."
)


def compact(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def encode(rows):
    return ("\n".join(compact(row) for row in rows)
            + ("\n" if rows else "")).encode("utf-8")


def build_expected(root=ROOT):
    register = source_register(root, "v3")
    if len(register["files"]) != 4:
        raise ValueError("missing separate third-cohort original CC0 MAME source lists")
    dat_index, dat_counts = read_libretro(root)
    if dat_counts["libretro_source_records"] != 117145:
        raise ValueError("Libretro original source revision drifted")
    candidates, conflicting = [], []
    software_count = 0
    original_sha1_count = 0
    matched_software = set()
    matched_dat = set()
    source_counts = Counter()
    for filename in register["files"]:
        original = verify_one(root, register, filename)
        list_id = original["source_list_name"]
        for row in original_index_rows(root, filename, original, "v3"):
            software_count += 1
            source_software = (list_id, row["original_software_ordinal"])
            if row["original_xml_sha256"] != original["original_xml_sha256"]:
                raise ValueError("MAME original source projection changed")
            for source_media in row["original_media_claims"]:
                attr = source_media["original_media_attributes"]
                sha1 = valid_sha1(attr.get("sha1"))
                if sha1 is None:
                    continue
                original_sha1_count += 1
                original_size = mame_size(attr.get("size"))
                for other in dat_index.get(sha1, ()):
                    base = {
                        "schema_version": 1,
                        "original_media_sha1": sha1,
                        "mame": {
                            "source_list": list_id,
                            "software_ordinal": row["original_software_ordinal"],
                            "original_title": row["original_title"],
                            "source_media_ordinal": source_media["source_ordinal"],
                            "source_media_kind": source_media["kind"],
                            "source_media_name": attr.get("name"),
                            "original_declared_size_bytes": original_size,
                            "source_xml_sha256": row["original_xml_sha256"],
                            "source_manifest_path": (
                                "data/mame/softlists-v3/"
                                + filename.removesuffix(".xml")
                                + "/manifest.json"
                            ),
                        },
                        "libretro": {
                            "platform": other["platform"],
                            "source_record_ordinal": other["source_record_ordinal"],
                            "source_media_ordinal": other["source_media_ordinal"],
                            "original_title": other["source_title"],
                            "original_media_size_bytes": other["media_size_bytes"],
                            "source_dat_path": other["source_dat_path"],
                            "source_dat_blob_sha": other["source_dat_blob_sha"],
                        },
                    }
                    if (
                        original_size is not None
                        and original_size != other["media_size_bytes"]
                    ):
                        conflicting.append({
                            **base,
                            "kind": "rejected-v3-mame-libretro-original-declared-media-size-conflict",
                            "interpretation": "excluded-source-size-conflict-not-equal-media-file-or-game-identity",
                        })
                        continue
                    candidates.append({
                        **base,
                        "kind": "review-only-v3-mame-libretro-exact-media-sha1-candidate",
                        "size_corroborated": original_size is not None,
                        "interpretation": (
                            "review-only-source-sha1-candidate-"
                            "not-accepted-game-or-release-identity"
                        ),
                    })
                    matched_software.add(source_software)
                    matched_dat.add((other["platform"], other["source_record_ordinal"]))
                    source_counts[(list_id, other["platform"])] += 1
    if software_count != 166 or original_sha1_count != 199:
        raise ValueError("third original source-cohort observation counts changed")
    if len(candidates) + len(conflicting) > 20000:
        raise ValueError("candidate expansion exceeded source-evidence ceiling")
    order = lambda r: (
        r["mame"]["source_list"],r["mame"]["software_ordinal"],
        r["mame"]["source_media_ordinal"],r["libretro"]["platform"],
        r["libretro"]["source_record_ordinal"],
        r["libretro"]["source_media_ordinal"],
    )
    candidates.sort(key=order)
    conflicting.sort(key=order)
    linked = encode(candidates)
    rejected = encode(conflicting)
    report = {
        "schema_version": 1,
        "kind": "separate-third-cohort-exact-original-media-source-candidates",
        "mame_source_register": "sources/mame-softlists-v3.json",
        "libretro_source_registers": [
            "sources/libretro-no-intro.json",
            "sources/bulk-expansion-v1.json",
        ],
        "mame_source_license": "CC0-1.0",
        "libretro_source_license": "CC-BY-SA-4.0",
        "mame_original_source_lists": 4,
        "mame_original_software_observations": software_count,
        "mame_original_sha1_claims": original_sha1_count,
        "independent_libretro_dat_collections": 75,
        "original_libretro_dat_records": dat_counts["libretro_source_records"],
        "source_media_sha1_candidate_pairs": len(candidates),
        "candidate_pairs_with_corroborated_size": sum(
            candidate["size_corroborated"] for candidate in candidates
        ),
        "independent_mame_software_with_candidates": len(matched_software),
        "independent_libretro_dat_records_with_candidates": len(matched_dat),
        "source_size_disagreement_rows": len(conflicting),
        "source_scope_pair_candidate_evidence": [
            {
                "mame_source_list": left,
                "libretro_source_scope": right,
                "source_media_candidate_pairs": count,
            }
            for (left, right), count in sorted(source_counts.items())
        ],
        "candidate_path": str(OUTPUT),
        "candidate_sha256": hashlib.sha256(linked).hexdigest(),
        "candidate_bytes": len(linked),
        "rejected_size_conflicts_path": str(CONFLICTS),
        "rejected_size_conflicts_sha256": hashlib.sha256(rejected).hexdigest(),
        "rejected_size_conflicts_bytes": len(rejected),
        "interpretation": POLICY,
    }
    return linked, rejected, json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original, disagreements, summary = build_expected()
    path, conflict_path, report = ROOT / OUTPUT, ROOT / CONFLICTS, ROOT / REPORT
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        conflict_path.write_bytes(disagreements)
        report.write_text(summary, encoding="utf-8")
    elif (
        not path.is_file() or path.is_symlink() or path.read_bytes() != original
        or not conflict_path.is_file() or conflict_path.is_symlink()
        or conflict_path.read_bytes() != disagreements
        or not report.is_file() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("third CC0 MAME source reconciliation differs from original evidence")
    value = json.loads(summary)
    print(f"verified {value['source_media_sha1_candidate_pairs']} independent v3 original SHA1 evidence pairs")


if __name__ == "__main__":
    main()
