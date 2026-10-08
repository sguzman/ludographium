import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from triage_enrichment import review_platform

BASE = {
    "platform": "gb", "source_revision": "rev",
    "records": [{
        "source_ordinal": 7,
        "name": "Example (USA)",
        "roms": [{"crc32": "ABCDEF01", "sha1": "0"*40, "size": 128}],
    }],
}


def claim(field, value, status, comment="Other (USA)"):
    return {
        "field": field, "value": value, "crc32": "ABCDEF01",
        "source_comment": comment, "source_path": f"{field}.dat",
        "source_blob_sha": "1"*40, "source_ordinal": 1,
        "resolution": {"status": status, "base_source_ordinal": None},
    }


class ReviewQueueTests(unittest.TestCase):
    def test_groups_evidence_without_assigning_unresolved_claims(self):
        bundle = {
            "platform": "gb", "source_id": "field-src",
            "source_revision": "rev", "base_source_revision": "rev",
            "claims": [
                claim("developer", "A", "comment_mismatch"),
                claim("publisher", "B", "comment_mismatch"),
                claim("genre", "Puzzle", "matched"),
            ],
        }
        bundle["claims"][-1]["resolution"]["base_source_ordinal"] = 7
        result = review_platform(BASE, bundle, sample_limit=1)
        self.assertEqual(result["source_claims"], 2)
        self.assertEqual(result["review_groups"], 1)
        entry = result["samples"][0]
        self.assertEqual(len(entry["source_claims"]), 2)
        self.assertEqual(entry["candidate_base_records"][0]["base_source_ordinal"], 7)
        self.assertEqual(entry["candidate_base_records"][0]["source_title"], "Example (USA)")
        self.assertEqual(entry["source_title_comment"], "Other (USA)")

    def test_rejects_malformed_unresolved_resolution(self):
        bundle = {"platform": "gb", "source_id": "s", "source_revision": "rev",
                  "base_source_revision": "rev",
                  "claims": [claim("developer", "A", "comment_mismatch")]}
        bundle["claims"][0]["resolution"]["base_source_ordinal"] = 7
        with self.assertRaises(ValueError):
            review_platform(BASE, bundle)

    def test_zero_unresolved_claims(self):
        bundle = {"platform": "gb", "source_id": "s", "source_revision": "rev",
                  "base_source_revision": "rev", "claims": []}
        result = review_platform(BASE, bundle)
        self.assertEqual(result["review_groups"], 0)
        self.assertEqual(result["source_claims"], 0)


if __name__ == "__main__":
    unittest.main()
