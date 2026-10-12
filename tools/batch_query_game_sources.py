#!/usr/bin/env python3
"""Bounded offline JSONL batch search over independently pinned game sources.

One verified local SQLite session serves all requests. Per-request results
retain separate MAME CC0 and Libretro CC-BY-SA source evidence. No joining,
network requests, database mutation, or canonical game identities.
"""
import argparse
import json
from pathlib import Path
import re

from build_mame_catalog_sqlite import (
    ROOT, open_readonly, query_both_sources, verify,
)

MAX_REQUESTS = 1000
MAX_INPUT_BYTES = 1024 * 1024
MAX_PER_PROVIDER = 50
ALLOWED_KEYS = frozenset(("id", "title", "sha1", "limit"))
SHA1 = re.compile(r"[0-9a-fA-F]{40}\Z")


def unique_json_keys(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"duplicate query field: {name}")
        result[name] = value
    return result


def load_requests(path, default_limit=5):
    if type(default_limit) is not int or not 1 <= default_limit <= MAX_PER_PROVIDER:
        raise ValueError("batch default limit must be 1..50 per provider")
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("query source must be a regular JSONL file")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("query batch input exceeds 1 MiB")
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        raise ValueError("query JSONL must end with a newline")
    lines = text.splitlines()
    if not 1 <= len(lines) <= MAX_REQUESTS:
        raise ValueError("query batch must contain between 1 and 1000 entries")
    requests, ids = [], set()
    for ordinal, line in enumerate(lines, 1):
        try:
            record = json.loads(line, object_pairs_hook=unique_json_keys)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"invalid source query JSONL row {ordinal}") from exc
        if not isinstance(record, dict) or set(record) - ALLOWED_KEYS:
            raise ValueError(f"unsupported source lookup fields at row {ordinal}")
        identifier = record.get("id")
        title = record.get("title")
        sha1 = record.get("sha1")
        limit = record.get("limit", default_limit)
        if (
            not isinstance(identifier, str)
            or not 1 <= len(identifier) <= 128
            or not identifier.strip()
            or identifier in ids
        ):
            raise ValueError(f"missing, duplicate or malformed request ID: {ordinal}")
        ids.add(identifier)
        if title is None and sha1 is None:
            raise ValueError(f"query row {ordinal} must have title or SHA-1")
        if title is not None and (
            not isinstance(title, str) or not 1 <= len(title) <= 250
            or not title.strip()
        ):
            raise ValueError(f"invalid original title query: {ordinal}")
        if sha1 is not None and (
            not isinstance(sha1, str) or SHA1.fullmatch(sha1) is None
        ):
            raise ValueError(f"invalid exact source media SHA-1: {ordinal}")
        if type(limit) is not int or not 1 <= limit <= MAX_PER_PROVIDER:
            raise ValueError(f"unsafe per-source query limit at row {ordinal}")
        requests.append({
            "id": identifier, "title": title,
            "sha1": sha1, "limit": limit,
        })
    return requests


def query_batch(conn, requests):
    for request in requests:
        result = query_both_sources(
            conn, title=request["title"], sha1=request["sha1"],
            limit=request["limit"],
        )
        yield {
            "request_id": request["id"],
            "schema_version": 1,
            "source_mode": "separate-original-provider-batch-query",
            "response": result,
            "interpretation": (
                "Independent provider observations only: MAME CC0-1.0 and "
                "Libretro CC-BY-SA-4.0, with no accepted game/release identity."
            ),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        requests = load_requests(args.input, args.limit)
    except (ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    if args.db.is_symlink() or not args.db.is_file():
        parser.error("missing local derived source database; use --build first")
    with open_readonly(args.db) as conn:
        verify(conn, ROOT)
        for row in query_batch(conn, requests):
            print(json.dumps(row, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
