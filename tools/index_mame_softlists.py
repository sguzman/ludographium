#!/usr/bin/env python3
"""Index all pinned MAME software-list XML source records without joining identities."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from acquire_mame_softlists import (
    BASE as ORIGINAL_BASE,
    BASE_V2 as ORIGINAL_BASE_V2,
    BASE_V3 as ORIGINAL_BASE_V3,
    BASE_V4 as ORIGINAL_BASE_V4,
    ROOT,
    REPORT as ORIGINAL_REPORT,
    REPORT_V2 as ORIGINAL_REPORT_V2,
    REPORT_V3 as ORIGINAL_REPORT_V3,
    REPORT_V4 as ORIGINAL_REPORT_V4,
    source_register,
    verify_one,
)

INDEX_BASE = Path("data/mame/software-observations-v1")
SUMMARY = Path("reports/mame-software-observations-v1-summary.json")
INDEX_BASE_V2 = Path("data/mame/software-observations-v2")
SUMMARY_V2 = Path("reports/mame-software-observations-v2-summary.json")
INDEX_BASE_V3 = Path("data/mame/software-observations-v3")
SUMMARY_V3 = Path("reports/mame-software-observations-v3-summary.json")
INDEX_BASE_V4 = Path("data/mame/software-observations-v4")
SUMMARY_V4 = Path("reports/mame-software-observations-v4-summary.json")
FIELDS = ("software_entries", "rom_sha1_claims", "disk_sha1_claims",
          "entries_with_year", "entries_with_publisher", "entries_with_serial")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def original_claims(xml, listname, source_sha, original_relative):
    parsed = ET.fromstring(xml)
    if parsed.tag != "softwarelist" or parsed.attrib.get("name") != listname:
        raise ValueError("software list identity drifted from original source")
    claims = []
    for ordinal, entry in enumerate(parsed.findall("./software"), 1):
        if not entry.attrib.get("name"):
            raise ValueError("MAME source item without original software ID")
        infos = [dict(el.attrib) for el in entry.findall("./info")]
        shared_features = [dict(el.attrib) for el in entry.findall("./sharedfeat")]
        media = []
        for part in entry.findall("./part"):
            for area in part:
                if area.tag not in {"dataarea", "diskarea"}:
                    continue
                for element in area:
                    if element.tag not in {"rom", "disk"}:
                        continue
                    media.append({
                        "source_ordinal": len(media) + 1,
                        "kind": element.tag,
                        "part_attributes": dict(part.attrib),
                        "area_attributes": dict(area.attrib),
                        "original_media_attributes": dict(element.attrib),
                    })
        claims.append({
            "schema_version": 1,
            "source": "MAME",
            "source_list": listname,
            "original_xml_path": original_relative,
            "original_xml_sha256": source_sha,
            "original_software_ordinal": ordinal,
            "original_software_attributes": dict(entry.attrib),
            "original_title": entry.findtext("description"),
            "original_year_literal": entry.findtext("year"),
            "original_publisher_literal": entry.findtext("publisher"),
            "original_info_attributes": infos,
            "original_shared_feature_attributes": shared_features,
            "original_media_claims": media,
            "interpretation": "original-mame-cc0-source-statement-not-canonical-game-release-or-media-identity",
        })
    return claims


def index_one(root, filename, raw_stats, cohort="v1"):
    source_base = {
        "v1": ORIGINAL_BASE, "v2": ORIGINAL_BASE_V2, "v3": ORIGINAL_BASE_V3,
        "v4": ORIGINAL_BASE_V4,
    }[cohort]
    index_base = {
        "v1": INDEX_BASE, "v2": INDEX_BASE_V2, "v3": INDEX_BASE_V3,
        "v4": INDEX_BASE_V4,
    }[cohort]
    base = source_base / filename.removesuffix(".xml")
    original = (root / base / filename).read_bytes()
    claims = original_claims(
        original,
        raw_stats["source_list_name"],
        raw_stats["original_xml_sha256"],
        str(base / filename),
    )
    if len(claims) != raw_stats["source_software_entries"]:
        raise ValueError(f"original software count differs: {filename}")
    rows = {
        "software_entries": len(claims),
        "rom_sha1_claims": sum(
            bool(media["original_media_attributes"].get("sha1"))
            for claim in claims for media in claim["original_media_claims"]
            if media["kind"] == "rom"
        ),
        "disk_sha1_claims": sum(
            bool(media["original_media_attributes"].get("sha1"))
            for claim in claims for media in claim["original_media_claims"]
            if media["kind"] == "disk"
        ),
        "entries_with_year": sum(claim["original_year_literal"] is not None for claim in claims),
        "entries_with_publisher": sum(claim["original_publisher_literal"] is not None for claim in claims),
        "entries_with_serial": sum(
            any(info.get("name") == "serial" for info in claim["original_info_attributes"])
            for claim in claims
        ),
    }
    equivalence = {
        "rom_sha1_claims": "source_rom_sha1_observations",
        "disk_sha1_claims": "source_disk_sha1_observations",
        "entries_with_year": "source_year_observations",
        "entries_with_publisher": "source_publisher_observations",
        "entries_with_serial": "source_serial_observations",
    }
    for here, source in equivalence.items():
        if rows[here] != raw_stats[source]:
            raise ValueError(f"original MAME {here} count differs: {filename}")
    payload = ("\n".join(compact(claim) for claim in claims) + "\n").encode("utf-8")
    indexdir = index_base / filename.removesuffix(".xml")
    manifest = {
        "schema_version": 1,
        "source": "MAME",
        "license": "CC0-1.0",
        "original_source_manifest": str(base / "manifest.json"),
        "original_xml_sha256": raw_stats["original_xml_sha256"],
        "original_source_list": raw_stats["source_list_name"],
        "original_xml_path": str(base / filename),
        "index_path": "observations.jsonl",
        "index_sha256": digest(payload),
        "index_bytes": len(payload),
        "index_rows": len(claims),
        "source_observation_counts": rows,
        "identity_policy": "Source-observation projection; no inferred work, media, title or release identity join",
    }
    return indexdir, manifest, payload


def build_expected(root=ROOT, cohort="v1"):
    register = source_register(root, cohort)
    manifests = []
    totals = {field: 0 for field in FIELDS}
    for filename in register["files"]:
        source = verify_one(root, register, filename)
        indexdir, index, payload = index_one(root, filename, source, cohort)
        manifests.append((indexdir, index, payload))
        for field in FIELDS:
            totals[field] += index["source_observation_counts"][field]
    if (
        len(manifests) != {"v1": 49, "v2": 16, "v3": 4, "v4": 8}[cohort]
        or (cohort == "v1" and totals["software_entries"] != 31464)
        or (cohort in ("v2", "v3", "v4") and totals["software_entries"] == 0)
    ):
        raise ValueError("incomplete original MAME source index")
    summary = {
        "schema_version": 1,
        "kind": "independent-cc0-mame-software-entry-projection",
        "source_register": f"sources/mame-softlists-{cohort}.json",
        "original_capture_summary": str({
            "v1": ORIGINAL_REPORT,
            "v2": ORIGINAL_REPORT_V2,
            "v3": ORIGINAL_REPORT_V3,
            "v4": ORIGINAL_REPORT_V4,
        }[cohort]),
        "indexed_source_partitions": len(manifests),
        "source_observation_totals": totals,
        "partitions": [
            {
                "source_list": manifest["original_source_list"],
                "original_xml_path": manifest["original_xml_path"],
                "original_xml_sha256": manifest["original_xml_sha256"],
                "index_manifest": str(indexdir / "manifest.json"),
                "index_sha256": manifest["index_sha256"],
                "counts": manifest["source_observation_counts"],
            }
            for indexdir, manifest, _ in manifests
        ],
        "interpretation": "Exactly pinned MAME XML claims projected to independent JSONL records. Original publishers, years, titles, media SHA1/CRC, serials and regional notes are evidence, not adjudicated canonical work/release identities.",
    }
    return manifests, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--cohort", choices=["v1", "v2", "v3", "v4"], default="v1")
    args = parser.parse_args()
    manifests, summary = build_expected(cohort=args.cohort)
    report = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    for folder, manifest, payload in manifests:
        manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        jsonl_path = ROOT / folder / "observations.jsonl"
        manifest_path = ROOT / folder / "manifest.json"
        if args.build:
            jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            jsonl_path.write_bytes(payload)
            manifest_path.write_text(manifest_text, encoding="utf-8")
        elif (
            not jsonl_path.exists()
            or jsonl_path.is_symlink()
            or jsonl_path.read_bytes() != payload
            or not manifest_path.exists()
            or manifest_path.is_symlink()
            or manifest_path.read_text(encoding="utf-8") != manifest_text
        ):
            parser.error(f"stale or missing original source index: {folder}")
    destination = ROOT / {
        "v1": SUMMARY, "v2": SUMMARY_V2, "v3": SUMMARY_V3,
        "v4": SUMMARY_V4,
    }[args.cohort]
    if args.build:
        destination.write_text(report, encoding="utf-8")
    elif (
        not destination.exists()
        or destination.is_symlink()
        or destination.read_text(encoding="utf-8") != report
    ):
        parser.error("stale or missing full MAME software observation report")
    print(
        f"verified {summary['indexed_source_partitions']} original source lists "
        f"and {summary['source_observation_totals']['software_entries']} records"
    )


if __name__ == "__main__":
    main()
