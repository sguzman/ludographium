import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from import_enrichment import blob_sha, import_platform, parse_field_dat

SOURCE = b'''clrmamepro (\n name "GB"\n)\ngame (\n comment "Sample (USA)"\n developer "Example Studio"\n rom ( crc ABCD1234 )\n)\ngame (\n developer "Unknown Credit"\n rom ( crc 98765432 )\n)'''
BASE = {
    "kind": "source-observations", "platform": "gb", "source_id": "no-intro",
    "source_revision": "abc", "records": [
        {"source_ordinal": 1, "name": "Sample (USA)", "roms": [{"crc32": "ABCD1234"}]},
        {"source_ordinal": 2, "name": "Other", "roms": [{"crc32": "98765432"}]},
    ]
}


class EnrichmentTests(unittest.TestCase):
    def test_parser_and_missing_comment(self):
        rows = parse_field_dat(SOURCE, field="developer")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["value"], "Example Studio")
        self.assertEqual(rows[0]["source_ordinal"], 1)
        self.assertIsNone(rows[1]["comment"])

    def test_multiline_crc_records(self):
        raw = b'''game (
 comment "Sample (USA)"
 developer "Studio"
 rom (
  crc ABCD1234
 )
)'''
        rows = parse_field_dat(raw, field="developer")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["crc32"], "ABCD1234")
        with self.assertRaisesRegex(ValueError, "unterminated ROM"):
            parse_field_dat(raw.replace(b"\n )\n)", b"\n)"), field="developer")

    def test_numeric_source_fields_preserve_original_atoms(self):
        raw = b'''game (
 comment "Example (USA)"
 users 4
 rom ( crc ABCD1234 )
)
game (
 comment "Other (USA)"
 rumble 1
 rom (
  crc DEADBEEF
 )
)'''
        users = parse_field_dat(raw, field="users")
        rumble = parse_field_dat(raw, field="rumble")
        self.assertEqual(users[0]["value"], "4")
        self.assertEqual(users[0]["source_fields"]["users"], "4")
        self.assertEqual(rumble[1]["value"], "1")
        self.assertIsNone(rumble[0]["value"])

    def test_bad_fields_fail_closed(self):
        malformed = SOURCE.replace(b'developer "Example Studio"', b'developer (bad)')
        with self.assertRaisesRegex(ValueError, "unsupported source line"):
            parse_field_dat(malformed, field="developer")
        with self.assertRaises(ValueError):
            parse_field_dat(SOURCE.replace(b"ABCD1234", b"NOPE"), field="developer")

    def test_import_resolves_only_exact_title_plus_crc(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "generated/v1").mkdir(parents=True)
            (root / "archive/libretro-enrichment/gb").mkdir(parents=True)
            (root / "generated/v1/gb.json").write_text(json.dumps(BASE))
            (root / "archive/libretro-enrichment/gb/developer.dat").write_bytes(SOURCE)
            registry = {
                "source_id": "libretro-enrichment", "repository_revision": "abc",
                "files": [{"platform": "gb", "field": "developer", "source_path": "x.dat",
                           "git_blob_sha": blob_sha(SOURCE)}],
            }
            data = import_platform(root, registry, "gb")
            self.assertEqual(data["resolution_counts"], {"matched": 1, "missing_comment": 1})
            self.assertEqual(data["claims"][0]["resolution"]["base_source_ordinal"], 1)
            self.assertIsNone(data["claims"][1]["resolution"]["base_source_ordinal"])

            BASE["records"][0]["name"] = "Changed"
            (root / "generated/v1/gb.json").write_text(json.dumps(BASE))
            other = import_platform(root, registry, "gb")
            self.assertEqual(other["claims"][0]["resolution"]["status"], "comment_mismatch")
            BASE["records"][0]["name"] = "Sample (USA)"

    def test_unknown_fields_preserved(self):
        raw = b'game (\n comment "Sample (USA)"\n developer "Studio"\n franchise "Other"\n rom ( crc ABCD1234 )\n)'
        rows = parse_field_dat(raw, field="developer")
        self.assertEqual(rows[0]["source_fields"]["franchise"], "Other")

    def test_hash_rejects_modified_archive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "generated/v1").mkdir(parents=True)
            (root / "archive/libretro-enrichment/gb").mkdir(parents=True)
            (root / "generated/v1/gb.json").write_text(json.dumps(BASE))
            (root / "archive/libretro-enrichment/gb/developer.dat").write_bytes(SOURCE + b"extra")
            reg = {"source_id": "libretro-enrichment", "repository_revision": "abc",
                   "files": [{"platform": "gb", "field": "developer",
                              "source_path": "x", "git_blob_sha": blob_sha(SOURCE)}]}
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                import_platform(root, reg, "gb")


if __name__ == "__main__":
    unittest.main()
