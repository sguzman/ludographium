#!/usr/bin/env python3
"""Bulk-ingest all registered additional console DATs into one offline SQLite corpus.

The original ten-platform source collection and its prior releases remain
unchanged. Additional sources are pinned individually by upstream Git blob
SHA, retrieved once per build (or from a verified local source cache), and
stored byte-for-byte in the resulting SQLite file. No game-by-game curation.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from urllib.parse import quote
from urllib.request import urlopen

from build_corpus import build as build_base
from build_corpus import counts as base_counts
from build_corpus import query, open_readonly
from import_dat import import_dat

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "sources/bulk-expansion-v1.json"
SOURCE_ARCHIVES = """
CREATE TABLE source_archives (
    platform TEXT PRIMARY KEY REFERENCES platforms(platform),
    git_blob_sha TEXT NOT NULL,
    dat_bytes BLOB NOT NULL
);
"""
HEX_SHA = re.compile(r"^[a-f0-9]{40}$")
PLATFORM = re.compile(r"^[a-z0-9]+$")


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def pinned_manifest(root):
    raw = (root / MANIFEST).read_bytes()
    manifest = json.loads(raw)
    if manifest.get("schema_version") != 1 or manifest.get("kind") != "pinned-bulk-platform-expansion":
        raise ValueError("unsupported expansion manifest")
    if manifest["source_id"] != "libretro-no-intro":
        raise ValueError("unexpected new source identity")
    if not HEX_SHA.fullmatch(manifest["repository_revision"]):
        raise ValueError("invalid pinned upstream revision")
    if manifest["declared_repository_license"] != "CC-BY-SA-4.0":
        raise ValueError("unexpected declared source license: examine rights before importing")
    if manifest["repository"] != "https://github.com/libretro/libretro-database":
        raise ValueError("unapproved upstream repository")
    seen = set()
    for entry in manifest["platforms"]:
        platform = entry["platform"]
        if not PLATFORM.fullmatch(platform) or platform in seen:
            raise ValueError(f"invalid or repeated expansion platform {platform}")
        seen.add(platform)
        if not (entry["source_path"].startswith("metadat/no-intro/")
                and entry["source_path"].endswith(".dat")
                and "/" not in entry["source_path"][17:]):
            raise ValueError("invalid upstream source path")
        if not HEX_SHA.fullmatch(entry["git_blob_sha"]):
            raise ValueError(f"invalid pinned Git blob SHA for {platform}")
        if type(entry["bytes"]) is not int or not 0 < entry["bytes"] < 50_000_000:
            raise ValueError(f"invalid source byte size for {platform}")
    if not seen:
        raise ValueError("bulk manifest selected no sources")
    return manifest


def retrieve(entry, revision, cache_dir=None):
    if cache_dir is not None:
        raw = (cache_dir / (entry["platform"] + ".dat")).read_bytes()
    else:
        path = quote(entry["source_path"], safe="/")
        url = (f"https://raw.githubusercontent.com/libretro/libretro-database/"
               f"{revision}/{path}")
        error = None
        for attempt in range(4):
            try:
                with urlopen(url, timeout=60) as response:
                    raw = response.read(entry["bytes"] + 1)
                break
            except (OSError, TimeoutError) as exc:
                error = exc
                if attempt == 3:
                    raise OSError(f"unable to retrieve pinned source {entry['platform']}") from error
                time.sleep(1 + attempt * 2)
    if len(raw) != entry["bytes"] or git_blob(raw) != entry["git_blob_sha"]:
        raise ValueError(f"pinned source size / Git blob SHA mismatch: {entry['platform']}")
    return entry["platform"], raw


def ingest(root, temp_path, manifest, source_dir=None, workers=8):
    source_entries = sorted(manifest["platforms"], key=lambda e: e["platform"])
    # Build and verify all original source and field observations first.
    base = build_base(root, temp_path)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fetched = dict(pool.map(
            lambda entry: retrieve(entry, manifest["repository_revision"], source_dir),
            source_entries,
        ))
    importer = {
        "source_id": manifest["source_id"],
        "repository_revision": manifest["repository_revision"],
        "declared_repository_license": manifest["declared_repository_license"],
        "files": source_entries,
    }
    with sqlite3.connect(temp_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SOURCE_ARCHIVES)
        conn.execute(
            "INSERT INTO provenance VALUES (?, ?)",
            ("bulk_expansion", json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))),
        )
        extra = Counter()
        for entry in source_entries:
            platform = entry["platform"]
            bundle = import_dat(fetched[platform], importer, platform)
            conn.execute(
                "INSERT INTO platforms VALUES (?,?,?,?,?,?,?,?,?)",
                (platform, bundle["source_id"], bundle["source_revision"],
                 bundle["source_path"], bundle["source_blob_sha"],
                 bundle["source_license"], bundle["dat_version"],
                 bundle["record_count"], bundle["rom_count"]),
            )
            conn.execute(
                "INSERT INTO source_archives VALUES (?,?,?)",
                (platform, entry["git_blob_sha"], fetched[platform]),
            )
            for record in bundle["records"]:
                ordinal = record["source_ordinal"]
                conn.execute(
                    "INSERT INTO games VALUES (?,?,?,?,?,?)",
                    (platform, ordinal, record["name"], record.get("region"),
                     record.get("serial"),
                     json.dumps(
                         {key: value for key, value in record.items()
                          if key not in {"source_ordinal", "name", "roms"}},
                         ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                for media_ordinal, media in enumerate(record["roms"], 1):
                    conn.execute(
                        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (platform, ordinal, media_ordinal, media["name"], media["size"],
                         media.get("sha1"), media.get("crc32"), media.get("md5"),
                         media.get("serial"),
                         json.dumps(media, ensure_ascii=False, separators=(",", ":"))),
                    )
            extra.update(platforms=1, games=bundle["record_count"], media=bundle["rom_count"])
            print(f"ADDED {platform}: {bundle['record_count']} source observations, "
                  f"{bundle['rom_count']} media entries", flush=True)
        conn.commit()
        conn.execute("VACUUM")
        expected = {
            "platforms": base["platforms"] + extra["platforms"],
            "games": base["games"] + extra["games"],
            "media": base["media"] + extra["media"],
            "claims": base["claims"],
            "matched": base["matched"],
            "with_metadata": base["with_metadata"],
        }
        observed = validate_expanded(conn, manifest, expected=expected)
        return observed


def validate_expanded(conn, manifest, expected=None):
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("expanded SQLite integrity check failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("expanded SQLite foreign key check failed")
    actual = base_counts(conn)
    if actual["platforms"] != manifest["base_platform_count"] + len(manifest["platforms"]):
        raise ValueError("incorrect total platform coverage")
    rows = conn.execute(
        "SELECT platform,source_id,source_revision,source_path,source_blob_sha,"
        "source_license,source_record_count,media_count FROM platforms"
    )
    platforms = {row[0]: row[1:] for row in rows}
    for entry in manifest["platforms"]:
        platform = entry["platform"]
        found = platforms.get(platform)
        if found is None or found[:5] != (
            manifest["source_id"], manifest["repository_revision"],
            entry["source_path"], entry["git_blob_sha"],
            manifest["declared_repository_license"],
        ):
            raise ValueError(f"expanded source mismatch: {platform}")
        stored = conn.execute(
            "SELECT git_blob_sha,dat_bytes FROM source_archives WHERE platform=?",
            (platform,),
        ).fetchone()
        if stored is None or stored[0] != entry["git_blob_sha"] or len(stored[1]) != entry["bytes"]:
            raise ValueError(f"missing archived DAT bytes: {platform}")
        if git_blob(stored[1]) != entry["git_blob_sha"]:
            raise ValueError(f"archived DAT blob mismatch: {platform}")
        record_count = conn.execute(
            "SELECT count(*) FROM games WHERE platform=?", (platform,)
        ).fetchone()[0]
        media_count = conn.execute(
            "SELECT count(*) FROM media WHERE platform=?", (platform,)
        ).fetchone()[0]
        if (record_count, media_count) != found[5:]:
            raise ValueError(f"platform counts diverge: {platform}")
    if conn.execute("SELECT count(*) FROM source_archives").fetchone()[0] != len(manifest["platforms"]):
        raise ValueError("archived DAT inventory mismatch")
    if expected is not None and actual != expected:
        raise ValueError(f"corpus coverage differs: {actual} != {expected}")
    return actual


def build(root, destination, *, source_dir=None, workers=8):
    manifest = pinned_manifest(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".ludographium-expanded-", suffix=".sqlite", dir=destination.parent
    )
    os.close(fd)
    try:
        result = ingest(root, Path(temporary), manifest, source_dir, workers)
        os.replace(temporary, destination)
        return result
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--db", type=Path)
    p.add_argument("--source-dir", type=Path, help="optional complete verified pinned DAT cache")
    p.add_argument("--workers", type=int, default=8)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--summary", action="store_true")
    mode.add_argument("--title")
    mode.add_argument("--sha1")
    p.add_argument("--platform")
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()
    if not 1 <= args.workers <= 16:
        p.error("--workers must be 1..16")
    db = args.db or Path("/tmp/ludographium-expanded.sqlite")
    if args.build:
        if args.platform or args.limit != 20:
            p.error("search filters require a search mode")
        result = build(args.root, db, source_dir=args.source_dir, workers=args.workers)
        print("PASS: expanded corpus " + json.dumps(result, sort_keys=True))
        return
    with open_readonly(db) as conn:
        if args.verify:
            result = validate_expanded(conn, pinned_manifest(args.root))
        elif args.summary:
            result = base_counts(conn)
        else:
            result = query(conn, platform=args.platform, title=args.title,
                           sha1=args.sha1, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
