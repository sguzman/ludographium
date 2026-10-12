"""Offline title-review search guards and provenance assertions."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_mame_title_review import query


class ConservativeTitleQueryTests(unittest.TestCase):
    def test_full_verified_title_review_inventory(self):
        result = query(ROOT, limit=2)
        self.assertEqual(result["original_source_candidate_pairs"], 6825)
        self.assertEqual(result["distinct_original_mame_records_with_candidates"], 2699)
        self.assertEqual(result["returned_candidate_pairs"], 2)
        self.assertTrue(all(
            row["interpretation"].startswith("review-only-")
            and row["source_scope_pair_sha1_supported_mame_records"] >= 3
            for row in result["pairs"]
        ))
        self.assertIn("not a verified game", result["interpretation"])

    def test_ambiguity_and_filters_keep_all_provenance(self):
        result = query(ROOT, ambiguous_only=True, limit=4)
        self.assertGreater(result["total_filtered_candidate_pairs"], 0)
        self.assertTrue(all(
            row["is_ambiguous_among_source_review_candidates"]
            and row["source_review_alternatives_for_same_mame_record"] > 1
            for row in result["pairs"]
        ))
        with self.assertRaises(ValueError):
            query(ROOT, min_scope_support=2)
        with self.assertRaises(ValueError):
            query(ROOT, title=" ")


if __name__ == "__main__":
    unittest.main()
