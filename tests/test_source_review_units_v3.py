"""Pin 133 additive review units without game-identity inference."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_source_review_units_v3 import build_expected


class AdditiveSourceReviewUnitsTests(unittest.TestCase):
    def test_all_separate_v3_review_evidence_survives_and_has_stable_ids(self):
        raw, text = build_expected(ROOT)
        metadata = json.loads(text)
        self.assertEqual(metadata["additional_original_review_units"], 133)
        self.assertEqual(metadata["unchanged_prior_source_review_units"], 21712)
        self.assertEqual(metadata["cumulative_separate_source_review_units"], 21845)
        self.assertEqual(len(raw.splitlines()), 133)
        rows = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len({r["stable_review_id"] for r in rows}), 133)
        self.assertTrue(all(
            row["stable_review_id"].startswith("lgreview:v1:")
            and row["mame"]["source_cohort"] == "v3"
            and row["review_status"] == "unreviewed-original-evidence"
            and row["interpretation"].startswith("review-task-only-")
            for row in rows
        ))


if __name__ == "__main__":
    unittest.main()
