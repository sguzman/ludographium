#!/usr/bin/env python3
"""Pin independent entity-search responses for unmapped console/accessory scopes."""
import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = "sources/wikidata-platform-discovery-v1.json"
BASE = Path("data/wikidata/platform-discovery-v1")
QID = re.compile(r"Q[1-9][0-9]*\Z")
USER_AGENT = (
    "Ludographium/1.0 (https://github.com/sguzman/ludographium; "
    "unverified Wikidata CC0 platform-source research)"
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sources(root):
    config = read_json(root / REGISTER)
    gaps = read_json(root / config["source_gap_report"])
    if (config["schema_version"] != 1
            or config["kind"] != "unverified-wikidata-platform-entity-search-hints"
            or config["provider"] != "Wikidata"
            or config["license"] != "CC0-1.0"
            or config["search_language"] != "en"
            or config["result_limit"] != 25):
        raise ValueError("unexpected discovery source register")
    expected = {
        entry["platform"]
        for entry in gaps["gaps"]
        if entry["review_class"] == "unregistered-platform-or-accessory"
    }
    declared = [target["platform"] for target in config["targets"]]
    if len(declared) != len(set(declared)) or set(declared) != expected:
        raise ValueError("discovery target list differs from independently audited gaps")
    if any(not target["search_hint"].strip() for target in config["targets"]):
        raise ValueError("empty entity-search hint")
    return config


def request_url(config, hint):
    params = {
        "action": "wbsearchentities",
        "format": "json",
        "formatversion": "2",
        "language": config["search_language"],
        "limit": str(config["result_limit"]),
        "search": hint,
        "type": "item",
    }
    return config["endpoint"] + "?" + urllib.parse.urlencode(params)


def verify_response(raw, limit):
    response = json.loads(raw)
    candidates = response.get("search")
    if not isinstance(candidates, list) or len(candidates) > limit:
        raise ValueError("unrecognized or oversized Wikidata entity-search response")
    ids = []
    for value in candidates:
        if not isinstance(value, dict) or not isinstance(value.get("id"), str):
            raise ValueError("non-entity search result")
        if QID.fullmatch(value["id"]) is None:
            raise ValueError("invalid Wikidata search result QID")
        ids.append(value["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate entity-search result")
    return len(ids)


def verify_capture(root, config, target):
    folder = root / BASE / target["platform"]
    manifest_path = folder / "manifest.json"
    raw_path = folder / "response.json"
    if folder.is_symlink() or manifest_path.is_symlink() or raw_path.is_symlink():
        raise ValueError("symbolic link in pinned platform-search source")
    manifest = read_json(manifest_path)
    raw = raw_path.read_bytes()
    expected_url = request_url(config, target["search_hint"])
    if (manifest.get("schema_version") != 1
            or manifest.get("source") != "Wikidata"
            or manifest.get("license") != "CC0-1.0"
            or manifest.get("source_register") != REGISTER
            or manifest.get("platform") != target["platform"]
            or manifest.get("search_hint") != target["search_hint"]
            or manifest.get("request_url") != expected_url
            or manifest.get("source_response_path") != "response.json"
            or manifest.get("source_response_bytes") != len(raw)
            or manifest.get("source_response_sha256") != sha256(raw)
            or manifest.get("review_status") != "unverified-platform-entity-search-results"
            or not manifest.get("captured_at_utc")):
        raise ValueError(f"platform candidate-source manifest mismatch: {target['platform']}")
    count = verify_response(raw, config["result_limit"])
    if count != manifest.get("source_candidate_rows"):
        raise ValueError("entity-search source candidate count mismatch")
    return count


def acquire(root, config, target):
    folder = root / BASE / target["platform"]
    if (folder / "manifest.json").exists():
        verify_capture(root, config, target)
        return False
    url = request_url(config, target["search_hint"])
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 200:
            raise ValueError(f"Wikidata source HTTP status: {response.status}")
        raw = response.read(3_000_001)
    if len(raw) > 3_000_000:
        raise ValueError("Wikidata entity-search response exceeds 3MB")
    count = verify_response(raw, config["result_limit"])
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "response.json").write_bytes(raw)
    manifest = {
        "schema_version": 1,
        "source": "Wikidata",
        "license": "CC0-1.0",
        "source_register": REGISTER,
        "platform": target["platform"],
        "search_hint": target["search_hint"],
        "request_url": url,
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_response_path": "response.json",
        "source_response_sha256": sha256(raw),
        "source_response_bytes": len(raw),
        "source_candidate_rows": count,
        "review_status": "unverified-platform-entity-search-results",
        "policy": "Unverified entity-search evidence only; no accepted P400 or game identity",
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    config = sources(ROOT)
    present = 0
    created = 0
    for target in config["targets"]:
        manifest = ROOT / BASE / target["platform"] / "manifest.json"
        if args.check:
            if manifest.exists():
                verify_capture(ROOT, config, target)
                present += 1
        else:
            if acquire(ROOT, config, target):
                created += 1
                print(f"captured {target['platform']}", flush=True)
                time.sleep(2)
            present += 1
    print(
        f"pinned entity-search partitions verified={present}, "
        f"new={created}, targets={len(config['targets'])}"
    )


if __name__ == "__main__":
    main()
