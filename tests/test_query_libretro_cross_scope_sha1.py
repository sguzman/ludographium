"""Guard source-only cross-platform fingerprint group search."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_libretro_cross_scope_sha1 import query


class CrossScopeQueryTests(unittest.TestCase):
    def test_reject_malformed_filters_before_scanning_original_source(self):
        for kwargs in (
            {"limit": 0}, {"limit": 201}, {"limit": True},
            {"minimum_scopes": 1}, {"minimum_scopes": 76},
            {"minimum_scopes": True}, {"sha1": "not-valid"},
            {"title": " "}, {"platform": "x" * 251},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query(ROOT, **kwargs)

    def test_returned_groups_remain_unreviewed_source_observations(self):
        result = query(ROOT, limit=2)
        self.assertEqual(result["independent_source_collections"], 75)
        self.assertGreater(result["total_cross_scope_fingerprint_groups"], 0)
        self.assertGreater(result["returned_fingerprint_groups"], 0)
        for record in result["groups"]:
            self.assertGreaterEqual(record["distinct_source_scope_count"], 2)
            self.assertIn("no-canonical", record["interpretation"])
            self.assertEqual(record["source_license"], "CC-BY-SA-4.0")


if __name__ == "__main__":
    unittest.main()
