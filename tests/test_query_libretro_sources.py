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

    def test_original_records_can_be_paged_without_reidentification(self):
        initial = query(ROOT, platform="tigergamecom", limit=3)
        shifted = query(ROOT, platform="tigergamecom", offset=1, limit=2)
        self.assertEqual(
            initial["total_filtered_original_source_records"],
            shifted["total_filtered_original_source_records"],
        )
        self.assertEqual(initial["records"][1:], shifted["records"])
        self.assertEqual(shifted["offset"], 1)
        self.assertEqual(shifted["next_offset"], 3)
        self.assertTrue(all(
            item["source_license"] == "CC-BY-SA-4.0"
            for item in shifted["records"]
        ))
        count = initial["total_filtered_original_source_records"]
        last = query(ROOT, platform="tigergamecom", offset=count - 1, limit=2)
        self.assertEqual(last["returned_original_source_records"], 1)
        self.assertIsNone(last["next_offset"])
        for offset in (-1, True, "1", 1_000_001):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                query(ROOT / "nonexistent", offset=offset)

    def test_additive_review_cohort_excludes_verified_third_wave_leads(self):
        original = query(
            ROOT, platform="atari5200", without_review_leads=True, limit=1
        )
        combined = query(
            ROOT, platform="atari5200", without_review_leads=True,
            review_cohort="combined", limit=1,
        )
        self.assertEqual(original["review_evidence_cohorts"], ["baseline"])
        self.assertEqual(combined["review_evidence_cohorts"], ["baseline", "v3"])
        self.assertGreater(
            original["total_filtered_original_source_records"],
            combined["total_filtered_original_source_records"],
        )
        self.assertEqual(
            original["scanned_original_source_records"],
            combined["scanned_original_source_records"],
        )
        # Unrelated source scopes retain original review-gap membership.
        old = query(ROOT, platform="n64", without_review_leads=True, limit=1)
        new = query(
            ROOT, platform="n64", without_review_leads=True,
            review_cohort="combined", limit=1,
        )
        self.assertEqual(
            old["total_filtered_original_source_records"],
            new["total_filtered_original_source_records"],
        )
        with self.assertRaises(ValueError):
            query(ROOT, review_cohort="combined")
        with self.assertRaises(ValueError):
            query(ROOT, review_cohort="unregistered")

    def test_fourth_cohort_only_removes_verified_watara_review_gaps(self):
        older = query(
            ROOT, platform="watarasupervision", without_review_leads=True,
            review_cohort="combined", limit=2,
        )
        complete = query(
            ROOT, platform="watarasupervision", without_review_leads=True,
            review_cohort="all-pinned", limit=2,
        )
        self.assertEqual(
            older["total_filtered_original_source_records"]
            - complete["total_filtered_original_source_records"], 70
        )
        self.assertEqual(
            complete["review_evidence_cohorts"], ["baseline", "v3", "v4"]
        )
        self.assertEqual(
            older["scanned_original_source_records"],
            complete["scanned_original_source_records"],
        )
        unmodified = query(
            ROOT, platform="n64", without_review_leads=True,
            review_cohort="all-pinned", limit=1,
        )
        self.assertEqual(
            unmodified["total_filtered_original_source_records"], query(
                ROOT, platform="n64", without_review_leads=True,
                review_cohort="combined", limit=1,
            )["total_filtered_original_source_records"],
        )

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
