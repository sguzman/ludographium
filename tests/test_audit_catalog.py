import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_catalog import summarize


class CoverageTests(unittest.TestCase):
    def test_counts_and_repeated_occurrences(self):
        bundle = {
            "schema_version": 1, "kind": "source-observations", "platform": "gb",
            "record_count": 2, "rom_count": 2,
            "records": [
                {
                    "name": "Example", "region": "USA",
                    "roms": [{"name": "a.gb", "size": 1024, "crc32": "11111111",
                              "sha1": "A"*40, "md5": "B"*32}]
                },
                {
                    "name": "Example",
                    "roms": [{"name": "b.gb", "size": 1024, "crc32": "11111111",
                              "sha1": "A"*40, "md5": "C"*32}]
                },
            ],
        }
        report = summarize(bundle)
        self.assertEqual(report["source_records"], 2)
        self.assertEqual(report["record_field_presence"]["region"], 1)
        self.assertEqual(report["record_field_presence"]["serial"], 0)
        self.assertEqual(report["media_field_presence"]["sha1"], 2)
        self.assertEqual(report["repeated_sha1_groups"], {"groups": 1, "source_occurrences": 2})
        self.assertEqual(report["multi_match_crc32_size_groups"], {"groups": 1, "source_occurrences": 2})
        self.assertEqual(report["identical_title_groups"], {"groups": 1, "source_occurrences": 2})

    def test_rejects_incorrect_counts(self):
        with self.assertRaises(ValueError):
            summarize({"schema_version": 1, "kind": "source-observations",
                       "record_count": 1, "rom_count": 0, "records": []})


if __name__ == "__main__":
    unittest.main()
