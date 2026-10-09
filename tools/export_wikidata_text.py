#!/usr/bin/env python3
"""Project pinned Wikidata source evidence into compact, Git-reviewable JSONL.

This exports TEXT, not a binary database. It never changes the original source
snapshot, invents identities, or merges distinct platform observations.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_SHA256 = "db9d4c66041de776438b4316b34e1c648671889aea944efc6268446252f68734"
QID = re.compile(r"Q[1-9][0-9]*\Z")
PLATFORM = re.compile(r"[a-z0-9]+\Z")
SOURCE = "https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-source-data-v1.6.0.json"


def as_jsonl(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def project(snapshot_bytes):
    actual = hashlib.sha256(snapshot_bytes).hexdigest()
    if actual != SNAPSHOT_SHA256:
        raise ValueError("pinned Wikidata snapshot SHA-256 mismatch")
    snap = json.loads(snapshot_bytes)
    if snap.get("kind") != "wikidata-console-source-snapshot" or snap.get("source_license") != "CC0-1.0":
        raise ValueError("unrecognized Wikidata source snapshot")
    exports = {}
    items_total = dates_total = source_rows_total = 0
    part_info = []
    for part in snap["parts"]:
        platform = part["platform"]
        if not PLATFORM.fullmatch(platform) or platform in exports:
            raise ValueError("invalid or duplicate source platform")
        raw = part["raw_response"].encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != part["response_sha256"]:
            raise ValueError("Wikidata platform response checksum mismatch")
        rows = json.loads(raw)["results"]["bindings"]
        if len(rows) != part["row_count"]:
            raise ValueError("source response row count changed")
        merged = {}
        for row in rows:
            uri = row["item"]["value"]
            qid = uri.rsplit("/", 1)[-1]
            if not QID.fullmatch(qid) or not uri.startswith(("http://www.wikidata.org/entity/", "https://www.wikidata.org/entity/")):
                raise ValueError("invalid Wikidata entity URI")
            target = merged.setdefault(qid, {"qid": qid, "english_label": None, "dates": []})
            label = row.get("label", {}).get("value")
            if label is not None:
                if target["english_label"] is not None and target["english_label"] != label:
                    raise ValueError("conflicting source item labels")
                target["english_label"] = label
            if "date" in row:
                source_date = row["date"]
                recorded = {"type": source_date["type"], "value": source_date["value"]}
                for key in ("datatype", "xml:lang"):
                    if key in source_date:
                        recorded[key] = source_date[key]
                if recorded not in target["dates"]:
                    target["dates"].append(recorded)
        if len(merged) != part["distinct_items"]:
            raise ValueError("Wikidata item inventory mismatch")
        for value in merged.values():
            value["dates"].sort(key=lambda d: (d["type"], d["value"], d.get("datatype", ""), d.get("xml:lang", "")))
        lines = "".join(as_jsonl(merged[qid]) for qid in sorted(merged, key=lambda qid: int(qid[1:])))
        exports[platform + ".jsonl"] = lines.encode("utf-8")
        items_total += len(merged)
        source_rows_total += len(rows)
        dates_total += sum(1 for row in rows if row.get("date", {}).get("type") in ("literal", "typed-literal"))
        part_info.append({
            "platform": platform,
            "wikidata_platform": part["wikidata_platform"],
            "source_query_sha256": part["query_sha256"],
            "source_response_sha256": part["response_sha256"],
            "received_at_utc": part["received_at_utc"],
            "source_rows": len(rows),
            "distinct_items": len(merged),
            "text_path": platform + ".jsonl",
            "text_sha256": hashlib.sha256(exports[platform + ".jsonl"]).hexdigest(),
            "text_bytes": len(exports[platform + ".jsonl"]),
        })
    if (len(exports), items_total, dates_total, source_rows_total) != (16, 15868, 29333, 30341):
        raise ValueError("unexpected pinned source coverage")
    manifest = {
        "schema_version": 1,
        "kind": "wikidata-console-text-corpus",
        "source": "Wikidata CC0 structured data",
        "source_snapshot_sha256": SNAPSHOT_SHA256,
        "source_snapshot_url": SOURCE,
        "source_revision": "2026-10-09-pinned-sparql-snapshot",
        "identity_policy": "Items and dates are attributed claims, never canonical matches to Libretro source records.",
        "platform_collections": len(exports),
        "item_platform_observations": items_total,
        "literal_date_claims": dates_total,
        "original_query_rows": source_rows_total,
        "files": part_info,
    }
    exports["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return exports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data/wikidata/v1")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--build", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    expected = project(args.snapshot.read_bytes())
    if args.build:
        args.output.mkdir(parents=True, exist_ok=True)
        for path, raw in expected.items():
            (args.output / path).write_bytes(raw)
    else:
        found = {p.name for p in args.output.iterdir() if p.is_file()}
        if found != set(expected):
            raise ValueError("text corpus file inventory differs")
        for name, raw in expected.items():
            if (args.output / name).read_bytes() != raw:
                raise ValueError(f"non-reproducible text source: {name}")
    print(f"PASS: {len(expected)-1} text platform files, 15,868 item observations,"
          " 29,333 literal date claims, all source checksums validated")


if __name__ == "__main__":
    main()
