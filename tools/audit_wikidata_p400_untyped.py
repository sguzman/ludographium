#!/usr/bin/env python3
"""Offline audit of pinned, type-agnostic Wikidata P400 source captures.

The resulting entities are raw Wikidata claims, not verified video games.
No network requests or modification of original provider data.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = Path("reports/wikidata-source-coverage-matrix-v1.json")
REPORT = Path("reports/wikidata-p400-untyped-probe-audit-v1.json")
BASE = Path("data/wikidata/p400-untyped-probe-v1")
INTERPRETATION = (
    "Original direct P400 observations do not require video-game P31. "
    "Returned QIDs and P31 classes are unverified source assertions, not verified "
    "games, editions, release identities, or platform associations. A zero-row "
    "query records provider-specific noncoverage, not absence of a game library."
)


def read_json(root, relative):
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"symlinked source evidence: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def qid_from_uri(uri):
    prefix = "http://www.wikidata.org/entity/"
    alternate = "https://www.wikidata.org/entity/"
    if uri.startswith(prefix):
        value = uri[len(prefix):]
    elif uri.startswith(alternate):
        value = uri[len(alternate):]
    else:
        raise ValueError(f"non-Wikidata original QID URI: {uri}")
    if not value.startswith("Q") or not value[1:].isdigit() or value[1] == "0":
        raise ValueError(f"malformed original entity QID: {uri}")
    return value


def verified_bytes(root, folder, manifest, category, filename):
    relative = folder / filename
    path = root / relative
    if path.is_symlink():
        raise ValueError(f"symlinked original query data: {relative}")
    data = path.read_bytes()
    if (
        manifest[f"source_{category}_path"] != filename
        or manifest[f"source_{category}_bytes"] != len(data)
        or manifest[f"source_{category}_sha256"] != hashlib.sha256(data).hexdigest()
    ):
        raise ValueError(f"original source checksum or byte count changed: {relative}")
    return data


def build_report(root=ROOT):
    matrix = read_json(root, MATRIX)
    scopes = sorted(
        (
            scope for scope in matrix["registered_scopes"]
            if scope["all_four_families_empty"]
        ),
        key=lambda scope: scope["platform"],
    )
    if len(scopes) != 10:
        raise ValueError("expected exactly ten zero-yield original P400 scopes")
    parts = []
    for scope in scopes:
        platform, platform_qid = scope["platform"], scope["wikidata_platform"]
        if not platform.isascii() or not platform.isalnum() or not platform.islower():
            raise ValueError(f"unsafe original source scope: {platform}")
        folder = BASE / platform
        manifest_path = folder / "manifest.json"
        manifest = read_json(root, manifest_path)
        if (
            manifest["schema_version"] != 1
            or manifest["source"] != "Wikidata"
            or manifest["license"] != "CC0-1.0"
            or manifest["source_revision"] != "live-query-capture"
            or manifest["source_register"] != str(MATRIX)
            or manifest["platform"] != platform
            or manifest["wikidata_platform"] != platform_qid
            or manifest["query_limit"] != 20000
            or manifest["query_class"] != "direct-P400-with-optional-P31-no-game-type-inference"
            or not manifest["captured_at_utc"]
        ):
            raise ValueError(f"unexpected original probe manifest: {platform}")
        query = verified_bytes(root, folder, manifest, "query", "query.rq").decode("utf-8")
        if (
            f"?item wdt:P400 wd:{platform_qid} ." not in query
            or "OPTIONAL { ?item wdt:P31 ?itemType . }" not in query
            or "LIMIT 20000" not in query
            or "SELECT DISTINCT ?item ?itemType" not in query
        ):
            raise ValueError(f"wrong Wikidata query scope: {platform}")
        response = json.loads(
            verified_bytes(root, folder, manifest, "response", "response.json")
        )
        if response["head"]["vars"] != ["item", "itemType"]:
            raise ValueError(f"unexpected P400 source response columns: {platform}")
        bindings = response["results"]["bindings"]
        if not isinstance(bindings, list) or len(bindings) >= 20000:
            raise ValueError(f"unbounded or missing source bindings: {platform}")
        raw = verified_bytes(root, folder, manifest, "bindings", "bindings.jsonl")
        if raw and not raw.endswith(b"\n"):
            raise ValueError(f"unterminated original binding JSONL: {platform}")
        original = [json.loads(line) for line in raw.splitlines()]
        if original != bindings or len(bindings) != manifest["source_rows"]:
            raise ValueError(f"original source JSONL and response disagree: {platform}")
        items, types = set(), set()
        type_counts = Counter()
        typed = 0
        for binding in bindings:
            if binding["item"]["type"] != "uri":
                raise ValueError(f"original P400 subject not an entity URI: {platform}")
            items.add(qid_from_uri(binding["item"]["value"]))
            if "itemType" in binding:
                if binding["itemType"]["type"] != "uri":
                    raise ValueError(f"original P31 value not an entity URI: {platform}")
                types.add(qid_from_uri(binding["itemType"]["value"]))
                type_counts[binding["itemType"]["value"]] += 1
                typed += 1
        if (
            len(items) != manifest["distinct_items"]
            or typed != manifest["typed_rows"]
            or len(bindings) - typed != manifest["untyped_rows"]
            or dict(type_counts) != manifest["item_type_counts"]
        ):
            raise ValueError(f"original response source statistics disagree: {platform}")
        parts.append({
            "platform": platform,
            "wikidata_platform": platform_qid,
            "original_source_rows": len(bindings),
            "distinct_item_observations": len(items),
            "typed_rows": typed,
            "untyped_rows": len(bindings) - typed,
            "source_item_qids": sorted(items),
            "original_p31_type_qids": sorted(types),
            "source_manifest_path": str(manifest_path),
            "source_response_sha256": manifest["source_response_sha256"],
        })
    return {
        "schema_version": 1,
        "kind": "independent-wikidata-direct-p400-type-agnostic-probe-audit",
        "original_source_yield_report": str(MATRIX),
        "probed_platform_scopes": len(parts),
        "total_original_p400_bindings": sum(x["original_source_rows"] for x in parts),
        "total_distinct_item_scope_observations": sum(
            x["distinct_item_observations"] for x in parts
        ),
        "total_original_instance_type_bindings": sum(x["typed_rows"] for x in parts),
        "zero_result_scopes": [
            x["platform"] for x in parts if x["original_source_rows"] == 0
        ],
        "nonempty_scopes": [
            x["platform"] for x in parts if x["original_source_rows"] > 0
        ],
        "per_platform": parts,
        "interpretation": INTERPRETATION,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    path = ROOT / REPORT
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != payload:
            parser.error(f"pinned source audit is missing/stale: {REPORT}")
        print(f"verified {REPORT}")
    else:
        path.write_text(payload, encoding="utf-8")
        print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
