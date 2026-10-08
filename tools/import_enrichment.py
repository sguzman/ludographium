#!/usr/bin/env python3
"""Preserve and resolve pinned Libretro per-field metadata observations."""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"^game \(\r?\n(.*?)^\)\s*$", re.M | re.S)
SCALAR = re.compile(r'^\s*([a-z0-9_]+)\s+"((?:\\.|[^"\\])*)"\s*$', re.I)
ROM = re.compile(r"^\s*rom\s*\(\s*crc\s+([0-9a-f]{8})\s*\)\s*$", re.I)
ROM_BEGIN = re.compile(r"^\s*rom\s*\(\s*$", re.I)
ROM_CRC = re.compile(r"^\s*crc\s+([0-9a-f]{8})\s*$", re.I)
ROM_END = re.compile(r"^\s*\)\s*$")


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def unquote(value):
    return re.sub(r'\\([\\"])', r"\1", value)


def parse_field_dat(raw, *, field):
    """Reject unsupported records; keep every observed field and original ordinal."""
    text = raw.decode("utf-8")
    blocks = list(BLOCK.finditer(text))
    starts = len(re.findall(r"^game \($", text, re.M))
    if starts != len(blocks):
        raise ValueError(f"unparsed game blocks: {len(blocks)} of {starts}")
    observations = []
    for ordinal, block in enumerate(blocks, 1):
        values = {}
        crc = None
        in_rom = False
        for line in block.group(1).splitlines():
            if not line.strip():
                continue
            if in_rom:
                if ROM_END.fullmatch(line):
                    in_rom = False
                    continue
                field = ROM_CRC.fullmatch(line)
                if field and crc is None:
                    crc = field[1].upper()
                    continue
                raise ValueError(f"unsupported multiline ROM field at {ordinal}: {line[:100]}")
            rm = ROM.fullmatch(line)
            if rm:
                if crc is not None:
                    raise ValueError(f"duplicate crc in source occurrence {ordinal}")
                crc = rm[1].upper()
                continue
            if ROM_BEGIN.fullmatch(line):
                if crc is not None:
                    raise ValueError(f"duplicate ROM at source occurrence {ordinal}")
                in_rom = True
                continue
            sm = SCALAR.fullmatch(line)
            if sm is None:
                raise ValueError(f"unsupported source line at {ordinal}: {line[:100]}")
            key = sm[1].lower()
            if key in values:
                raise ValueError(f"duplicate {key} at source occurrence {ordinal}")
            values[key] = unquote(sm[2])
        if in_rom:
            raise ValueError(f"unterminated ROM block at source occurrence {ordinal}")
        if crc is None:
            raise ValueError(f"missing crc at source occurrence {ordinal}")
        observations.append({
            "source_ordinal": ordinal,
            "crc32": crc,
            "value": values.get(field),
            "comment": values.get("comment"),
            "source_fields": values,
        })
    return observations


def import_platform(root, registry, platform):
    """Resolve to source-collection occurrences, not to inferred canonical games."""
    catalog = json.loads((root / f"generated/v1/{platform}.json").read_bytes())
    if catalog.get("kind") != "source-observations" or catalog.get("platform") != platform:
        raise ValueError(f"invalid source catalog for {platform}")
    if catalog["source_revision"] != registry["repository_revision"]:
        raise ValueError("source and enrichment snapshots differ")
    crc_index = defaultdict(list)
    for record in catalog["records"]:
        for media in record["roms"]:
            if media.get("crc32"):
                crc_index[media["crc32"].upper()].append(
                    (record["source_ordinal"], record["name"])
                )
    claims = []
    files = [f for f in registry["files"] if f["platform"] == platform]
    for f in sorted(files, key=lambda entry: entry["field"]):
        filename = root / f"archive/libretro-enrichment/{platform}/{f['field']}.dat"
        raw = filename.read_bytes()
        if blob_sha(raw) != f["git_blob_sha"]:
            raise ValueError(f"source mismatch: {filename}")
        for record in parse_field_dat(raw, field=f["field"]):
            candidates = crc_index.get(record["crc32"], [])
            if record["value"] is None:
                status, target = "missing_value", None
            elif not candidates:
                status, target = "unmatched_crc", None
            elif len(candidates) > 1:
                status, target = "ambiguous_crc", None
            elif record["comment"] is None:
                status, target = "missing_comment", None
            elif candidates[0][1] != record["comment"]:
                status, target = "comment_mismatch", None
            else:
                status, target = "matched", candidates[0][0]
            claims.append({
                "field": f["field"],
                "value": record["value"],
                "crc32": record["crc32"],
                "source_ordinal": record["source_ordinal"],
                "source_comment": record["comment"],
                "source_fields": record["source_fields"],
                "source_path": f["source_path"],
                "source_blob_sha": f["git_blob_sha"],
                "resolution": {"status": status, "base_source_ordinal": target},
            })
    counts = {}
    for claim in claims:
        status = claim["resolution"]["status"]
        counts[status] = counts.get(status, 0) + 1
    return {
        "schema_version": 1,
        "kind": "source-enrichment-claims",
        "platform": platform,
        "source_id": registry["source_id"],
        "source_revision": registry["repository_revision"],
        "base_source_id": catalog["source_id"],
        "base_source_revision": catalog["source_revision"],
        "claim_count": len(claims),
        "resolution_counts": dict(sorted(counts.items())),
        "claims": claims,
    }


def canonical_bytes(data):
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    registry = json.loads((args.root / "sources/libretro-enrichment.json").read_bytes())
    if registry.get("schema_version") != 1:
        raise ValueError("unsupported source registry")
    platforms = sorted({f["platform"] for f in registry["files"]})
    for platform in platforms:
        data = import_platform(args.root, registry, platform)
        path = args.root / f"generated/enrichment-v1/{platform}.json"
        expected = canonical_bytes(data)
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
        elif not path.exists() or path.read_bytes() != expected:
            raise SystemExit(f"FAIL: enrichment index diverges: {platform}")
        print(f"{platform}: {data['claim_count']} claims; "
              + ", ".join(f"{k}={v}" for k, v in data["resolution_counts"].items()))


if __name__ == "__main__":
    main()
