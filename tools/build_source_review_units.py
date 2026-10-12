#!/usr/bin/env python3
"""Build an exception-oriented, stable-ID review queue from pinned source leads.

Stable IDs designate original-source review tasks, NEVER canonical works,
releases, editions, or games. Every evidence row remains review-only.
Source candidates are referred to by original JSONL ordinals rather than
duplicated or silently promoted.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT

MEDIA_INDEX = Path("data/reconciliation/mame-libretro-sha1-v1/links.jsonl")
MEDIA_REPORT = Path("reports/mame-libretro-media-sha1-v1-summary.json")
TITLE_INDEX = Path("data/reconciliation/mame-libretro-title-review-v1/candidates.jsonl")
TITLE_REPORT = Path("reports/mame-libretro-title-review-v1-summary.json")
OUTPUT = Path("data/reconciliation/source-review-units-v1/units.jsonl")
SUMMARY = Path("reports/source-review-units-v1-summary.json")
POLICY = (
    "Stable IDs name original MAME source-observation review tasks only. "
    "Even a one-target media-SHA1 source lead never becomes a verified game, "
    "work, release, regional edition or cross-provider source identity. "
    "Title leads have no authority beyond exact names in supported source scopes."
)


def source_bytes(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"linked source evidence: {relative}")
    return path.read_bytes()


def source_report(root, report_path, index_path, checksum_field, bytes_field, count_field):
    report = json.loads(source_bytes(root, report_path))
    original = source_bytes(root, index_path)
    if (
        report["schema_version"] != 1
        or report[checksum_field] != hashlib.sha256(original).hexdigest()
        or report[bytes_field] != len(original)
        or report[count_field] != len(original.splitlines())
        or (original and not original.endswith(b"\n"))
    ):
        raise ValueError(f"source evidence and manifest diverged: {index_path}")
    return report, original


def original_review_id(source_list, original_xml_sha256, software_ordinal):
    if (
        not source_list or "/" in source_list
        or len(original_xml_sha256) != 64
        or not all(c in "0123456789abcdef" for c in original_xml_sha256)
        or type(software_ordinal) is not int or software_ordinal <= 0
    ):
        raise ValueError("unsafe original MAME source review coordinates")
    identifier = f"mame-source-review-v1\0{source_list}\0{original_xml_sha256}\0{software_ordinal}"
    return "lgreview:v1:" + hashlib.sha256(identifier.encode("utf-8")).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_expected(root=ROOT):
    media_report, media_raw = source_report(
        root, MEDIA_REPORT, MEDIA_INDEX, "match_index_sha256",
        "match_index_bytes", "exact_sha1_source_candidate_pairs"
    )
    title_report, title_raw = source_report(
        root, TITLE_REPORT, TITLE_INDEX, "candidate_sha256",
        "candidate_bytes", "total_review_only_exact_title_candidates"
    )
    if (
        media_report["mame_software_lists"] != 65
        or media_report["exact_sha1_source_candidate_pairs"] != 19025
        or title_report["mame_source_list_count"] != 65
        or title_report["total_review_only_exact_title_candidates"] != 6825
    ):
        raise ValueError("source review input coverage is incomplete")
    groups = {}
    source_xml_by_list = {}
    libretro_sha_by_scope = {}
    for kind, original_rows in (("media", media_raw), ("title", title_raw)):
        for source_line, raw in enumerate(original_rows.splitlines(), 1):
            record = json.loads(raw)
            mame = record["mame"]
            libretro = record["libretro"]
            if kind == "media":
                if (
                    record["kind"] != "exact-mame-libretro-media-sha1-source-candidate"
                    or not record["size_corroborated"]
                    or not record["interpretation"].startswith("review-only")
                ):
                    raise ValueError("unknown source media evidence class")
                xml_sha = mame["source_xml_sha256"]
                original_mame_title = mame["original_title"]
                libretro_blob = libretro["source_dat_blob_sha"]
                original_libretro_title = libretro["source_title"]
                mame_ordinal = mame["software_ordinal"]
                libretro_ordinal = libretro["source_record_ordinal"]
            else:
                if (
                    record["kind"] != "review-only-exact-source-title-correspondence"
                    or record["source_scope_pair_sha1_supported_mame_records"] < 3
                    or not record["interpretation"].startswith("review-only")
                ):
                    raise ValueError("unknown source title evidence class")
                xml_sha = mame["original_source_xml_sha256"]
                original_mame_title = mame["original_title"]
                libretro_blob = libretro["original_git_blob_sha"]
                original_libretro_title = libretro["original_title"]
                mame_ordinal = mame["software_ordinal"]
                libretro_ordinal = libretro["source_ordinal"]
            scope = mame["source_list"]
            platform = libretro["platform"]
            if scope in source_xml_by_list and source_xml_by_list[scope] != xml_sha:
                raise ValueError(f"conflicting original MAME XML source digest: {scope}")
            source_xml_by_list[scope] = xml_sha
            if platform in libretro_sha_by_scope and libretro_sha_by_scope[platform] != libretro_blob:
                raise ValueError(f"conflicting original Libretro source revision: {platform}")
            libretro_sha_by_scope[platform] = libretro_blob
            original_key = (scope, mame_ordinal)
            if original_key not in groups:
                groups[original_key] = {
                    "mame": {
                        "source_list": scope,
                        "original_software_ordinal": mame_ordinal,
                        "original_title": original_mame_title,
                        "original_xml_sha256": xml_sha,
                        "source_license": "CC0-1.0",
                    },
                    "media_ordinals": [],
                    "title_ordinals": [],
                    "targets": {},
                }
            group = groups[original_key]
            if (
                group["mame"]["original_title"] != original_mame_title
                or group["mame"]["original_xml_sha256"] != xml_sha
            ):
                raise ValueError("source review evidence switches original software observation")
            target_key = (platform, libretro_ordinal)
            target = group["targets"].setdefault(target_key, {
                "platform": platform,
                "original_source_ordinal": libretro_ordinal,
                "original_title": original_libretro_title,
                "original_git_blob_sha": libretro_blob,
                "source_license": "CC-BY-SA-4.0",
                "has_equal_sha1_and_size_evidence": False,
                "has_exact_normalized_title_review_evidence": False,
            })
            if (
                target["original_title"] != original_libretro_title
                or target["original_git_blob_sha"] != libretro_blob
            ):
                raise ValueError("original Libretro target source observation changed")
            if kind == "media":
                group["media_ordinals"].append(source_line)
                target["has_equal_sha1_and_size_evidence"] = True
            else:
                group["title_ordinals"].append(source_line)
                target["has_exact_normalized_title_review_evidence"] = True
    units = []
    priority = Counter()
    ambiguity = Counter()
    for (listname, ordinal), group in sorted(groups.items()):
        source = group["mame"]
        targets = [
            group["targets"][key] for key in sorted(group["targets"])
        ]
        ambiguous = len(targets) > 1
        has_sha1 = bool(group["media_ordinals"])
        has_title = bool(group["title_ordinals"])
        if has_sha1 and has_title:
            raise ValueError("title-only source review accidentally includes hash-matched MAME record")
        if not has_sha1 and not has_title:
            raise ValueError("empty original evidence review unit")
        classification = (
            "multiple-media-supported-source-targets" if has_sha1 and ambiguous
            else "single-media-supported-source-target" if has_sha1
            else "multiple-exact-title-source-targets" if ambiguous
            else "single-exact-title-source-target"
        )
        priority[classification] += 1
        ambiguity["ambiguous_source_units" if ambiguous else "single_target_source_units"] += 1
        units.append({
            "schema_version": 1,
            "kind": "original-source-review-unit",
            "stable_review_id": original_review_id(listname, source["original_xml_sha256"], ordinal),
            "mame": source,
            "candidate_libretro_targets": targets,
            "distinct_candidate_libretro_target_count": len(targets),
            "multiple_source_target_alternatives": ambiguous,
            "media_evidence_jsonl_source_ordinals": group["media_ordinals"],
            "title_evidence_jsonl_source_ordinals": group["title_ordinals"],
            "source_review_priority_class": classification,
            "review_status": "unreviewed-original-evidence",
            "interpretation": "review-task-only-not-accepted-game-or-release-identity",
        })
    ids = [row["stable_review_id"] for row in units]
    if len(ids) != len(set(ids)):
        raise ValueError("review unit stable source IDs collided")
    if (
        sum(len(row["media_evidence_jsonl_source_ordinals"]) for row in units) != 19025
        or sum(len(row["title_evidence_jsonl_source_ordinals"]) for row in units) != 6825
        or sum(bool(row["media_evidence_jsonl_source_ordinals"]) for row in units) !=
        media_report["distinct_matched_mame_software_records"]
        or sum(bool(row["title_evidence_jsonl_source_ordinals"]) for row in units) !=
        title_report["distinct_mame_software_with_title_candidate"]
    ):
        raise ValueError("source review queue lost or merged pinned input evidence")
    raw = ("\n".join(compact(row) for row in units)
           + ("\n" if units else "")).encode("utf-8")
    report = {
        "schema_version": 1,
        "kind": "stable-source-observation-review-unit-queue",
        "source_media_report": str(MEDIA_REPORT),
        "source_media_index_sha256": media_report["match_index_sha256"],
        "source_title_report": str(TITLE_REPORT),
        "source_title_index_sha256": title_report["candidate_sha256"],
        "media_candidate_rows": 19025,
        "title_candidate_rows": 6825,
        "original_mame_records_with_media_evidence": media_report[
            "distinct_matched_mame_software_records"
        ],
        "original_mame_records_with_title_only_evidence": title_report[
            "distinct_mame_software_with_title_candidate"
        ],
        "source_review_units": len(units),
        "source_review_priority_class_counts": dict(sorted(priority.items())),
        "source_review_ambiguity_counts": dict(sorted(ambiguity.items())),
        "stable_review_id_specification": (
            "lgreview:v1:sha256(UTF-8('mame-source-review-v1\\0'"
            "+source_list+'\\0'+original_xml_sha256+'\\0'+decimal_source_ordinal))"
        ),
        "review_index_path": str(OUTPUT),
        "review_index_sha256": hashlib.sha256(raw).hexdigest(),
        "review_index_bytes": len(raw),
        "interpretation": POLICY,
    }
    return raw, json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw, report = build_expected()
    target, summary = ROOT / OUTPUT, ROOT / SUMMARY
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        summary.write_text(report, encoding="utf-8")
    elif (
        not target.exists() or target.is_symlink() or target.read_bytes() != raw
        or not summary.exists() or summary.is_symlink()
        or summary.read_text(encoding="utf-8") != report
    ):
        parser.error("stale/unverified source review queue and manifest")
    result = json.loads(report)
    print(f"verified {result['source_review_units']} stable-ID source review units")


if __name__ == "__main__":
    main()
