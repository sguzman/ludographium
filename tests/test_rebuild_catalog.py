import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fetch_pinned_sources import git_blob_sha, pinned_url, source_path
from rebuild_catalog import rebuild


class SourceRebuildTests(unittest.TestCase):
    def test_blob_and_safe_paths(self):
        data = b"test"
        expected = hashlib.sha1(b"blob 4\0test").hexdigest()
        self.assertEqual(git_blob_sha(data), expected)
        self.assertEqual(str(source_path({"platform": "gb"}, "base")),
                         "archive/libretro-no-intro/gb.dat")
        self.assertEqual(str(source_path({"platform": "gba", "field": "publisher"}, "enrichment")),
                         "archive/libretro-enrichment/gba/publisher.dat")
        with self.assertRaises(ValueError):
            source_path({"platform": "../evil"}, "base")

    def test_rejects_unpinned_url(self):
        reg = {"repository": "https://github.com/libretro/libretro-database",
               "repository_revision": "not-a-real-commit"}
        with self.assertRaises(ValueError):
            pinned_url(reg, {"source_path": "metadat/no-intro/gb.dat"})

    def test_rebuild_single_platform(self):
        dat = b'''clrmamepro (
 name "Game Boy"
 version "1"
)
game (
 name "Example (USA)"
 rom ( name "Example.gb" size 1024 crc ABCDEF01 md5 00000000000000000000000000000000 sha1 1111111111111111111111111111111111111111 )
)'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sources").mkdir()
            (root / "archive/libretro-no-intro").mkdir(parents=True)
            (root / "archive/libretro-no-intro/gb.dat").write_bytes(dat)
            source = {
                "source_id": "demo", "repository_revision": "abc",
                "declared_repository_license": "example",
                "files": [{"platform": "gb", "source_path": "file.dat",
                           "git_blob_sha": git_blob_sha(dat)}],
            }
            (root / "sources/libretro-no-intro.json").write_text(json.dumps(source))
            produced = rebuild(root)
            self.assertEqual(json.loads(produced["generated/v1/gb.json"])["record_count"], 1)
            catalog = json.loads(produced["generated/v1/catalog.json"])
            self.assertEqual(catalog["platforms"][0]["platform"], "gb")


if __name__ == "__main__":
    unittest.main()
