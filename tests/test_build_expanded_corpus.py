"""Batch expansion tests use pinned synthetic DAT bytes; no network or ROMs."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_expanded_corpus import build, git_blob, pinned_manifest, validate_expanded
from build_corpus import open_readonly, query
from test_build_corpus import fixture


def dat_file(title, sha1):
    return (
        'clrmamepro (\n name "Synthetic console"\n version "pinned"\n)\n'
        'game (\n'
        f' name "{title}"\n'
        ' region "World"\n'
        f' rom ( name "candidate.bin" size 128 crc ABCDEF01 sha1 {sha1} )\n'
        ')\n'
    ).encode("utf-8")


class ExpandedCorpusTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        fixture(self.root)
        self.source_dir = self.root / "cache"
        self.source_dir.mkdir()
        self.db = self.root / "results" / "expanded.sqlite"
        self.source = dat_file("Brand New Console Game (World)", "E" * 40)
        (self.source_dir / "exampleconsole.dat").write_bytes(self.source)
        self.manifest_file = self.root / "sources" / "bulk-expansion-v1.json"
        self.manifest = {
            "schema_version": 1,
            "kind": "pinned-bulk-platform-expansion",
            "source_id": "libretro-no-intro",
            "repository": "https://github.com/libretro/libretro-database",
            "repository_revision": "f" * 40,
            "declared_repository_license": "CC-BY-SA-4.0",
            "base_platform_count": 1,
            "platforms": [{
                "platform": "exampleconsole",
                "label": "Example Console",
                "source_path": "metadat/no-intro/Example Console.dat",
                "git_blob_sha": git_blob(self.source),
                "bytes": len(self.source),
            }],
        }
        self.flush_manifest()

    def flush_manifest(self):
        self.manifest_file.write_text(json.dumps(self.manifest))

    def test_batch_adds_all_and_preserves_old_sources_and_field_claims(self):
        result = build(self.root, self.db, source_dir=self.source_dir)
        self.assertEqual(result, {
            "platforms": 2, "games": 4, "media": 5, "claims": 4,
            "matched": 2, "with_metadata": 2,
        })
        with open_readonly(self.db) as conn:
            self.assertEqual(validate_expanded(conn, pinned_manifest(self.root)), result)
            self.assertEqual(
                query(conn, title="Brand New Console")["matches"][0]["platform"],
                "exampleconsole",
            )
            self.assertEqual(
                query(conn, sha1="E" * 40)["matches"][0]["source"]["source_path"],
                "metadat/no-intro/Example Console.dat",
            )
            self.assertEqual(conn.execute(
                "SELECT dat_bytes FROM source_archives WHERE platform='exampleconsole'"
            ).fetchone()[0], self.source)
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM claims WHERE resolution_status='comment_mismatch'"
            ).fetchone()[0], 1)

    def test_deterministic_no_hidden_serial_curation(self):
        build(self.root, self.db, source_dir=self.source_dir)
        before = hashlib.sha256(self.db.read_bytes()).digest()
        build(self.root, self.db, source_dir=self.source_dir)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).digest(), before)

    def test_rejects_corrupt_source_without_overwriting_previous_build(self):
        build(self.root, self.db, source_dir=self.source_dir)
        previous = hashlib.sha256(self.db.read_bytes()).hexdigest()
        (self.source_dir / "exampleconsole.dat").write_bytes(self.source + b"modified")
        with self.assertRaisesRegex(ValueError, "SHA mismatch"):
            build(self.root, self.db, source_dir=self.source_dir)
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), previous)

    def test_rejects_collision_and_bad_manifest_path(self):
        self.manifest["platforms"].append(dict(self.manifest["platforms"][0]))
        self.flush_manifest()
        with self.assertRaisesRegex(ValueError, "repeated expansion platform"):
            pinned_manifest(self.root)
        self.manifest["platforms"] = self.manifest["platforms"][:1]
        self.manifest["platforms"][0]["source_path"] = "../escape.dat"
        self.flush_manifest()
        with self.assertRaisesRegex(ValueError, "upstream source path"):
            pinned_manifest(self.root)

    def test_corruption_fails_integrity_after_build(self):
        build(self.root, self.db, source_dir=self.source_dir)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE source_archives SET dat_bytes=?", (b"tampered",))
        with open_readonly(self.db) as conn, self.assertRaisesRegex(ValueError, "archived DAT"):
            validate_expanded(conn, pinned_manifest(self.root))


if __name__ == "__main__":
    unittest.main()
