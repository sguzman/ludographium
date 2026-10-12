"""Offline bulk provider-acquisition gap audit invariants."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_source_review_gaps import build_report


class SourceReviewAcquisitionGaps(unittest.TestCase):
    def test_65_source_lists_and_complete_nonidentity_coverage_partition(self):
        report = build_report(ROOT)
        self.assertEqual(report["independent_mame_source_lists"], 65)
        totals = report["original_source_observation_totals"]
        self.assertEqual(totals["original_software_entries"], 32953)
        self.assertEqual(totals["exact_media_supported_original_records"], 19013)
        self.assertEqual(totals["conservative_title_only_original_records"], 2699)
        self.assertEqual(totals["original_records_without_any_review_lead"], 11241)
        self.assertEqual(totals["ambiguous_original_review_units"], 2042)
        self.assertEqual(
            totals["exact_media_supported_original_records"]
            + totals["conservative_title_only_original_records"]
            + totals["original_records_without_any_review_lead"],
            totals["original_software_entries"],
        )
        self.assertIn("not imply an absent game", report["interpretation"])


if __name__ == "__main__":
    unittest.main()
