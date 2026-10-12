"""Offline three-provider coverage query invariants."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_three_provider_source_coverage import query


class ThreeProviderCoverageQueryTest(unittest.TestCase):
    def test_invalid_filters_reject_without_loading_corpus(self):
        for kwargs in (
            {"limit": 0}, {"limit": 201}, {"limit": True},
            {"min_source_records": -1}, {"min_source_records": True},
            {"wikidata_registered": "true"}, {"platform": " "},
            {"coverage_class": "verified-games"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query(ROOT, **kwargs)

    def test_all_original_collections_and_no_secondary_evidence_scope(self):
        current = query(ROOT, limit=2)
        self.assertEqual(current["libretro_source_collection_count"], 75)
        self.assertEqual(current["returned_source_collections"], 2)
        missing = query(
            ROOT, coverage_class="neither-secondary-source-family-observed",
            limit=20,
        )
        self.assertEqual(missing["total_filtered_original_source_collections"], 11)
        self.assertEqual(missing["returned_source_collections"], 11)
        self.assertTrue(all(
            row["source_media_candidate_rows"] == 0
            and not row["wikidata_registered_platform_has_any_source_rows"]
            for row in missing["source_collections"]
        ))


if __name__ == "__main__":
    unittest.main()
