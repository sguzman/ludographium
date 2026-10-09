#!/usr/bin/env python3
"""Validate an explicit request to publish a pinned Ludographium dataset.

The workflow reads this file only when its committed contents change on main.
A request selects a new immutable dataset tag; it does not control shell
commands, arbitrary Git refs, target revisions, or arbitrary release assets.
"""
import argparse
import json
from pathlib import Path

from prepare_release import validate_tag

MAX_REQUEST_BYTES = 4096
EXPECTED_KEYS = {"schema_version", "tag"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate release-request key: {key}")
        result[key] = value
    return result


def parse_release_request(data: bytes) -> str:
    if not data or len(data) > MAX_REQUEST_BYTES:
        raise ValueError("release request missing or exceeds allowed size")
    request = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(request, dict) or request.keys() != EXPECTED_KEYS:
        raise ValueError("release request must contain exactly schema_version and tag")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ValueError("unsupported release request schema")
    tag = request["tag"]
    if not isinstance(tag, str) or len(tag) > 64:
        raise ValueError("release request tag must be a short string")
    validate_tag(tag)
    return tag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    print(parse_release_request(args.file.read_bytes()))


if __name__ == "__main__":
    main()
