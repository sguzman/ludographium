#!/usr/bin/env python3
"""Pin stable, noncanonical review tasks for additional third-MAME source cohort.

The original 21,712-unit queue remains unchanged. Review IDs address original
source software observations, never inferred games, releases or platforms.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from acquire_mame_softlists import ROOT, source_register
from build_source_review_units import original_review_id, compact
from reconcile_mame_v3_media import OUTPUT as MEDIA_INDEX, REPORT as MEDIA_REPORT
from reconcile_mame_v3_titles import OUTPUT as TITLE_INDEX, SUMMARY as TITLE_REPORT

OUTPUT = Path("data/reconciliation/source-review-units-v3/units.jsonl")
REPORT = Path("reports/source-review-units-v3-summary.json")
PRIOR_REPORT = Path("reports/source-review-units-v1-summary.json")
PRIOR_COUNT = 21712


def source_bytes(root, relative):
    file = root / relative
    if file.is_symlink() or not file.is_file():
        raise ValueError(f"missing or linked original source: {relative}")
    return file.read_bytes()


def pinned(root, report_file, data_file, digest_field, size_field, count_field):
    report = json.loads(source_bytes(root, report_file))
    raw = source_bytes(root, data_file)
    if (
        report["schema_version"] != 1
        or report[digest_field] != hashlib.sha256(raw).hexdigest()
        or report[size_field] != len(raw)
        or report[count_field] != len(raw.splitlines())
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError(f"changed pinned source cohort evidence: {data_file}")
    return report, raw


def build_expected(root=ROOT):
    media_report, media_raw = pinned(
        root, MEDIA_REPORT, MEDIA_INDEX,
        "candidate_sha256", "candidate_bytes", "source_media_sha1_candidate_pairs",
    )
    title_report, title_raw = pinned(
        root, TITLE_REPORT, TITLE_INDEX,
        "candidate_sha256", "candidate_bytes", "original_title_review_candidate_pairs",
    )
    prior = json.loads(source_bytes(root, PRIOR_REPORT))
    if (
        prior["source_review_units"] != PRIOR_COUNT
        or media_report["mame_source_register"] != "sources/mame-softlists-v3.json"
        or media_report["source_media_sha1_candidate_pairs"] != 127
        or title_report["original_mame_source_register"] != "sources/mame-softlists-v3.json"
        or title_report["original_title_review_candidate_pairs"] != 8
        or title_report["distinct_original_mame_software_with_title_leads"] != 6
    ):
        raise ValueError("new independent review-unit source registers diverged")
    cohort = source_register(root, "v3")
    lists = {filename.removesuffix(".xml") for filename in cohort["files"]}
    if len(lists) != 4:
        raise ValueError("third original MAME cohort lacks four lists")
    prior_lists = {
        name.removesuffix(".xml")
        for cohort_name in ("v1", "v2")
        for name in source_register(root, cohort_name)["files"]
    }
    if lists & prior_lists:
        raise ValueError("third-cohort review units collide with older source scopes")
    groups = {}
    xml_by_list = {}
    blob_by_scope = {}
    for kind, raw in (("media", media_raw), ("title", title_raw)):
        for ordinal, line in enumerate(raw.splitlines(), 1):
            record = json.loads(line)
            mame, libretro = record["mame"], record["libretro"]
            if kind == "media":
                if (
                    record["kind"] != "review-only-v3-mame-libretro-exact-media-sha1-candidate"
                    or not record["size_corroborated"]
                    or mame["original_declared_size_bytes"] !=
                    libretro["original_media_size_bytes"]
                ):
                    raise ValueError("invalid separate v3 SHA1 source claim")
                software_ordinal = mame["software_ordinal"]
                xml_sha = mame["source_xml_sha256"]
                title = mame["original_title"]
                libretro_ordinal = libretro["source_record_ordinal"]
                libretro_title = libretro["original_title"]
                blob_sha = libretro["source_dat_blob_sha"]
            else:
                if (
                    record["kind"] != "third-mame-cohort-review-only-exact-title-evidence"
                    or mame["source_cohort"] != "v3"
                    or record["scope_pair_distinct_mame_sha1_supported_records"] < 3
                ):
                    raise ValueError("invalid separate v3 title source claim")
                software_ordinal = mame["original_software_ordinal"]
                xml_sha = mame["source_xml_sha256"]
                title = mame["original_title"]
                libretro_ordinal = libretro["original_source_ordinal"]
                libretro_title = libretro["original_title"]
                blob_sha = libretro["original_git_blob_sha"]
            listname = mame["source_list"]
            platform = libretro["platform"]
            if listname not in lists:
                raise ValueError("v3 source lead refers to an earlier MAME register")
            if (
                listname in xml_by_list and xml_by_list[listname] != xml_sha
                or platform in blob_by_scope and blob_by_scope[platform] != blob_sha
            ):
                raise ValueError("original source digest changed across review claims")
            xml_by_list[listname] = xml_sha
            blob_by_scope[platform] = blob_sha
            key = (listname, software_ordinal)
            if key not in groups:
                groups[key] = {
                    "mame": {
                        "source_list": listname,
                        "original_software_ordinal": software_ordinal,
                        "original_title": title,
                        "original_xml_sha256": xml_sha,
                        "source_license": "CC0-1.0",
                        "source_cohort": "v3",
                    },
                    "media_ordinals": [],
                    "title_ordinals": [],
                    "targets": {},
                }
            group = groups[key]
            if (
                group["mame"]["original_title"] != title
                or group["mame"]["original_xml_sha256"] != xml_sha
            ):
                raise ValueError("original source-title evidence changed inside review unit")
            target_key = (platform, libretro_ordinal)
            target = group["targets"].setdefault(target_key, {
                "platform": platform,
                "original_source_ordinal": libretro_ordinal,
                "original_title": libretro_title,
                "original_git_blob_sha": blob_sha,
                "source_license": "CC-BY-SA-4.0",
                "has_equal_sha1_and_size_evidence": False,
                "has_exact_normalized_title_review_evidence": False,
            })
            if (
                target["original_title"] != libretro_title
                or target["original_git_blob_sha"] != blob_sha
            ):
                raise ValueError("original Libretro target evidence changed within a unit")
            if kind == "media":
                group["media_ordinals"].append(ordinal)
                target["has_equal_sha1_and_size_evidence"] = True
            else:
                group["title_ordinals"].append(ordinal)
                target["has_exact_normalized_title_review_evidence"] = True
    units = []
    class_counts = Counter()
    ambiguities = Counter()
    for (listname, source_ordinal), group in sorted(groups.items()):
        targets = [group["targets"][key] for key in sorted(group["targets"])]
        media = group["media_ordinals"]
        titles = group["title_ordinals"]
        if not targets or (media and titles):
            raise ValueError("accepted identity or conflated different review source types")
        ambiguous = len(targets) > 1
        classification = (
            "multiple-media-supported-source-targets" if media and ambiguous
            else "single-media-supported-source-target" if media
            else "multiple-exact-title-source-targets" if ambiguous
            else "single-exact-title-source-target"
        )
        class_counts[classification] += 1
        ambiguities["ambiguous_source_units" if ambiguous else "single_target_source_units"] += 1
        units.append({
            "schema_version": 1,
            "kind": "original-source-review-unit",
            "stable_review_id": original_review_id(
                listname, group["mame"]["original_xml_sha256"], source_ordinal
            ),
            "mame": group["mame"],
            "candidate_libretro_targets": targets,
            "distinct_candidate_libretro_target_count": len(targets),
            "multiple_source_target_alternatives": ambiguous,
            "media_evidence_jsonl_source_ordinals": media,
            "title_evidence_jsonl_source_ordinals": titles,
            "source_review_priority_class": classification,
            "review_status": "unreviewed-original-evidence",
            "interpretation": "review-task-only-not-accepted-game-or-release-identity",
        })
    identifiers = [unit["stable_review_id"] for unit in units]
    if (
        len(identifiers) != len(set(identifiers))
        or len(units) != 133
        or sum(len(unit["media_evidence_jsonl_source_ordinals"]) for unit in units) != 127
        or sum(len(unit["title_evidence_jsonl_source_ordinals"]) for unit in units) != 8
        or sum(bool(unit["media_evidence_jsonl_source_ordinals"]) for unit in units) != 127
        or sum(bool(unit["title_evidence_jsonl_source_ordinals"]) for unit in units) != 6
    ):
        raise ValueError("third-cohort source review lost or duplicated observations")
    data = ("\n".join(compact(unit) for unit in units)
            + ("\n" if units else "")).encode("utf-8")
    summary = {
        "schema_version": 1,
        "kind": "additive-third-mame-cohort-stable-source-review-queue",
        "prior_original_source_review_report": str(PRIOR_REPORT),
        "unchanged_prior_source_review_units": PRIOR_COUNT,
        "mame_source_cohort": "v3",
        "source_media_report": str(MEDIA_REPORT),
        "source_media_index_sha256": media_report["candidate_sha256"],
        "source_title_report": str(TITLE_REPORT),
        "source_title_index_sha256": title_report["candidate_sha256"],
        "original_media_candidate_pairs": 127,
        "original_title_candidate_pairs": 8,
        "additional_original_review_units": len(units),
        "cumulative_separate_source_review_units": PRIOR_COUNT + len(units),
        "source_review_priority_class_counts": dict(sorted(class_counts.items())),
        "source_review_ambiguity_counts": dict(sorted(ambiguities.items())),
        "review_index_path": str(OUTPUT),
        "review_index_sha256": hashlib.sha256(data).hexdigest(),
        "review_index_bytes": len(data),
        "interpretation": (
            "Stable IDs identify independent third-cohort original source "
            "observations as review tasks only, not canonical game or release "
            "identities. Older pinned review units remain immutable."
        ),
    }
    return data, json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original, summary = build_expected()
    path, report = ROOT / OUTPUT, ROOT / REPORT
    if args.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original)
        report.write_text(summary, encoding="utf-8")
    elif (
        not path.is_file() or path.is_symlink() or path.read_bytes() != original
        or not report.is_file() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("independently pinned third-cohort review queue changed")
    metadata = json.loads(summary)
    print(
        f"verified {metadata['additional_original_review_units']} additive v3 "
        "source-observation review units"
    )


if __name__ == "__main__":
    main()
