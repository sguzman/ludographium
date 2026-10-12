#!/usr/bin/env python3
"""Compare fourth-cohort MAME CC0 source claims with pinned Libretro DAT media.

Original source coordinates and provider licenses remain independent. Exact
SHA-1 AND equal source-declared byte size are required for a corroborated
media evidence pair. SHA-1 agreement without an independently declared size
is retained separately and NEVER promoted to a verified media candidate.
Nothing here accepts game, work, release, platform or edition identities.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT, source_register, verify_one
from query_mame_sources import original_index_rows
from reconcile_mame_media import read_libretro, valid_sha1, mame_size

INDEX = Path("data/reconciliation/mame-libretro-sha1-v4/links.jsonl")
UNKNOWN_SIZE = Path("data/reconciliation/mame-libretro-sha1-v4/size-uncorroborated.jsonl")
CONFLICTS = Path("data/reconciliation/mame-libretro-sha1-v4/size-disagreements.jsonl")
REPORT = Path("reports/mame-libretro-sha1-v4-summary.json")
ORIGINAL_REPORT = Path("reports/mame-software-observations-v4-summary.json")


def compact(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def encode(rows):
    return ("\n".join(compact(row) for row in rows)
            + ("\n" if rows else "")).encode("utf-8")


def size_status(mame_declared, libretro_declared):
    """Keep unknown-size and contradicted-size evidence out of matching."""
    if mame_declared is None:
        return "uncorroborated-size"
    if type(mame_declared) is not int or mame_declared < 0:
        raise ValueError("unrecognized source-declared MAME byte size")
    if type(libretro_declared) is not int or libretro_declared < 0:
        raise ValueError("unrecognized source-declared Libretro byte size")
    return "corroborated" if mame_declared == libretro_declared else "size-conflict"


def build_expected(root=ROOT):
    registered = source_register(root, "v4")
    if len(registered["files"]) != 8:
        raise ValueError("unregistered fourth MAME source scope")
    original_summary = json.loads((root / ORIGINAL_REPORT).read_text(encoding="utf-8"))
    counts = original_summary["source_observation_totals"]
    if (
        original_summary["schema_version"] != 1
        or original_summary["source_register"] != "sources/mame-softlists-v4.json"
        or original_summary["indexed_source_partitions"] != 8
        or counts["software_entries"] != 373
        or counts["rom_sha1_claims"] != 181
        or counts["disk_sha1_claims"] != 193
    ):
        raise ValueError("fourth-cohort original observation census differs")
    dat_by_sha1, dat_counts = read_libretro(root)
    if dat_counts["libretro_source_records"] != 117145:
        raise ValueError("independent Libretro DAT source inventory changed")
    linked, uncorroborated, conflicting = [], [], []
    source_counts = Counter()
    original_claims = Counter()
    matched_software = set()
    matched_dat = set()
    software = 0
    for filename in registered["files"]:
        pinned = verify_one(root, registered, filename)
        source_list = pinned["source_list_name"]
        for row in original_index_rows(root, filename, pinned, "v4"):
            software += 1
            source_key = (source_list, row["original_software_ordinal"])
            if row["original_xml_sha256"] != pinned["original_xml_sha256"]:
                raise ValueError("fourth-cohort original XML or software ordinal changed")
            for media in row["original_media_claims"]:
                attr = media["original_media_attributes"]
                sha1 = valid_sha1(attr.get("sha1"))
                if sha1 is None:
                    continue
                original_claims[media["kind"]] += 1
                size = mame_size(attr.get("size"))
                for dat in dat_by_sha1.get(sha1, ()):
                    status = size_status(size, dat["media_size_bytes"])
                    base = {
                        "schema_version": 1,
                        "source_cohort": "v4",
                        "original_media_sha1": sha1,
                        "mame": {
                            "source_list": source_list,
                            "original_software_ordinal": row["original_software_ordinal"],
                            "original_title": row["original_title"],
                            "source_xml_sha256": row["original_xml_sha256"],
                            "source_media_ordinal": media["source_ordinal"],
                            "source_media_kind": media["kind"],
                            "source_media_name": attr.get("name"),
                            "original_declared_size_bytes": size,
                            "original_manifest_path": (
                                "data/mame/softlists-v4/"
                                + filename.removesuffix(".xml") + "/manifest.json"
                            ),
                        },
                        "libretro": {
                            "platform": dat["platform"],
                            "original_source_ordinal": dat["source_record_ordinal"],
                            "original_title": dat["source_title"],
                            "source_media_ordinal": dat["source_media_ordinal"],
                            "original_media_size_bytes": dat["media_size_bytes"],
                            "source_dat_path": dat["source_dat_path"],
                            "original_git_blob_sha": dat["source_dat_blob_sha"],
                        },
                    }
                    if status == "uncorroborated-size":
                        uncorroborated.append({
                            **base,
                            "kind": "fourth-cohort-sha1-equal-size-not-corroborated",
                            "interpretation": (
                                "sha1-equal-without-mame-declared-size-"
                                "not-verified-equal-media-or-game-identity"
                            ),
                        })
                    elif status == "size-conflict":
                        conflicting.append({
                            **base,
                            "kind": "fourth-cohort-same-sha1-declared-size-conflict",
                            "interpretation": (
                                "excluded-same-sha1-incompatible-source-declared-byte-size"
                            ),
                        })
                    else:
                        linked.append({
                            **base,
                            "kind": "fourth-cohort-corroborated-media-review-candidate",
                            "size_corroborated": True,
                            "interpretation": (
                                "review-only-equal-sha1-and-byte-size-"
                                "not-a-game-or-release-identity"
                            ),
                        })
                        matched_software.add(source_key)
                        matched_dat.add((dat["platform"], dat["source_record_ordinal"]))
                        source_counts[(source_list, dat["platform"])] += 1
    if (
        software != 373
        or original_claims["rom"] != 181
        or original_claims["disk"] != 193
        or sum(map(len, (linked, uncorroborated, conflicting))) > 10000
    ):
        raise ValueError("fourth-cohort media evidence inventory changed")
    def order(row):
        left, right = row["mame"], row["libretro"]
        return (
            left["source_list"], left["original_software_ordinal"],
            left["source_media_ordinal"], right["platform"],
            right["original_source_ordinal"], right["source_media_ordinal"],
        )
    for rows in (linked, uncorroborated, conflicting):
        rows.sort(key=order)
    outputs = tuple(encode(rows) for rows in (linked, uncorroborated, conflicting))
    report = {
        "schema_version": 1,
        "kind": "independent-fourth-mame-cohort-media-sha1-evidence-audit",
        "mame_source_register": "sources/mame-softlists-v4.json",
        "original_observation_report": str(ORIGINAL_REPORT),
        "source_license_mame": "CC0-1.0",
        "source_license_libretro": "CC-BY-SA-4.0",
        "prior_media_source_report": "reports/mame-libretro-sha1-v3-summary.json",
        "original_mame_source_lists": 8,
        "original_mame_software_observations": software,
        "original_mame_rom_sha1_claims": original_claims["rom"],
        "original_mame_disk_sha1_claims": original_claims["disk"],
        "original_libretro_dat_collections": 75,
        "original_libretro_records": dat_counts["libretro_source_records"],
        "source_corrobated_media_candidate_pairs": len(linked),
        "source_sha1_equal_without_declared_mame_size_pairs": len(uncorroborated),
        "source_same_sha1_declared_size_conflicts": len(conflicting),
        "distinct_mame_software_with_corrobated_media_leads": len(matched_software),
        "distinct_libretro_records_with_corrobated_media_leads": len(matched_dat),
        "source_scope_corrobated_pair_counts": [
            {
                "mame_source_list": left,
                "libretro_platform": right,
                "size_corrobated_media_candidate_pairs": number,
            }
            for (left, right), number in sorted(source_counts.items())
        ],
        "corrobated_candidate_path": str(INDEX),
        "corrobated_candidate_sha256": hashlib.sha256(outputs[0]).hexdigest(),
        "corrobated_candidate_bytes": len(outputs[0]),
        "size_uncorroborated_path": str(UNKNOWN_SIZE),
        "size_uncorroborated_sha256": hashlib.sha256(outputs[1]).hexdigest(),
        "size_uncorroborated_bytes": len(outputs[1]),
        "rejected_size_conflicts_path": str(CONFLICTS),
        "rejected_size_conflicts_sha256": hashlib.sha256(outputs[2]).hexdigest(),
        "rejected_size_conflicts_bytes": len(outputs[2]),
        "interpretation": (
            "Independent fourth-cohort CC0 MAME original SHA1 claims checked "
            "against pinned CC-BY-SA-4.0 Libretro source DAT claims. A corroborated "
            "media pair requires equal SHA1 and equal independently declared "
            "byte-size evidence. SHA1 without declared MAME media size and "
            "contradictory source sizes are retained separately. No accepted "
            "game, platform, edition, release or media identity is inferred. "
            "Earlier source evidence ledgers remain immutable."
        ),
    }
    return outputs, json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs, report_text = build_expected()
    paths = (INDEX, UNKNOWN_SIZE, CONFLICTS)
    if args.write:
        for path, content in zip(paths, outputs):
            target = ROOT / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (ROOT / REPORT).write_text(report_text, encoding="utf-8")
    elif (
        any(
            not (ROOT / path).is_file()
            or (ROOT / path).is_symlink()
            or (ROOT / path).read_bytes() != content
            for path, content in zip(paths, outputs)
        )
        or not (ROOT / REPORT).is_file()
        or (ROOT / REPORT).is_symlink()
        or (ROOT / REPORT).read_text(encoding="utf-8") != report_text
    ):
        parser.error("original fourth-cohort media SHA1 evidence was modified or omitted")
    summary = json.loads(report_text)
    print(
        "verified", summary["source_corrobated_media_candidate_pairs"],
        "v4 source SHA1+size pairs;",
        summary["source_sha1_equal_without_declared_mame_size_pairs"],
        "size-unknown leads;", summary["source_same_sha1_declared_size_conflicts"],
        "size conflicts",
    )


if __name__ == "__main__":
    main()
