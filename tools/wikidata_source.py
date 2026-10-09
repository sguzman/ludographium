#!/usr/bin/env python3
"""Acquire one CC0 Wikidata source snapshot by platform, with no title scraping.

Wikidata is a separate source of *claims*. Platform QIDs are pinned in
sources/wikidata-v1.json. Only broad source/platform SPARQL queries are used.
Every response, query, fetch time, HTTP digest, and unique item ID is kept.
No records are matched to the console corpus in this acquisition stage.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
QID = re.compile(r"Q[1-9][0-9]*\Z")
PLATFORM = re.compile(r"[a-z0-9]+\Z")
ITEM_URI = re.compile(r"https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)\Z")
MAX_RESPONSE = 20_000_000
USER_AGENT = ("Ludographium/1.0 "
              "(https://github.com/sguzman/ludographium; "
              "public independent metadata corpus research)")


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def register(root):
    data = json.loads((root / "sources/wikidata-v1.json").read_bytes())
    if (data.get("schema_version") != 1 or data.get("provider") != "wikidata"
            or data.get("provider_license") != "CC0-1.0"
            or data.get("endpoint") != "https://query.wikidata.org/sparql"):
        raise ValueError("unapproved Wikidata source register")
    limit = data["query_limit"]
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("unsafe platform-wide query limit")
    platforms, ids = set(), set()
    for entry in data["platforms"]:
        platform, qid = entry["platform"], entry["wikidata_platform"]
        if (not PLATFORM.fullmatch(platform) or not QID.fullmatch(qid)
                or platform in platforms or qid in ids):
            raise ValueError("invalid or duplicated platform/QID in register")
        platforms.add(platform)
        ids.add(qid)
    if not platforms:
        raise ValueError("empty Wikidata platform scope")
    return data


def query(qid, limit):
    if not QID.fullmatch(qid) or not 1 <= limit <= 10000:
        raise ValueError("unsafe Wikidata query")
    # Query the platform's *full* Wikidata video-game set (not user title
    # examples). Never use fuzzy regex or retrieve images/third-party prose.
    return (
        "SELECT DISTINCT ?item ?label ?date WHERE {\n"
        f"  ?item wdt:P31 wd:Q7889; wdt:P400 wd:{qid}.\n"
        "  OPTIONAL { ?item rdfs:label ?label. "
        'FILTER(LANG(?label) = "en") }\n'
        "  OPTIONAL { ?item wdt:P577 ?date. }\n"
        "}\nORDER BY ?item ?date\n"
        f"LIMIT {limit}\n"
    )


def extract_bindings(raw):
    parsed = json.loads(raw)
    if parsed.get("head", {}).get("vars") != ["item", "label", "date"]:
        raise ValueError("Wikidata SPARQL binding columns changed")
    bindings = parsed.get("results", {}).get("bindings")
    if not isinstance(bindings, list):
        raise ValueError("Wikidata SPARQL result rows absent")
    for row in bindings:
        uri = row.get("item", {}).get("value", "")
        if not ITEM_URI.fullmatch(uri):
            raise ValueError(f"invalid QID URI in source result: {uri!r}")
        if "label" in row and (
                row["label"].get("xml:lang") != "en"
                or row["label"].get("type") != "literal"):
            raise ValueError("Wikidata English label binding malformed")
        if "date" in row:
            date = row["date"]
            if (date.get("type") not in ("literal", "typed-literal", "bnode", "uri")
                    or not isinstance(date.get("value"), str)):
                raise ValueError("Wikidata publication date binding malformed")
            # A Wikidata unknown/unspecified date can be a blank node (or
            # another nonliteral RDF binding). Preserve the raw source row,
            # but never reinterpret it as a concrete calendar date.
    return bindings


def fetch_one(endpoint, sparql, *, timeout=55, attempts=4):
    url = endpoint + "?" + urlencode({"format": "json", "query": sparql})
    request = Request(
        url, headers={"User-Agent": USER_AGENT,
                      "Accept": "application/sparql-results+json"}
    )
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise ValueError("Wikidata response exceeds bounded size")
            return raw
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
            retry = exc.headers.get("Retry-After")
            delay = int(retry) if retry and retry.isdecimal() else 5 * (attempt + 1)
            time.sleep(min(max(delay, 3), 75))
        except (TimeoutError, URLError):
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def make_snapshot(cfg, fetch, *, now=None, pause=1):
    now = now or (lambda: datetime.now(timezone.utc).isoformat())
    parts = []
    for spec in cfg["platforms"]:
        sparql = query(spec["wikidata_platform"], cfg["query_limit"])
        raw = fetch(cfg["endpoint"], sparql)
        bindings = extract_bindings(raw)
        if len(bindings) >= cfg["query_limit"]:
            raise ValueError(f"query for {spec['platform']} reached row limit; "
                             "incomplete scope must not be published")
        part = {
            **spec,
            "query": sparql,
            "query_sha256": hashlib.sha256(sparql.encode()).hexdigest(),
            "received_at_utc": now(),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_response": raw.decode("utf-8"),
            "row_count": len(bindings),
            "distinct_items": len({
                ITEM_URI.fullmatch(row["item"]["value"])[1] for row in bindings
            }),
        }
        parts.append(part)
        print(f"WIKIDATA {spec['platform']}: {part['distinct_items']} items, "
              f"{len(bindings)} source rows", flush=True)
        if pause:
            time.sleep(pause)
    return {
        "schema_version": 1,
        "kind": "wikidata-console-source-snapshot",
        "source_id": "wikidata",
        "source_license": cfg["provider_license"],
        "endpoint": cfg["endpoint"],
        "source_register_sha256": hashlib.sha256(canonical(cfg)).hexdigest(),
        "source_properties": {
            "P31": "instance of video game Q7889",
            "P400": "computing platform",
            "P577": "publication date",
            "rdfs:label": "English entity label",
        },
        "parts": parts,
    }


def validate_snapshot(cfg, snapshot):
    if (snapshot.get("schema_version") != 1
            or snapshot.get("kind") != "wikidata-console-source-snapshot"
            or snapshot.get("source_id") != "wikidata"
            or snapshot.get("source_license") != "CC0-1.0"
            or snapshot.get("source_register_sha256") != hashlib.sha256(canonical(cfg)).hexdigest()):
        raise ValueError("Wikidata snapshot source/manifest mismatch")
    if len(snapshot["parts"]) != len(cfg["platforms"]):
        raise ValueError("missing Wikidata query partition")
    item_count = row_count = dated = 0
    for expected, part in zip(cfg["platforms"], snapshot["parts"]):
        if part["platform"] != expected["platform"] or part["wikidata_platform"] != expected["wikidata_platform"]:
            raise ValueError("Wikidata source platform mapping changed")
        statement = query(part["wikidata_platform"], cfg["query_limit"])
        raw = part["raw_response"].encode("utf-8")
        if (part["query"] != statement or
                part["query_sha256"] != hashlib.sha256(statement.encode()).hexdigest() or
                part["response_sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError("Wikidata query or response digest mismatch")
        records = extract_bindings(raw)
        if len(records) != part["row_count"] or len(records) >= cfg["query_limit"]:
            raise ValueError("Wikidata result count differs")
        unique = {ITEM_URI.fullmatch(b["item"]["value"])[1] for b in records}
        if len(unique) != part["distinct_items"]:
            raise ValueError("Wikidata unique item count differs")
        item_count += len(unique)
        row_count += len(records)
        dated += sum("date" in b and b["date"]["type"] in ("literal", "typed-literal")
                     for b in records)
    return {"platform_partitions": len(cfg["platforms"]),
            "platform_item_observations": item_count,
            "rows": row_count, "dated_rows": dated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--fetch", action="store_true")
    modes.add_argument("--verify", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    cfg = register(args.root)
    if args.fetch:
        snapshot = make_snapshot(cfg, fetch_one)
        result = validate_snapshot(cfg, snapshot)
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_bytes(canonical(snapshot))
        print(f"ACQUIRED {args.snapshot} " + json.dumps(result, sort_keys=True))
    else:
        snapshot = json.loads(args.snapshot.read_bytes())
        print("VERIFIED " + json.dumps(validate_snapshot(cfg, snapshot), sort_keys=True))


if __name__ == "__main__":
    main()
