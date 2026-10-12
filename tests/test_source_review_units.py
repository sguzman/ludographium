"""Tests for noncanonical deterministic review IDs and evidence paths."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_source_review_units import original_review_id


class StableReviewIdentifierTests(unittest.TestCase):
    def test_deterministic_only_within_same_pinned_original_source(self):
        digest = "a" * 64
        value = original_review_id("gamecom", digest, 1)
        self.assertEqual(value, original_review_id("gamecom", digest, 1))
        self.assertTrue(value.startswith("lgreview:v1:"))
        self.assertNotEqual(value, original_review_id("gamecom", digest, 2))
        self.assertNotEqual(value, original_review_id("gamecom", "b" * 64, 1))
        self.assertNotEqual(value, original_review_id("wswan", digest, 1))

    def test_rejects_unsafe_or_missing_review_coordinates(self):
        for name, sha, ordinal in (
            ("../scope", "a" * 64, 1), ("gamecom", "xyz", 1),
            ("gamecom", "a" * 64, 0), ("", "a" * 64, 1),
        ):
            with self.subTest(name=name, sha=sha, ordinal=ordinal):
                with self.assertRaises(ValueError):
                    original_review_id(name, sha, ordinal)


if __name__ == "__main__":
    unittest.main()
