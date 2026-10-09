#!/usr/bin/env python3
"""Reconcile a pinned Wikidata snapshot with all 75 console source collections.

Candidate links are exact platform + tightly normalized English title matches.
They are never canonical game work IDs or independently verified publication
facts. Every Wikidata item/date and source response remains independently
queryable, including records with zero/multiple candidate links.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import unicodedata

from build_corpus import counts, open_readonly
from build_expanded_corpus import validate_expanded, pinned_manifest
from enrich_expanded_corpus import field_manifest, validate_fields
from wikidata_source import ITEM_URI, register, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
TRAILER = re.compile(r"\s+\(([^()]*)\)\s*$")
REV = re.compile(r"Rev ([0-9]+|[A-Z])\Z")
REGIONS = {
    "USA", "Europe", "World", "Japan", "Australia", "Brazil", "Canada",
    "Korea", "Asia", "China", "Taiwan", "Hong Kong", "France", "Germany",
    "Spain", "Italy", "Sweden", "Netherlands", "Russia", "UK",
}
LANGS = {"En", "Fr", "De", "Es", "It", "Pt", "Ja", "Ko", "Zh", "Nl", "Ru", "Sv"}

SCHEMA = """
CREATE TABLE wikidata_queries (
    platform TEXT PRIMARY KEY REFERENCES platforms(platform),
    wikidata_platform TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_sha256 TEXT NOT NULL,
    received_at_utc TEXT NOT NULL,
    response_sha256 TEXT NOT NULL,
    raw_response TEXT NOT NULL,
    source_row_count INTEGER NOT NULL
);
CREATE TABLE wikidata_items (
    platform TEXT NOT NULL,
    item_id TEXT NOT NULL,
    english_label TEXT,
    PRIMARY KEY (platform,item_id),
    FOREIGN KEY (platform) REFERENCES platforms(platform)
);
CREATE TABLE wikidata_dates (
    platform TEXT NOT NULL,
    item_id TEXT NOT NULL,
    date_value TEXT NOT NULL,
    date_datatype TEXT,
    PRIMARY KEY (platform,item_id,date_value),
    FOREIGN KEY (platform,item_id) REFERENCES wikidata_items(platform,item_id)
);
CREATE TABLE wikidata_link_candidates (
    platform TEXT NOT NULL,
    source_ordinal INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    source_title_key TEXT NOT NULL,
    wikidata_title_key TEXT NOT NULL,
    competing_wikidata_items INTEGER NOT NULL,
    status TEXT NOT NULL
      CHECK (status IN ('title_candidate','ambiguous_wikidata_title')),
    PRIMARY KEY (platform,source_ordinal,item_id),
    FOREIGN KEY (platform,source_ordinal) REFERENCES games(platform,source_ordinal),
    FOREIGN KEY (platform,item_id) REFERENCES wikidata_items(platform,item_id),
    CHECK (source_title_key = wikidata_title_key)
);
CREATE INDEX idx_wikidata_english_label ON wikidata_items(platform,english_label);
CREATE INDEX idx_wikidata_candidate_item ON wikidata_link_candidates(platform,item_id);
CREATE INDEX idx_wikidata_candidate_status ON wikidata_link_candidates(status);
CREATE VIEW wikidata_candidate_detail AS
    SELECT g.platform,g.source_ordinal,g.title AS source_title,
           wi.item_id,wi.english_label,lc.status,lc.competing_wikidata_items,
           'https://www.wikidata.org/wiki/' || wi.item_id AS wikidata_url
    FROM wikidata_link_candidates lc
    JOIN games g ON g.platform=lc.platform AND g.source_ordinal=lc.source_ordinal
    JOIN wikidata_items wi ON wi.platform=lc.platform AND wi.item_id=lc.item_id;
"""


def title_key(name):
    if not isinstance(name, str):
        raise ValueError("invalid source title")
    name = unicodedata.normalize("NFC", name).strip()
    # Discard only explicit trailing source tags. Never remove arbitrary
    # parenthetical title content, editions or unspecified marketing suffixes.
    for _ in range(12):
        match = TRAILER.search(name)
        if not match:
            break
        tag = match[1].strip()
        parts = [part.strip() for part in tag.split(",")]
        region = bool(parts) and all(x in REGIONS for x in parts)
        language = bool(parts) and all(x in LANGS for x in parts)
        if region or language or REV.fullmatch(tag):
            name = name[:match.start()].rstrip()
        else:
            break
    return " ".join(name.split()).casefold()


def source_items(snapshot):
    for part in snapshot["parts"]:
        platform = part["platform"]
        seen = {}
        dates = set()
        result = json.loads(part["raw_response"])
        for row in result["results"]["bindings"]:
            qid = ITEM_URI.fullmatch(row["item"]["value"])[1]
            label = row.get("label", {}).get("value")
            if qid in seen and label and seen[qid] and label != seen[qid]:
                raise ValueError(f"conflicting English Wikidata labels for {qid}")
            seen[qid] = label or seen.get(qid)
            if "date" in row:
                date = row["date"]
                if date.get("type") in ("literal", "typed-literal"):
                    dates.add((qid, date["value"], date.get("datatype")))
        yield platform, seen, sorted(dates)


def summary(conn):
    return {
        "platform_source_collections": conn.execute("SELECT count(*) FROM platforms").fetchone()[0],
        "source_observations": conn.execute("SELECT count(*) FROM games").fetchone()[0],
        "wikidata_platforms": conn.execute("SELECT count(*) FROM wikidata_queries").fetchone()[0],
        "wikidata_item_platform_observations": conn.execute("SELECT count(*) FROM wikidata_items").fetchone()[0],
        "wikidata_publication_date_claims": conn.execute("SELECT count(*) FROM wikidata_dates").fetchone()[0],
        "candidate_links": conn.execute("SELECT count(*) FROM wikidata_link_candidates").fetchone()[0],
        "source_observations_with_candidate": conn.execute(
            "SELECT count(*) FROM (SELECT platform,source_ordinal FROM wikidata_link_candidates GROUP BY 1,2)"
        ).fetchone()[0],
        "ambiguous_candidate_links": conn.execute(
            "SELECT count(*) FROM wikidata_link_candidates WHERE status='ambiguous_wikidata_title'"
        ).fetchone()[0],
    }


def validate(conn, cfg, snapshot, *, expected=None):
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Wikidata SQLite integrity failed")
    if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("Wikidata source/target foreign keys broken")
    result = validate_snapshot(cfg, snapshot)
    counts_now = summary(conn)
    if counts_now["wikidata_platforms"] != result["platform_partitions"]:
        raise ValueError("missing source query partitions")
    if counts_now["wikidata_item_platform_observations"] != result["platform_item_observations"]:
        raise ValueError("Wikidata item count mismatch")
    for part in snapshot["parts"]:
        row = conn.execute(
            "SELECT wikidata_platform,query_sha256,response_sha256,raw_response,source_row_count "
            "FROM wikidata_queries WHERE platform=?", (part["platform"],),
        ).fetchone()
        if (row is None or row != (part["wikidata_platform"], part["query_sha256"],
                                  part["response_sha256"], part["raw_response"],
                                  part["row_count"])):
            raise ValueError(f"Wikidata source response changed: {part['platform']}")
        candidates = conn.execute(
            "SELECT source_ordinal,item_id,source_title_key,wikidata_title_key,"
            "competing_wikidata_items,status FROM wikidata_link_candidates WHERE platform=?",
            (part["platform"],),
        )
        for ordinal,qid,source_key,wikidata_key,competitors,status in candidates:
            titles = conn.execute(
                "SELECT g.title,wi.english_label FROM games g JOIN wikidata_items wi "
                "ON g.platform=wi.platform WHERE g.platform=? AND g.source_ordinal=? AND wi.item_id=?",
                (part["platform"],ordinal,qid),
            ).fetchone()
            if (titles is None or source_key != title_key(titles[0])
                    or wikidata_key != title_key(titles[1])
                    or source_key != wikidata_key):
                raise ValueError("unsafe Wikidata title candidate recorded")
            n = conn.execute(
                "SELECT count(*) FROM wikidata_items WHERE platform=?",
                (part["platform"],),
            ).fetchone()[0]
            if competitors < 1 or competitors > n or status != (
                    "title_candidate" if competitors == 1 else "ambiguous_wikidata_title"):
                raise ValueError("candidate ambiguity status is inconsistent")
    if expected is not None and counts_now != expected:
        raise ValueError(f"Wikidata match counts changed: {counts_now} != {expected}")
    return counts_now


def append(conn, cfg, snapshot):
    validate_snapshot(cfg, snapshot)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO provenance VALUES (?,?)", (
        "wikidata_register", json.dumps(cfg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ))
    for part, (platform, item_map, dates) in zip(snapshot["parts"], source_items(snapshot)):
        conn.execute(
            "INSERT INTO wikidata_queries VALUES (?,?,?,?,?,?,?,?)",
            (platform, part["wikidata_platform"], part["query"],
             part["query_sha256"], part["received_at_utc"], part["response_sha256"],
             part["raw_response"], part["row_count"]),
        )
        for qid, label in sorted(item_map.items()):
            conn.execute("INSERT INTO wikidata_items VALUES (?,?,?)",
                         (platform, qid, label))
        for qid, date, datatype in dates:
            conn.execute("INSERT INTO wikidata_dates VALUES (?,?,?,?)",
                         (platform, qid, date, datatype))
        by_key = defaultdict(set)
        for qid, label in item_map.items():
            if label and title_key(label):
                by_key[title_key(label)].add(qid)
        for ordinal, title in conn.execute(
                "SELECT source_ordinal,title FROM games WHERE platform=? ORDER BY source_ordinal",
                (platform,)):
            key = title_key(title)
            for qid in sorted(by_key.get(key, ())):
                opponents = len(by_key[key])
                status = "title_candidate" if opponents == 1 else "ambiguous_wikidata_title"
                conn.execute(
                    "INSERT INTO wikidata_link_candidates VALUES (?,?,?,?,?,?,?)",
                    (platform, ordinal, qid, key, key, opponents, status),
                )
        print(f"JOIN {platform}: {len(item_map)} Wikidata item observations", flush=True)
    conn.commit()


def build(root, base_db, snapshot_path, output):
    cfg = register(root)
    snapshot = json.loads(snapshot_path.read_bytes())
    validate_snapshot(cfg, snapshot)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".ludographium-wikidata-", suffix=".sqlite",
                                dir=output.parent)
    os.close(fd)
    try:
        shutil.copyfile(base_db, temp)
        with sqlite3.connect(temp) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            validate_expanded(conn, pinned_manifest(root))
            validate_fields(conn, field_manifest(root))
            old = counts(conn)
            conn.executescript("PRAGMA foreign_keys=ON;")
            append(conn, cfg, snapshot)
            conn.execute("VACUUM")
            if counts(conn) != old:
                raise ValueError("original source corpus changed during Wikidata reconciliation")
            numbers = validate(conn, cfg, snapshot)
        os.replace(temp, output)
        return numbers
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--build", action="store_true")
    modes.add_argument("--verify", action="store_true")
    modes.add_argument("--summary", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--from-db", type=Path)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args()
    if args.build:
        if args.from_db is None or args.snapshot is None or args.from_db == args.db:
            parser.error("--build requires distinct --from-db, --db and --snapshot")
        stats = build(args.root, args.from_db, args.snapshot, args.db)
    else:
        with open_readonly(args.db) as conn:
            if args.verify:
                if args.snapshot is None:
                    parser.error("--verify requires --snapshot")
                stats = validate(conn, register(args.root),
                                 json.loads(args.snapshot.read_bytes()))
                validate_expanded(conn, pinned_manifest(args.root))
                validate_fields(conn, field_manifest(args.root))
            else:
                stats = summary(conn)
    print(json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
