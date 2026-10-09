"""Test a complete corpus-wide SQLite build; no manually curated identities."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_corpus import build, counts, open_readonly, query, validate


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def fixture(root):
    (root / "generated/v1").mkdir(parents=True)
    (root / "generated/enrichment-v1").mkdir(parents=True)
    (root / "sources").mkdir(parents=True)
    (root / "reports").mkdir(parents=True)
    (root / "METADATA-NOTICE.md").write_text("Fixture provider attribution", encoding="utf-8")
    base = {
        "schema_version": 1, "kind": "source-observations",
        "platform": "gb", "source_id": "provider-base",
        "source_revision": "pinned", "source_path": "original.dat",
        "source_blob_sha": "gitblob", "source_license": "CC-BY-SA-4.0",
        "record_count": 3, "rom_count": 4, "records": [
            {"source_ordinal": 1, "name": "Alpha Game (USA)",
             "region": "USA", "roms": [
                 {"name": "alpha.gb", "size": 128,
                  "sha1": "A"*40, "crc32": "12345678", "md5": "F"*32}
             ]},
            {"source_ordinal": 2, "name": "Alpha Game (USA) (Rev 1)",
             "roms": [
                 {"name": "alpha-v1.gb", "size": 128,
                  "sha1": "B"*40, "crc32": "ABCDEF01"}]},
            {"source_ordinal": 3, "name": "Multifile (World)",
             "roms": [
                 {"name": "multifile-1.gb", "size": 64, "sha1": "C"*40},
                 {"name": "multifile-2.gb", "size": 64, "sha1": "D"*40}]},
        ],
    }
    enrichment = {
        "schema_version": 1, "kind": "source-enrichment-claims",
        "platform": "gb", "source_id": "provider-fields",
        "source_revision": "pinned", "base_source_id": "provider-base",
        "base_source_revision": "pinned", "claim_count": 4,
        "resolution_counts": {"matched": 2, "comment_mismatch": 1, "unmatched_crc": 1},
        "claims": [
            {
                "source_ordinal": 1, "source_path": "publisher.dat",
                "source_blob_sha": "fieldblob", "field": "publisher",
                "value": "Example Company", "crc32": "12345678",
                "source_comment": "Alpha Game (USA)",
                "source_fields": {"comment": "Alpha Game (USA)", "publisher": "Example Company"},
                "resolution": {"status": "matched", "base_source_ordinal": 1}
            },
            {
                "source_ordinal": 2, "source_path": "genre.dat",
                "source_blob_sha": "anotherblob", "field": "genre",
                "value": "Platformer", "crc32": "ABCDEF01",
                "source_comment": "Alpha Game (USA) (Rev 1)",
                "source_fields": {"comment": "Alpha Game (USA) (Rev 1)"},
                "resolution": {"status": "matched", "base_source_ordinal": 2}
            },
            {
                "source_ordinal": 3, "source_path": "publisher.dat",
                "source_blob_sha": "fieldblob", "field": "publisher",
                "value": "Wrong", "crc32": "12345678",
                "source_comment": "Other Game (USA)",
                "source_fields": {"comment": "Other Game (USA)"},
                "resolution": {"status": "comment_mismatch", "base_source_ordinal": None}
            },
            {
                "source_ordinal": 4, "source_path": "serial.dat",
                "source_blob_sha": "fieldblob", "field": "serial",
                "value": "ZZ01", "crc32": "00000000",
                "source_comment": "Unknown",
                "source_fields": {"serial": "ZZ01"},
                "resolution": {"status": "unmatched_crc", "base_source_ordinal": None}
            },
        ],
    }
    catalog = {
        "schema_version": 1, "kind": "source-catalog",
        "source_id": "provider-base", "source_revision": "pinned",
        "platforms": [{"platform": "gb", "source_records": 3, "rom_fingerprints": 4,
                        "artifact_path": "generated/v1/gb.json"}],
    }
    registry = {"schema_version": 1, "repository_revision": "pinned"}
    coverage = {"total_claims": 4, "resolution_counts": {"matched": 2}}
    files = {
        "generated/v1/gb.json": base,
        "generated/enrichment-v1/gb.json": enrichment,
        "generated/v1/catalog.json": catalog,
        "sources/libretro-no-intro.json": registry,
        "sources/libretro-enrichment.json": registry,
        "reports/enrichment-coverage-v1.json": coverage,
    }
    for name, data in files.items():
        (root / name).write_bytes(encoded(data))
    sources = [
        {"path": name, "bytes": len(encoded(data)),
         "sha256": hashlib.sha256(encoded(data)).hexdigest()}
        for name, data in files.items() if name != "reports/enrichment-coverage-v1.json"
    ]
    (root / "generated/v1/distribution.json").write_bytes(encoded({
        "schema_version": 1, "kind": "ludographium-distribution",
        "source_revision": "pinned", "artifacts": sources,
    }))


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        fixture(self.root)
        self.db = self.root / "output" / "metadata.sqlite"

    def test_all_source_records_and_unresolved_claims_are_retained(self):
        result = build(self.root, self.db)
        self.assertEqual(result, {"games": 3, "media": 4, "claims": 4, "matched": 2, "platforms": 1, "with_metadata": 2})
        with open_readonly(self.db) as conn:
            self.assertEqual(validate(conn, self.root), result)
            self.assertEqual(conn.execute("SELECT count(*) FROM matched_metadata").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT count(*) FROM claims WHERE base_source_ordinal IS NULL").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT count(*) FROM provenance").fetchone()[0], 4)
            self.assertIn("CC-BY-SA-4.0", conn.execute("SELECT source_license FROM platforms").fetchone()[0])
            original = conn.execute("SELECT json_value FROM provenance WHERE key='rights_notice'").fetchone()[0]
            self.assertEqual(json.loads(original), "Fixture provider attribution")

    def test_lookup_preserves_source_evidence_and_does_not_join_revisions(self):
        build(self.root, self.db)
        with open_readonly(self.db) as conn:
            result = query(conn, title="Alpha Game", limit=10)
            self.assertEqual(result["match_count"], 2)
            self.assertEqual(result["matches"][0]["title"], "Alpha Game (USA)")
            self.assertEqual(result["matches"][1]["title"], "Alpha Game (USA) (Rev 1)")
            self.assertEqual(len(result["matches"][0]["metadata_claims"]), 1)
            self.assertEqual(result["matches"][0]["metadata_claims"][0]["source_ordinal"], 1)
            self.assertEqual(result["matches"][0]["metadata_claims"][0]["source_path"], "publisher.dat")
            self.assertEqual(result["matches"][0]["source"]["source_blob_sha"], "gitblob")
            self.assertEqual(result["matches"][0]["metadata_claims"][0]["value"], "Example Company")
            self.assertEqual(query(conn, sha1="B"*40, platform="gb")["matches"][0]["source"]["source_ordinal"], 2)
            self.assertEqual(query(conn, title="Z", platform="gb")["match_count"], 0)
            self.assertEqual(len(query(conn, title="Multifile")["matches"][0]["media"]), 2)
            self.assertEqual(query(conn, title="Multifile")["matches"][0]["metadata_claims"], [])

    def test_build_is_deterministic_and_source_tampering_fails_closed(self):
        build(self.root, self.db)
        first = self.db.read_bytes()
        build(self.root, self.db)
        self.assertEqual(first, self.db.read_bytes())
        target = self.root / "generated/enrichment-v1/gb.json"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            build(self.root, self.db)
        self.assertEqual(first, self.db.read_bytes())

    def test_conflicting_claim_join_is_rejected(self):
        p = self.root / "generated/enrichment-v1/gb.json"
        extra = json.loads(p.read_text())
        extra["claims"][0]["source_comment"] = "Different Game"
        p.write_bytes(encoded(extra))
        manifest_path = self.root / "generated/v1/distribution.json"
        manifest = json.loads(manifest_path.read_text())
        claim = next(x for x in manifest["artifacts"] if x["path"] == "generated/enrichment-v1/gb.json")
        claim["bytes"] = len(p.read_bytes())
        claim["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest_path.write_bytes(encoded(manifest))
        with self.assertRaisesRegex(ValueError, "invalid source-to-claim join"):
            build(self.root, self.db)

    def test_invalid_filters_do_not_turn_into_sql_wildcards(self):
        build(self.root, self.db)
        with open_readonly(self.db) as conn:
            for kwargs in [
                {"title": " "}, {"title": "Game", "sha1": "A"*40},
                {"sha1": "garbage"}, {"title": "Game", "limit": 101}
            ]:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    query(conn, **kwargs)
            self.assertEqual(query(conn, title="%")["match_count"], 0)


if __name__ == "__main__":
    unittest.main()
