"""Wikidata source and linkage fixtures: no live API dependency."""
import hashlib
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from wikidata_source import (
    make_snapshot, validate_snapshot, query, extract_bindings,
    register, canonical,
)
from reconcile_wikidata import (
    build, title_key, summary, validate,
)
from build_corpus import open_readonly
from enrich_expanded_corpus import build as build_fields
from test_enrich_expanded_corpus import ExpandedFieldTests

DT = "http://www.w3.org/2001/XMLSchema#dateTime"


def bindings(qids=("Q125",)):
    result = []
    for qid in qids:
        result.append({
            "item": {"type": "uri", "value": "http://www.wikidata.org/entity/" + qid},
            "label": {"type": "literal", "xml:lang": "en",
                      "value": "Brand New Console Game"},
            "date": {"type": "literal", "datatype": DT,
                     "value": "1994-01-01T00:00:00Z"},
        })
    return result


def response(rows):
    return json.dumps({"head": {"vars": ["item", "label", "date"]},
                       "results": {"bindings": rows}}, separators=(",", ":")).encode()


class WikidataTests(unittest.TestCase):
    def setUp(self):
        # Exercise real populated source tables, including unresolved field DATs,
        # rather than a decorative isolated matching algorithm.
        self.helper = ExpandedFieldTests(methodName="test_all_field_sources_are_preserved_and_matched_only_to_exact_records")
        self.helper.setUp()
        self.addCleanup(self.helper.doCleanups)
        self.root = self.helper.root
        self.base = self.helper.db_base
        self.extended = self.helper.db
        build_fields(self.root, self.base, self.extended, cache_dir=self.helper.cache)
        self.root.joinpath("sources/wikidata-v1.json").write_text(json.dumps({
            "schema_version": 1, "provider": "wikidata",
            "provider_license": "CC0-1.0",
            "endpoint": "https://query.wikidata.org/sparql",
            "query_limit": 1000,
            "platforms": [{"platform": "exampleconsole", "wikidata_platform": "Q1234"}],
        }))
        self.snapshot_path = self.root / "snapshot.json"
        self.output = self.root / "with-wikidata.sqlite"

    def acquire(self, rows):
        cfg = register(self.root)
        def fetch(endpoint, sparql):
            self.assertEqual(endpoint, "https://query.wikidata.org/sparql")
            self.assertIn("wd:Q1234", sparql)
            return response(rows)
        snap = make_snapshot(cfg, fetch, pause=0, now=lambda: "2026-10-09T17:00:00+00:00")
        self.snapshot_path.write_bytes(canonical(snap))
        return snap

    def test_bulk_data_is_attributed_without_canonical_identity(self):
        snap = self.acquire(bindings())
        self.assertEqual(validate_snapshot(register(self.root), snap)["platform_item_observations"], 1)
        counts = build(self.root, self.extended, self.snapshot_path, self.output)
        self.assertEqual(counts["source_observations"], 4)
        self.assertEqual(counts["wikidata_item_platform_observations"], 1)
        self.assertEqual(counts["candidate_links"], 1)
        self.assertEqual(counts["wikidata_publication_date_claims"], 1)
        with open_readonly(self.output) as db:
            self.assertEqual(validate(db, register(self.root), snap), counts)
            row = db.execute("SELECT source_ordinal,item_id,status FROM wikidata_link_candidates").fetchone()
            self.assertEqual(row, (1, "Q125", "title_candidate"))
            self.assertEqual(db.execute("SELECT count(*) FROM claims").fetchone()[0], 5)
            self.assertEqual(db.execute("SELECT count(*) FROM games").fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT count(*) FROM wikidata_queries").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM wikidata_dates").fetchone()[0], 1)
            self.assertIn("wd:Q1234", db.execute("SELECT query_text FROM wikidata_queries").fetchone()[0])
            self.assertEqual(db.execute("SELECT count(*) FROM wikidata_link_candidates WHERE status='title_candidate'").fetchone()[0], 1)

    def test_collision_never_creates_unique_candidate(self):
        self.acquire(bindings(("Q125", "Q126")))
        counts = build(self.root, self.extended, self.snapshot_path, self.output)
        self.assertEqual(counts["candidate_links"], 2)
        self.assertEqual(counts["ambiguous_candidate_links"], 2)
        with open_readonly(self.output) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM wikidata_link_candidates "
                                        "WHERE status='title_candidate'").fetchone()[0], 0)

    def test_reproducible_and_tampering_rejected_without_overwriting(self):
        snap = self.acquire(bindings())
        build(self.root, self.extended, self.snapshot_path, self.output)
        before = hashlib.sha256(self.output.read_bytes()).hexdigest()
        build(self.root, self.extended, self.snapshot_path, self.output)
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), before)
        snap["parts"][0]["raw_response"] += " "
        self.snapshot_path.write_bytes(canonical(snap))
        with self.assertRaisesRegex(ValueError, "response digest mismatch"):
            build(self.root, self.extended, self.snapshot_path, self.output)
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), before)

    def test_typed_literal_dates_preserve_original_datatype(self):
        rows = bindings()
        rows[0]["date"]["type"] = "typed-literal"
        snap = self.acquire(rows)
        self.assertEqual(validate_snapshot(register(self.root), snap)["dated_rows"], 1)
        build(self.root, self.extended, self.snapshot_path, self.output)
        with open_readonly(self.output) as db:
            self.assertEqual(db.execute("SELECT date_datatype FROM wikidata_dates").fetchone()[0], DT)

    def test_no_guessy_title_normalization(self):
        self.assertEqual(title_key("Brand New Console Game (USA) (Rev 1)"),
                         "brand new console game")
        self.assertEqual(title_key("Brand New Console Game (World) (En,Fr)"),
                         "brand new console game")
        self.assertEqual(title_key("Game (Special Edition) (Europe)"),
                         "game (special edition)")
        self.assertNotEqual(title_key("Game (Special Edition) (Europe)"),
                            title_key("Game (Europe)"))
        self.assertNotEqual(title_key("Pokémon"), title_key("Pokemon"))
        self.assertNotEqual(title_key("Game DX"), title_key("Game"))

    def test_invalid_source_rows_fail_closed(self):
        self.acquire(bindings())
        with self.assertRaisesRegex(ValueError, "invalid QID URI"):
            extract_bindings(response([{
                "item": {"type": "uri", "value": "https://evil.invalid/item/Q125"}
            }]))
        cfg = register(self.root)
        with self.assertRaisesRegex(ValueError, "reached row limit"):
            make_snapshot({**cfg, "query_limit": 1},
                          lambda *_: response(bindings()), pause=0)
        with self.assertRaisesRegex(ValueError, "source/manifest mismatch"):
            validate_snapshot({**cfg, "query_limit": 1},
                              json.loads(self.snapshot_path.read_text()))


if __name__ == "__main__":
    unittest.main()
