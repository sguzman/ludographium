#!/usr/bin/env python3
"""Bulk accession and offline verification of CC0 MAME console software lists.

Original XML bytes are retained, not decoded ROM/media. Counts are source
observations rather than independently verified canonical game identities.
"""
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = Path("sources/mame-softlists-v1.json")
BASE = Path("data/mame/softlists-v1")
REPORT = Path("reports/mame-softlists-v1-summary.json")
REGISTER_V2 = Path("sources/mame-softlists-v2.json")
BASE_V2 = Path("data/mame/softlists-v2")
REPORT_V2 = Path("reports/mame-softlists-v2-summary.json")
REGISTER_V3 = Path("sources/mame-softlists-v3.json")
BASE_V3 = Path("data/mame/softlists-v3")
REPORT_V3 = Path("reports/mame-softlists-v3-summary.json")


def cohort_paths(register):
    cohort = register.get("accession_cohort", "v1")
    if cohort == "v1":
        return REGISTER, BASE, REPORT
    if cohort == "v2":
        return REGISTER_V2, BASE_V2, REPORT_V2
    if cohort == "v3":
        return REGISTER_V3, BASE_V3, REPORT_V3
    raise ValueError("unsupported MAME CC0 source accession cohort")
LICENSE = re.compile(rb"license\s*:\s*CC0-1\.0\b", re.I)
NAME = re.compile(r"[a-z0-9][a-z0-9_]*\.xml\Z")
MAX_SOURCE_BYTES = 25 * 1024 * 1024
USER_AGENT = (
    "Ludographium/1.0 (https://github.com/sguzman/ludographium; "
    "CC0 video-game source evidence accession)"
)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    if path.is_symlink():
        raise ValueError(f"source file is a symlink: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def source_register(root, cohort="v1"):
    if cohort not in ("v1", "v2", "v3"):
        raise ValueError("unknown MAME source cohort")
    source_path = {
        "v1": REGISTER, "v2": REGISTER_V2, "v3": REGISTER_V3,
    }[cohort]
    register = read_json(root / source_path)
    if register.get("accession_cohort", "v1") != cohort:
        raise ValueError("source register claims a different source cohort")
    files = register["files"]
    if (
        register["schema_version"] != 1
        or register["kind"] != "independent-cc0-mame-software-list-snapshots"
        or register["source"] != "MAME"
        or register["upstream_repository"] != "mamedev/mame"
        or register["upstream_path"] != "hash"
        or register["license"] != "CC0-1.0"
        or not re.fullmatch(r"[a-f0-9]{40}", register["upstream_commit_sha"])
        or not isinstance(files, list)
        or len(files) != {"v1": 49, "v2": 16, "v3": 4}[cohort]
        or files != sorted(set(files))
        or any(not isinstance(name, str) or not NAME.fullmatch(name) for name in files)
    ):
        raise ValueError("invalid CC0 software-list source register or filenames")
    return register


def original_stats(raw):
    if not LICENSE.search(raw[:32768]):
        raise ValueError("individual MAME software list lacks a CC0-1.0 header")
    if b"<!DOCTYPE softwarelist" not in raw[:1024]:
        raise ValueError("missing software-list XML document declaration")
    root = ET.fromstring(raw)
    if root.tag != "softwarelist" or not root.attrib.get("name"):
        raise ValueError("unexpected original MAME software-list root")
    entries = root.findall("./software")
    if not entries:
        raise ValueError("empty original MAME software-list source")
    ids = [item.attrib.get("name") for item in entries]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("missing or repeated source-specific MAME software names")
    return {
        "source_list_name": root.attrib["name"],
        "source_list_description": root.attrib.get("description", ""),
        "source_software_entries": len(entries),
        "source_description_observations": sum(item.find("description") is not None for item in entries),
        "source_year_observations": sum(item.find("year") is not None for item in entries),
        "source_publisher_observations": sum(item.find("publisher") is not None for item in entries),
        "source_serial_observations": sum(
            any(info.attrib.get("name") == "serial" for info in item.findall("info"))
            for item in entries
        ),
        "source_rom_sha1_observations": sum(
            bool(rom.attrib.get("sha1"))
            for item in entries for rom in item.findall(".//rom")
        ),
        "source_disk_sha1_observations": sum(
            bool(disk.attrib.get("sha1"))
            for item in entries for disk in item.findall(".//disk")
        ),
    }


def pinned_url(register, filename):
    return (
        "https://raw.githubusercontent.com/"
        + register["upstream_repository"] + "/"
        + register["upstream_commit_sha"] + "/hash/" + filename
    )


def verify_one(root, register, filename):
    source_register_path, source_base, _ = cohort_paths(register)
    folder = root / source_base / filename.removesuffix(".xml")
    manifest = read_json(folder / "manifest.json")
    xml_path = folder / filename
    if folder.is_symlink() or xml_path.is_symlink():
        raise ValueError("symbolic link in original MAME XML source")
    raw = xml_path.read_bytes()
    stats = original_stats(raw)
    expected = {
        "schema_version": 1,
        "source": "MAME",
        "source_register": str(source_register_path),
        "upstream_commit_sha": register["upstream_commit_sha"],
        "upstream_source_path": "hash/" + filename,
        "original_source_url": pinned_url(register, filename),
        "license": "CC0-1.0",
        "original_xml_path": filename,
        "original_xml_bytes": len(raw),
        "original_xml_sha256": digest(raw),
        **stats,
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError(f"original MAME source manifest mismatch: {filename}")
    if manifest.get("source_interpretation") != "unjoined-source-observations-not-canonical-game-or-media-identities":
        raise ValueError("MAME provenance policy was removed from source manifest")
    return expected


def download(register, filename):
    url = pinned_url(register, filename)
    for attempt in range(4):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml"}
            )
            with urllib.request.urlopen(request, timeout=150) as response:
                if response.status != 200:
                    raise ValueError(f"unexpected upstream source HTTP {response.status}")
                raw = response.read(MAX_SOURCE_BYTES + 1)
            if len(raw) > MAX_SOURCE_BYTES:
                raise ValueError(f"CC0 source exceeded 25 MiB: {filename}")
            return raw
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 3:
                raise RuntimeError(f"failed original CC0 acquisition: {filename}") from exc
            time.sleep(3 * (attempt + 1))
    raise AssertionError("unreachable")


def acquire_one(root, register, filename):
    source_register_path, source_base, _ = cohort_paths(register)
    folder = root / source_base / filename.removesuffix(".xml")
    if (folder / "manifest.json").exists():
        verify_one(root, register, filename)
        return False
    raw = download(register, filename)
    stats = original_stats(raw)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / filename).write_bytes(raw)
    manifest = {
        "schema_version": 1,
        "source": "MAME",
        "source_register": str(source_register_path),
        "upstream_commit_sha": register["upstream_commit_sha"],
        "upstream_source_path": "hash/" + filename,
        "original_source_url": pinned_url(register, filename),
        "license": "CC0-1.0",
        "original_xml_path": filename,
        "original_xml_bytes": len(raw),
        "original_xml_sha256": digest(raw),
        **stats,
        "source_interpretation": "unjoined-source-observations-not-canonical-game-or-media-identities",
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True


def summary(root, register):
    source_register_path, source_base, _ = cohort_paths(register)
    records = []
    for filename in register["files"]:
        observation = verify_one(root, register, filename)
        records.append({
            "source_file": observation["upstream_source_path"],
            "source_list_name": observation["source_list_name"],
            "source_software_entries": observation["source_software_entries"],
            "source_rom_sha1_observations": observation["source_rom_sha1_observations"],
            "source_disk_sha1_observations": observation["source_disk_sha1_observations"],
            "source_year_observations": observation["source_year_observations"],
            "source_publisher_observations": observation["source_publisher_observations"],
            "source_manifest": str(
                source_base / filename.removesuffix(".xml") / "manifest.json"
            ),
            "source_sha256": observation["original_xml_sha256"],
        })
    fields = (
        "source_software_entries", "source_rom_sha1_observations",
        "source_disk_sha1_observations", "source_year_observations",
        "source_publisher_observations",
    )
    return {
        "schema_version": 1,
        "kind": "independent-cc0-mame-softlist-source-yield-report",
        "upstream_commit_sha": register["upstream_commit_sha"],
        "source_register": str(source_register_path),
        "source_license": "CC0-1.0",
        "software_list_partitions": len(records),
        "source_observation_totals": {
            field: sum(item[field] for item in records) for field in fields
        },
        "partitions": records,
        "interpretation": "Attributable original MAME source software/media observations, not verified canonical works, regions, releases, or merged Libretro identities. No game media was acquired.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--acquire", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--cohort", choices=["v1", "v2", "v3"], default="v1")
    args = parser.parse_args()
    register = source_register(ROOT, args.cohort)
    if args.acquire:
        acquired = 0
        for filename in register["files"]:
            if acquire_one(ROOT, register, filename):
                acquired += 1
                print(f"pinned CC0 original source: {filename}", flush=True)
                time.sleep(1)
        print(f"source files accessioned={acquired} verified={len(register['files'])}")
    payload = json.dumps(summary(ROOT, register), indent=2, ensure_ascii=False) + "\n"
    _, _, report_path = cohort_paths(register)
    path = ROOT / report_path
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != payload:
            parser.error(f"source yield report is missing or stale: {report_path}")
        print(f"verified all original CC0 sources and report: {report_path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        print(f"wrote original CC0 source yield report: {report_path}")


if __name__ == "__main__":
    main()
