"""Third MAME source wave preserves noncanonical title-review scope."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reconcile_mame_v3_titles import build_expected


class AdditiveMameV3Titles(unittest.TestCase):
    def test_only_separately_registered_v3_unmatched_observations(self):
        raw, payload = build_expected(ROOT)
        report = json.loads(payload)
        self.assertEqual(report["original_mame_source_lists"], 4)
        self.assertEqual(report["original_software_observations"], 166)
        self.assertEqual(report["original_software_with_sha1_source_leads"], 127)
        self.assertEqual(report["original_software_without_sha1_source_leads"], 39)
        self.assertEqual(
            report["original_title_review_candidate_pairs"], len(raw.splitlines())
        )
        self.assertGreater(report["eligible_source_scope_pairs"], 0)
        self.assertTrue(all(
            json.loads(row)["interpretation"].startswith("review-only-")
            and json.loads(row)["mame"]["source_cohort"] == "v3"
            for row in raw.splitlines()
        ))


if __name__ == "__main__":
    unittest.main()
