"""Classify differing original source display names without asserting identity."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_mame_title_variance import classification


class OriginalDisplayNameVarianceTests(unittest.TestCase):
    def test_names_are_equal_only_after_conservative_normalization(self):
        self.assertEqual(
            classification("Tetris", "Tetris"),
            "exact-original-title",
        )
        self.assertEqual(
            classification("Tetris", "Tetris (World) (En,Ja)"),
            "equal-after-conservative-normalization",
        )

    def test_disagreement_remains_review_only(self):
        self.assertEqual(
            classification("Mario", "Luigi"),
            "different-normalized-titles",
        )
        self.assertEqual(
            classification("Mario Bros.", "Mario Bros. ~ Mario Brothers"),
            "one-title-contained-in-another",
        )
        self.assertEqual(
            classification("", "Mario"),
            "missing-source-title",
        )
        self.assertEqual(
            classification("Batman (Prototype)", "Batman (World)"),
            "different-normalized-titles",
        )


if __name__ == "__main__":
    unittest.main()
