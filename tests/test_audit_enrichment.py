import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_enrichment import summarize

BASE = {
    "source_revision": "abc",
    "records": [{"name": "A"}, {"name": "B"}],
}


def claim(field, value, status, ordinal=None):
    return {
        "field": field, "value": value,
        "resolution": {"status": status, "base_source_ordinal": ordinal},
    }


class AuditEnrichmentTests(unittest.TestCase):
    def test_unique_targets_and_conflicting_values(self):
        claims = [
            claim("developer", "X", "matched", 1),
            claim("developer", "Y", "matched", 1),
            claim("publisher", "Z", "matched", 2),
            claim("genre", "Puzzle", "comment_mismatch", None),
        ]
        bundle = {
            "schema_version": 1, "kind": "source-enrichment-claims",
            "platform": "gb", "base_source_revision": "abc",
            "claim_count": 4,
            "resolution_counts": {"matched": 3, "comment_mismatch": 1},
            "claims": claims,
        }
        value = summarize(bundle, BASE)
        self.assertEqual(value["matched_base_records_any_field"], 2)
        self.assertEqual(value["fields"]["developer"]["matched_base_records"], 1)
        self.assertEqual(value["different_values_for_one_field"], 1)
        self.assertEqual(value["conflict_samples"][0]["values"], ["X", "Y"])

    def test_additional_source_field_in_report(self):
        bundle = {
            "schema_version": 1, "kind": "source-enrichment-claims",
            "platform": "gb", "base_source_revision": "abc",
            "claim_count": 1, "resolution_counts": {"matched": 1},
            "claims": [claim("franchise", "Series", "matched", 1)],
        }
        value = summarize(bundle, BASE, fields=("developer", "franchise"))
        self.assertEqual(value["fields"]["franchise"]["matched_base_records"], 1)
        self.assertEqual(value["fields"]["developer"]["claims"], 0)

    def test_invalid_counts(self):
        bundle = {
            "schema_version": 1, "kind": "source-enrichment-claims",
            "platform": "gb", "base_source_revision": "abc",
            "claim_count": 1, "resolution_counts": {}, "claims": [],
        }
        with self.assertRaises(ValueError):
            summarize(bundle, BASE)


if __name__ == "__main__":
    unittest.main()
