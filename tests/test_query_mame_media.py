"""Read-only pagination over pinned SHA-1 media evidence cohorts."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_mame_media import query


class PinnedMediaEvidencePaginationTests(unittest.TestCase):
    def test_combined_pages_cross_the_65_plus_4_list_boundary(self):
        page = query(ROOT, cohort="combined", offset=19023, limit=4)
        self.assertEqual(page["total_original_candidate_pairs"], 19152)
        self.assertEqual(page["total_filtered_candidate_pairs"], 19152)
        self.assertEqual(page["returned_candidate_pairs"], 4)
        self.assertEqual(page["offset"], 19023)
        self.assertEqual(page["next_offset"], 19027)
        self.assertEqual(
            [pair["source_evidence_cohort"] for pair in page["pairs"]],
            ["baseline", "baseline", "v3", "v3"],
        )
        self.assertEqual(page["independent_mame_source_lists"], 69)

    def test_independent_third_cohort_has_stable_page_order(self):
        first = query(ROOT, cohort="v3", limit=2)
        next_page = query(ROOT, cohort="v3", offset=1, limit=1)
        self.assertEqual(first["total_original_candidate_pairs"], 127)
        self.assertEqual(next_page["pairs"][0], first["pairs"][1])
        last = query(ROOT, cohort="v3", offset=126, limit=5)
        self.assertEqual(last["returned_candidate_pairs"], 1)
        self.assertIsNone(last["next_offset"])
        empty = query(ROOT, cohort="v3", offset=127, limit=5)
        self.assertEqual(empty["returned_candidate_pairs"], 0)
        self.assertIsNone(empty["next_offset"])

    def test_fourth_cohort_and_full_77_list_media_evidence_are_independent(self):
        fourth = query(ROOT, cohort="v4", limit=3)
        self.assertEqual(fourth["total_original_candidate_pairs"], 70)
        self.assertEqual(fourth["total_filtered_candidate_pairs"], 70)
        self.assertEqual(fourth["independent_mame_source_lists"], 8)
        self.assertTrue(all(
            row["source_evidence_cohort"] == "v4"
            and row["mame"]["source_list"] == "svision"
            and row["libretro"]["platform"] == "watarasupervision"
            and row["size_corroborated"]
            for row in fourth["pairs"]
        ))
        all_pinned = query(ROOT, cohort="all-pinned", offset=19150, limit=4)
        self.assertEqual(all_pinned["total_original_candidate_pairs"], 19222)
        self.assertEqual(all_pinned["independent_mame_source_lists"], 77)
        self.assertEqual(all_pinned["source_cohorts"], ["baseline", "v3", "v4"])
        self.assertEqual(
            [row["source_evidence_cohort"] for row in all_pinned["pairs"]],
            ["v3", "v3", "v4", "v4"],
        )
        self.assertEqual(all_pinned["next_offset"], 19154)
        end = query(ROOT, cohort="v4", offset=69, limit=3)
        self.assertEqual(end["returned_candidate_pairs"], 1)
        self.assertIsNone(end["next_offset"])
        original = query(ROOT, cohort="combined", limit=1)
        self.assertEqual(original["total_original_candidate_pairs"], 19152)

    def test_bounded_offsets_are_checked_before_reading_original_sources(self):
        for offset in (-1, True, "4", 1_000_001):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                query(ROOT / "nonexistent", offset=offset)


if __name__ == "__main__":
    unittest.main()
