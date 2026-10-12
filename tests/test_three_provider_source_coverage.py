"""Cross-provider coverage classification is evidence-only, not an identity join."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_three_provider_source_coverage import source_coverage_class


class ProviderEvidenceClassTest(unittest.TestCase):
    def test_conservative_four_way_source_yield_partition(self):
        self.assertEqual(
            source_coverage_class(True, True),
            "both-independent-secondary-source-families",
        )
        self.assertEqual(
            source_coverage_class(True, False),
            "wikidata-source-rows-only",
        )
        self.assertEqual(
            source_coverage_class(False, True),
            "mame-exact-media-evidence-only",
        )
        self.assertEqual(
            source_coverage_class(False, False),
            "neither-secondary-source-family-observed",
        )


if __name__ == "__main__":
    unittest.main()
