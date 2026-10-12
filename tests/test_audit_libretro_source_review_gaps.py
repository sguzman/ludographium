"""Evidence gap categories must be exclusive and source-only."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_libretro_source_review_gaps import evidence_status


class OriginalLibretroGapClasses(unittest.TestCase):
    def test_all_supported_combinations_are_distinct(self):
        self.assertEqual(evidence_status(False, False), "no-review-lead")
        self.assertEqual(evidence_status(True, False), "media-only")
        self.assertEqual(evidence_status(False, True), "title-only")
        self.assertEqual(evidence_status(True, True), "both-media-and-title")


if __name__ == "__main__":
    unittest.main()
