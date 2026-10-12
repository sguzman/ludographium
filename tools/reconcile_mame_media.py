#!/usr/bin/env python3
"""Find exact SHA-1 media-byte claim overlaps across pinned MAME and Libretro.

This is a source-evidence index, not a title/game/edition identity join.
MAME software-list ROMs may represent chips or parts rather than complete
cartridges. Only equal SHA-1 with corroborating sizes (when given) is linked.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from acquire_mame_softlists import source_register, verify_one
from import_dat import import_dat
from build_expanded_corpus import pinned_manifest

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("data/mame/software-observations-v1")
MATCH_BASE = Path("data/reconciliation/mame-libretro-sha1-v1")
SUMMARY = Path("reports/mame-libretro-media-sha1-v1-summary.json")
HEX40 = re.compile(r"[a-fA-F0-9]{40}\Z")
INTERPRETATION = (
    "Equal SHA-1 of source-declared media bytes is exact media-fingerprint "
    "evidence only. Neither shared names nor matching source hashes establish "
    "that a MAME part/chip, Libretro ROM, video game, edition or release is the "
    "same identity. Distinct source scopes are retained and all potential "
    "cross-scope matches remain review-only."
)


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def source_json(path):
    if path.is_symlink():
        raise ValueError(f"symbolic link in pinned source: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def verified_mame_index(root, filename, expected):
    key = filename.removesuffix(".xml")
    directory = root / BASE / key
    manifest = source_json(directory / "manifest.json")
    path = directory / "observations.jsonl"
    if path.is_symlink():
        raise ValueError(f"symbolic link in MAME index: {path}")
    raw = path.read_bytes()
    if (
        manifest["schema_version"] != 1
        or manifest["source"] != "MAME"
        or manifest["license"] != "CC0-1.0"
        or manifest["original_source_list"] != expected["source_list_name"]
        or manifest["original_xml_sha256"] != expected["original_xml_sha256"]
        or manifest["original_xml_path"] != str(
            Path("data/mame/softlists-v1") / key / filename
        )
        or manifest["index_path"] != "observations.jsonl"
        or manifest["index_sha256"] != sha256(raw)
        or manifest["index_bytes"] != len(raw)
        or manifest["index_rows"] != expected["source_software_entries"]
        or manifest["identity_policy"] != "Source-observation projection; no inferred work, media, title or release identity join"
    ):
        raise ValueError(f"modified MAME source-index manifest: {filename}")
    if raw and not raw.endswith(b"\n"):
        raise ValueError(f"unterminated MAME source index: {filename}")
    records = [json.loads(line) for line in raw.splitlines()]
    if len(records) != manifest["index_rows"]:
        raise ValueError(f"MAME index record count mismatch: {filename}")
    return records, manifest


def valid_sha1(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise ValueError("malformed source media SHA-1 observation")
    return value.lower()


def mame_size(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("nonliteral MAME media size")
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
        return int(value, 16)
    if re.fullmatch(r"[0-9]+", value):
        return int(value, 10)
    raise ValueError(f"unsupported source media size: {value}")


def read_libretro(root):
    old = source_json(root / "sources/libretro-no-intro.json")
    new = pinned_manifest(root)
    if (
        old["repository_revision"] != new["repository_revision"]
        or old["source_id"] != new["source_id"]
        or old["declared_repository_license"] != new["declared_repository_license"]
        or len(old["files"]) != 10
        or len(new["platforms"]) != 65
    ):
        raise ValueError("incomplete independent Libretro source registers")
    expanded_import = {**new, "files": new["platforms"]}
    key_to_sources = defaultdict(list)
    seen_scopes = set()
    source_media = Counter()
    for scope in (
        {"register": old, "files": old["files"], "prefix": "archive/libretro-no-intro"},
        {"register": expanded_import, "files": new["platforms"], "prefix": "archive/libretro-bulk"},
    ):
        for item in scope["files"]:
            platform = item["platform"]
            if platform in seen_scopes:
                raise ValueError(f"duplicate registered Libretro scope: {platform}")
            seen_scopes.add(platform)
            path = (
                root / scope["prefix"] / (platform + ".dat")
                if scope["prefix"].endswith("libretro-no-intro")
                else root / scope["prefix"] / item["source_path"]
            )
            if path.is_symlink():
                raise ValueError(f"linked Libretro source DAT: {platform}")
            raw = path.read_bytes()
            if item.get("bytes") is not None and len(raw) != item["bytes"]:
                raise ValueError(f"Libretro source size drift: {platform}")
            parsed = import_dat(raw, scope["register"], platform)
            source_media["libretro_source_records"] += parsed["record_count"]
            source_media["libretro_media_claims"] += parsed["rom_count"]
            for game in parsed["records"]:
                for ordinal, media in enumerate(game["roms"], 1):
                    digest = valid_sha1(media.get("sha1"))
                    if digest is None:
                        continue
                    size = media.get("size")
                    if not isinstance(size, int) or size < 0:
                        raise ValueError(f"Libretro media size malformed: {platform}")
                    source_media["libretro_sha1_claims"] += 1
                    key_to_sources[digest].append({
                        "platform": platform,
                        "source_record_ordinal": game["source_ordinal"],
                        "source_media_ordinal": ordinal,
                        "source_title": game["name"],
                        "media_name": media["name"],
                        "media_size_bytes": size,
                        "source_dat_path": str(path.relative_to(root)),
                        "source_dat_blob_sha": parsed["source_blob_sha"],
                    })
    if len(seen_scopes) != 75:
        raise ValueError("expected 75 independently registered Libretro DAT sources")
    return key_to_sources, source_media


def build_expected(root=ROOT):
    register = source_register(root)
    libretro_by_sha1, source_counts = read_libretro(root)
    links = []
    size_conflicts = []
    totals = Counter()
    per_list = []
    for filename in register["files"]:
        original = verify_one(root, register, filename)
        records, manifest = verified_mame_index(root, filename, original)
        list_id = original["source_list_name"]
        list_counts = Counter()
        for ordinal, row in enumerate(records, 1):
            if (
                row["schema_version"] != 1
                or row["source"] != "MAME"
                or row["source_list"] != list_id
                or row["original_software_ordinal"] != ordinal
                or row["original_xml_sha256"] != original["original_xml_sha256"]
                or row["interpretation"] != "original-mame-cc0-source-statement-not-canonical-game-release-or-media-identity"
            ):
                raise ValueError(f"MAME indexed observation changed: {filename}:{ordinal}")
            list_counts["mame_software_records"] += 1
            for media in row["original_media_claims"]:
                list_counts["mame_media_claims"] += 1
                if media["kind"] not in ("rom", "disk"):
                    raise ValueError("unrecognized original MAME media type")
                digest = valid_sha1(media["original_media_attributes"].get("sha1"))
                if digest is None:
                    continue
                list_counts["mame_sha1_claims"] += 1
                source_size = mame_size(media["original_media_attributes"].get("size"))
                candidates = libretro_by_sha1.get(digest, ())
                for match in candidates:
                    if source_size is not None and source_size != match["media_size_bytes"]:
                        list_counts["same_sha1_size_disagreement"] += 1
                        size_conflicts.append({
                            "schema_version": 1,
                            "kind": "unresolved-mame-libretro-same-sha1-size-conflict",
                            "media_sha1": digest,
                            "mame": {
                                "source_list": list_id,
                                "software_ordinal": ordinal,
                                "software_name": row["original_software_attributes"]["name"],
                                "source_title": row["original_title"],
                                "source_media_ordinal": media["source_ordinal"],
                                "source_media_kind": media["kind"],
                                "declared_size_bytes": source_size,
                                "source_xml_sha256": row["original_xml_sha256"],
                                "source_index_sha256": manifest["index_sha256"],
                            },
                            "libretro": match,
                            "interpretation": "excluded-from-match-index-source-declared-size-conflict-not-file-or-game-identity",
                        })
                        continue
                    links.append({
                        "schema_version": 1,
                        "kind": "exact-mame-libretro-media-sha1-source-candidate",
                        "media_sha1": digest,
                        "size_corroborated": source_size is not None,
                        "mame": {
                            "source_list": list_id,
                            "software_ordinal": ordinal,
                            "software_name": row["original_software_attributes"]["name"],
                            "original_title": row["original_title"],
                            "source_media_ordinal": media["source_ordinal"],
                            "source_media_kind": media["kind"],
                            "media_name": media["original_media_attributes"].get("name"),
                            "source_size_bytes": source_size,
                            "source_xml_sha256": row["original_xml_sha256"],
                            "source_index_sha256": manifest["index_sha256"],
                            "source_index_path": str(
                                BASE / filename.removesuffix(".xml") / "observations.jsonl"
                            ),
                        },
                        "libretro": match,
                        "interpretation": "review-only-identical-media-sha1-not-verified-game-release-or-platform-identity",
                    })
                    list_counts["source_media_candidate_links"] += 1
                    if source_size is not None:
                        list_counts["size_corroborated_links"] += 1
        totals.update(list_counts)
        per_list.append({
            "source_list": list_id,
            "source_observations": dict(sorted(list_counts.items())),
            "source_index_sha256": manifest["index_sha256"],
            "original_xml_sha256": original["original_xml_sha256"],
        })
    links.sort(key=lambda row: (
        row["mame"]["source_list"],
        row["mame"]["software_ordinal"],
        row["mame"]["source_media_ordinal"],
        row["libretro"]["platform"],
        row["libretro"]["source_record_ordinal"],
        row["libretro"]["source_media_ordinal"],
    ))
    size_conflicts.sort(key=lambda row: (
        row["mame"]["source_list"],
        row["mame"]["software_ordinal"],
        row["mame"]["source_media_ordinal"],
        row["libretro"]["platform"],
        row["libretro"]["source_record_ordinal"],
        row["libretro"]["source_media_ordinal"],
    ))
    if len(links) > 200_000:
        raise ValueError("candidate pairs exceeded explicit evidence-safety ceiling")
    if totals["mame_software_records"] != 31464:
        raise ValueError("source index no longer covers 31,464 MAME software entries")
    by_platform = Counter(link["libretro"]["platform"] for link in links)
    payload = ("\n".join(compact(row) for row in links) + ("\n" if links else "")).encode("utf-8")
    disagreements = ("\n".join(compact(row) for row in size_conflicts)
                     + ("\n" if size_conflicts else "")).encode("utf-8")
    report = {
        "schema_version": 1,
        "kind": "independent-cross-source-media-sha1-exact-match-review",
        "mame_source_register": "sources/mame-softlists-v1.json",
        "libretro_base_register": "sources/libretro-no-intro.json",
        "libretro_expansion_register": "sources/bulk-expansion-v1.json",
        "mame_software_lists": len(register["files"]),
        "libretro_source_platforms": 75,
        "mame_observation_totals": dict(sorted(totals.items())),
        "libretro_observation_totals": dict(sorted(source_counts.items())),
        "exact_sha1_source_candidate_pairs": len(links),
        "distinct_matched_mame_software_records": len({
            (v["mame"]["source_list"], v["mame"]["software_ordinal"]) for v in links
        }),
        "distinct_matched_libretro_records": len({
            (v["libretro"]["platform"], v["libretro"]["source_record_ordinal"]) for v in links
        }),
        "matched_libretro_source_platform_counts": dict(sorted(by_platform.items())),
        "match_index_path": str(MATCH_BASE / "links.jsonl"),
        "match_index_sha256": sha256(payload),
        "match_index_bytes": len(payload),
        "size_disagreement_rows": len(size_conflicts),
        "size_disagreement_path": str(MATCH_BASE / "size-disagreements.jsonl"),
        "size_disagreement_sha256": sha256(disagreements),
        "size_disagreement_bytes": len(disagreements),
        "per_mame_source_list": per_list,
        "interpretation": INTERPRETATION,
    }
    return payload, disagreements, json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--build", action="store_true")
    modes.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows, disagreements, summary = build_expected()
    target = ROOT / MATCH_BASE / "links.jsonl"
    conflict_path = ROOT / MATCH_BASE / "size-disagreements.jsonl"
    report = ROOT / SUMMARY
    if args.build:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rows)
        conflict_path.write_bytes(disagreements)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(summary, encoding="utf-8")
    elif (
        not target.exists() or target.is_symlink() or target.read_bytes() != rows
        or not conflict_path.exists() or conflict_path.is_symlink()
        or conflict_path.read_bytes() != disagreements
        or not report.exists() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("cross-source SHA-1 evidence index differs from pinned originals")
    counts = json.loads(summary)
    print(
        f"verified {counts['mame_software_lists']} MAME lists, "
        f"{counts['libretro_source_platforms']} Libretro platform sources, "
        f"{counts['exact_sha1_source_candidate_pairs']} candidate media pairs"
    )


if __name__ == "__main__":
    main()
