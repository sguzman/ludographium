"""Original Libretro DAT sources must remain independently verifiable."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_libretro_sources import query, fold


class OriginalDatSearchTest(unittest.TestCase):
    def test_casefold_is_search_only(self):
        self.assertEqual(fold("POKÉMON"), "pokémon")
        self.assertEqual(fold("ＡＢＣ"), "abc")

    def test_original_gamecom_scope_is_searchable_without_sqlite(self):
        result = query(ROOT, platform="tigergamecom", limit=2)
        self.assertEqual(result["registered_source_platform_scopes"], 75)
        self.assertEqual(result["source_scopes_scanned"], 1)
        self.assertGreater(result["total_filtered_original_source_records"], 0)
        self.assertTrue(all(
            row["source_platform"] == "tigergamecom"
            and row["source_license"] == "CC-BY-SA-4.0"
            and row["original_git_blob_sha"]
            for row in result["records"]
        ))

    def test_invalid_filters_are_rejected_without_source_reads(self):
        for kwargs in (
            {"platform": "not-a-platform"},
            {"sha1": "bad-digest"},
            {"limit": 0},
            {"title": ""},
            {"serial": "x" * 251},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query(ROOT, **kwargs)


if __name__ == "__main__":
    unittest.main()
