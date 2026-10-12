#!/usr/bin/env python3
"""Audit differences in original game-title literals across exact media matches.

An identical source SHA-1/byte-size assertion is media evidence, not an
accepted game identity. Different display titles are review observations,
not necessarily catalog errors: localization, naming and editions vary.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from reconcile_mame_titles import normalized_title

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("data/reconciliation/mame-libretro-sha1-v1/links.jsonl")
SOURCE_REPORT = Path("reports/mame-libretro-media-sha1-v1-summary.json")
OUTPUT = Path("data/reconciliation/mame-libretro-title-variance-v1/differences.jsonl")
REPORT = Path("reports/mame-libretro-media-title-variance-v1.json")
KINDS = ("exact-original-title", "equal-after-conservative-normalization",
         "one-title-contained-in-another", "different-normalized-titles",
         "missing-source-title")
POLICY = (
    "Comparison of original attributed display-title literals on exact "
    "source-reported SHA1-and-byte-size media evidence. Differences can "
    "represent localization, descriptive expansions, naming conventions, "
    "edition variants or provider mistakes. Neither matching nor differing "
    "names establish, refute, merge or correct game/release identities."
)


def source_bytes(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"source symlink not accepted: {relative}")
    return path.read_bytes()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def classification(a, b):
    """Strict observations, not fuzzy correspondence decisions."""
    if not isinstance(a, str) or not isinstance(b, str) or not a.strip() or not b.strip():
        return "missing-source-title"
    if a == b:
        return "exact-original-title"
    norm_a, norm_b = normalized_title(a), normalized_title(b)
    if norm_a is None or norm_b is None:
        return "missing-source-title"
    if norm_a == norm_b:
        return "equal-after-conservative-normalization"
    # A full original display name can contain another title as a phrase.
    # This is not an identity assertion, nor is the substring deleted.
    if min(len(norm_a), len(norm_b)) >= 5 and (
        norm_a.startswith(norm_b + " ~ ")
        or norm_b.startswith(norm_a + " ~ ")
        or norm_a.endswith(" ~ " + norm_b)
        or norm_b.endswith(" ~ " + norm_a)
    ):
        return "one-title-contained-in-another"
    return "different-normalized-titles"


def build_expected(root=ROOT):
    report = json.loads(source_bytes(root, SOURCE_REPORT))
    raw = source_bytes(root, SOURCE)
    if (
        report["schema_version"] != 1
        or report["kind"] != "independent-cross-source-media-sha1-exact-match-review"
        or report["mame_software_lists"] != 65
        or report["libretro_source_platforms"] != 75
        or report["match_index_path"] != str(SOURCE)
        or report["match_index_sha256"] != hashlib.sha256(raw).hexdigest()
        or report["match_index_bytes"] != len(raw)
        or (raw and not raw.endswith(b"\n"))
    ):
        raise ValueError("pinned media evidence has been altered")
    totals = Counter()
    scope = defaultdict(Counter)
    by_mame = defaultdict(Counter)
    by_libretro = defaultdict(Counter)
    mismatches = []
    seen = 0
    for ordinal, line in enumerate(raw.splitlines(), 1):
        source = json.loads(line)
        mame = source["mame"]
        libretro = source["libretro"]
        if (
            source["schema_version"] != 1
            or source["kind"] != "exact-mame-libretro-media-sha1-source-candidate"
            or source["interpretation"] != "review-only-identical-media-sha1-not-verified-game-release-or-platform-identity"
            or not source["size_corroborated"]
            or mame["source_size_bytes"] != libretro["media_size_bytes"]
            or not isinstance(source["media_sha1"], str)
            or len(source["media_sha1"]) != 40
        ):
            raise ValueError(f"source fingerprint or identity policy drift at row {ordinal}")
        first, second = mame["original_title"], libretro["source_title"]
        kind = classification(first, second)
        totals[kind] += 1
        scope[(mame["source_list"], libretro["platform"])][kind] += 1
        by_mame[mame["source_list"]][kind] += 1
        by_libretro[libretro["platform"]][kind] += 1
        seen += 1
        if kind not in ("exact-original-title", "equal-after-conservative-normalization"):
            mismatches.append({
                "schema_version": 1,
                "kind": "source-name-variance-on-equal-sha1-media-claims",
                "source_media_evidence_row": ordinal,
                "source_media_sha1": source["media_sha1"],
                "source_media_size_bytes": mame["source_size_bytes"],
                "variance_class": kind,
                "mame": {
                    "source_list": mame["source_list"],
                    "software_ordinal": mame["software_ordinal"],
                    "original_title": first,
                    "source_xml_sha256": mame["source_xml_sha256"],
                    "source_media_ordinal": mame["source_media_ordinal"],
                },
                "libretro": {
                    "platform": libretro["platform"],
                    "source_record_ordinal": libretro["source_record_ordinal"],
                    "original_title": second,
                    "source_dat_blob_sha": libretro["source_dat_blob_sha"],
                    "source_media_ordinal": libretro["source_media_ordinal"],
                },
                "interpretation": "review-only-display-name-variance-not-a-canonical-identity-error",
            })
    if seen != report["exact_sha1_source_candidate_pairs"] or seen != 19025:
        raise ValueError("exact source media claims have been omitted")
    if sum(totals.values()) != seen:
        raise ValueError("source-variance category totals inconsistent")
    original = ("\n".join(compact(row) for row in mismatches)
                + ("\n" if mismatches else "")).encode("utf-8")
    def distributions(values, first, second):
        return [
            {first: key[0], second: key[1],
             "evidence_rows": sum(counter.values()),
             "source_name_variance_counts": dict(sorted(counter.items()))}
            for key, counter in sorted(values.items())
        ]
    return original, json.dumps({
        "schema_version": 1,
        "kind": "original-source-name-variance-on-exact-media-sha1-evidence",
        "input_source_report": str(SOURCE_REPORT),
        "input_media_sha1_index": str(SOURCE),
        "input_media_sha1_index_sha256": report["match_index_sha256"],
        "input_media_sha1_evidence_rows": seen,
        "source_name_classes": dict(sorted(totals.items())),
        "equal_original_or_normalized_title_rows": (
            totals["exact-original-title"]
            + totals["equal-after-conservative-normalization"]
        ),
        "display_name_variance_rows": len(mismatches),
        "variance_evidence_path": str(OUTPUT),
        "variance_evidence_sha256": hashlib.sha256(original).hexdigest(),
        "variance_evidence_bytes": len(original),
        "source_scope_pair_statistics": distributions(scope, "mame_list", "libretro_platform"),
        "mame_source_list_statistics": [
            {"mame_list": key, "evidence_rows": sum(counter.values()),
             "source_name_variance_counts": dict(sorted(counter.items()))}
            for key, counter in sorted(by_mame.items())
        ],
        "libretro_source_scope_statistics": [
            {"libretro_platform": key, "evidence_rows": sum(counter.values()),
             "source_name_variance_counts": dict(sorted(counter.items()))}
            for key, counter in sorted(by_libretro.items())
        ],
        "interpretation": POLICY,
    }, ensure_ascii=False, indent=2) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original, summary = build_expected()
    source = ROOT / OUTPUT
    report = ROOT / REPORT
    if args.write:
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(original)
        report.write_text(summary, encoding="utf-8")
    elif (
        not source.is_file() or source.is_symlink()
        or source.read_bytes() != original
        or not report.is_file() or report.is_symlink()
        or report.read_text(encoding="utf-8") != summary
    ):
        parser.error("original source title-variance audit differs from pinned evidence")
    manifest = json.loads(summary)
    print(
        f"verified {manifest['input_media_sha1_evidence_rows']} SHA1 source pairs; "
        f"{manifest['display_name_variance_rows']} title-variance observations"
    )


if __name__ == "__main__":
    main()
