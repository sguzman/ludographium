"""Complete synthetic batch-field ingestion tests: no network or manual curation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_corpus import open_readonly, query
from build_expanded_corpus import build as build_base_expansion, git_blob
from enrich_expanded_corpus import build, field_manifest, validate_fields
from test_build_corpus import fixture as base_fixture
from test_build_expanded_corpus import dat_file


class ExpandedFieldTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        base_fixture(self.root)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.db_base = self.root / "expanded.sqlite"
        self.db = self.root / "complete.sqlite"
        game_dat = dat_file("Brand New Console Game (World)", "E" * 40)
        (self.cache / "exampleconsole.dat").write_bytes(game_dat)
        revision = "f" * 40
        (self.root / "sources/bulk-expansion-v1.json").write_text(json.dumps({
            "schema_version": 1, "kind": "pinned-bulk-platform-expansion",
            "source_id": "libretro-no-intro",
            "repository": "https://github.com/libretro/libretro-database",
            "repository_revision": revision,
            "declared_repository_license": "CC-BY-SA-4.0",
            "base_platform_count": 1,
            "platforms": [{
                "platform": "exampleconsole", "label": "Example Console",
                "source_path": "metadat/no-intro/Example Console.dat",
                "git_blob_sha": git_blob(game_dat), "bytes": len(game_dat),
            }],
        }))
        build_base_expansion(self.root, self.db_base, source_dir=self.cache)
        self.field = (
            'game (\n comment "Brand New Console Game (World)"\n'
            ' publisher "Publisher Inc"\n rom ( crc ABCDEF01 )\n)\n'
        ).encode()
        (self.cache / "exampleconsole--publisher.dat").write_bytes(self.field)
        self.register = {
            "schema_version": 1, "kind": "pinned-bulk-bibliographic-expansion",
            "source_id": "libretro-metadata",
            "base_source_id": "libretro-no-intro",
            "repository": "https://github.com/libretro/libretro-database",
            "repository_revision": revision,
            "declared_repository_license": "CC-BY-SA-4.0",
            "files": [{
                "platform": "exampleconsole", "field": "publisher",
                "source_path": "metadat/publisher/Example Console.dat",
                "git_blob_sha": git_blob(self.field), "bytes": len(self.field),
            }],
        }
        self.update_register()

    def update_register(self):
        (self.root / "sources/bulk-fields-v1.json").write_text(json.dumps(self.register))

    def test_all_field_sources_are_preserved_and_matched_only_to_exact_records(self):
        result = build(self.root, self.db_base, self.db, cache_dir=self.cache)
        self.assertEqual(result, {
            "platforms": 2, "games": 4, "media": 5,
            "claims": 5, "matched": 3, "with_metadata": 3,
        })
        with open_readonly(self.db) as conn:
            self.assertEqual(validate_fields(conn, field_manifest(self.root)), result)
            matched = query(conn, title="Brand New Console")["matches"][0]
            self.assertEqual(matched["metadata_claims"][0]["value"], "Publisher Inc")
            self.assertEqual(matched["metadata_claims"][0]["source_path"],
                             "metadat/publisher/Example Console.dat")
            archive = conn.execute(
                "SELECT dat_bytes FROM field_archives WHERE platform='exampleconsole'"
            ).fetchone()[0]
            self.assertEqual(archive, self.field)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM claims WHERE resolution_status='comment_mismatch'"
            ).fetchone()[0], 1)

    def test_does_not_attach_identical_crc_when_original_titles_disagree(self):
        self.field = self.field.replace(
            b'comment "Brand New Console Game (World)"',
            b'comment "Different Product"',
        )
        (self.cache / "exampleconsole--publisher.dat").write_bytes(self.field)
        self.register["files"][0]["bytes"] = len(self.field)
        self.register["files"][0]["git_blob_sha"] = git_blob(self.field)
        self.update_register()
        build(self.root, self.db_base, self.db, cache_dir=self.cache)
        with open_readonly(self.db) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM claims WHERE platform='exampleconsole' "
                "AND resolution_status='comment_mismatch'"
            ).fetchone()[0], 1)
            self.assertEqual(query(conn, title="Brand New Console")["matches"][0]["metadata_claims"], [])

    def test_serial_only_claim_remains_unresolved_without_fabricated_crc(self):
        self.field = (
            'game (\n comment "Brand New Console Game (World)"\n'
            ' rom (\n  serial "ULUS-10080"\n )\n)\n'
        ).encode()
        (self.cache / "exampleconsole--serial.dat").write_bytes(self.field)
        self.register["files"][0]["field"] = "serial"
        self.register["files"][0]["source_path"] = "metadat/serial/Example Console.dat"
        self.register["files"][0]["bytes"] = len(self.field)
        self.register["files"][0]["git_blob_sha"] = git_blob(self.field)
        self.update_register()
        result = build(self.root, self.db_base, self.db, cache_dir=self.cache)
        self.assertEqual(result["claims"], 5)
        self.assertEqual(result["matched"], 2)
        with open_readonly(self.db) as conn:
            value, crc, status, target, fields = conn.execute(
                "SELECT value,crc32,resolution_status,base_source_ordinal,source_fields_json "
                "FROM claims WHERE platform='exampleconsole'"
            ).fetchone()
            self.assertEqual(value, "ULUS-10080")
            self.assertIsNone(crc)
            self.assertEqual(status, "missing_crc")
            self.assertIsNone(target)
            self.assertEqual(json.loads(fields)["rom_serial"], "ULUS-10080")
            self.assertEqual(query(conn, title="Brand New Console")["matches"][0]["metadata_claims"], [])

    def test_repeatable_export_and_tamper_rejection(self):
        build(self.root, self.db_base, self.db, cache_dir=self.cache)
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        build(self.root, self.db_base, self.db, cache_dir=self.cache)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.cache.joinpath("exampleconsole--publisher.dat").write_bytes(self.field + b"bad")
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            build(self.root, self.db_base, self.db, cache_dir=self.cache)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)

    def test_bad_field_and_mutated_blob_rejected(self):
        self.register["files"].append(dict(self.register["files"][0]))
        self.update_register()
        with self.assertRaisesRegex(ValueError, "repeated"):
            field_manifest(self.root)
        self.register["files"] = self.register["files"][:1]
        self.update_register()
        build(self.root, self.db_base, self.db, cache_dir=self.cache)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE field_archives SET dat_bytes=?", (b"broken",))
        with open_readonly(self.db) as conn, self.assertRaisesRegex(ValueError, "field archive source corruption"):
            validate_fields(conn, field_manifest(self.root))


if __name__ == "__main__":
    unittest.main()
