"""Read-only original media-source name variance query guards."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_mame_title_variance import query


class SourceNameVarianceQueryTests(unittest.TestCase):
    def test_invalid_filters_fail_before_reading_large_evidence_files(self):
        for kwargs in (
            {"limit": 0},
            {"limit": 201},
            {"limit": True},
            {"source_row": 0},
            {"source_row": True},
            {"source_row": 19026},
            {"variance_class": "verified-error"},
            {"media_sha1": "invalid"},
            {"title": " "},
            {"mame_list": "x" * 251},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query(ROOT, **kwargs)

    def test_every_returned_name_variance_remains_a_source_row(self):
        result = query(ROOT, limit=2)
        self.assertGreater(result["total_original_name_variances"], 0)
        self.assertEqual(result["original_media_evidence_rows"], 19025)
        self.assertEqual(result["returned_name_variances"], 2)
        row = result["records"][0]
        narrowed = query(ROOT, source_row=row["source_media_evidence_row"], limit=1)
        self.assertEqual(narrowed["returned_name_variances"], 1)
        self.assertEqual(
            narrowed["records"][0]["source_media_sha1"], row["source_media_sha1"]
        )
        self.assertIn("review-only", row["interpretation"])


if __name__ == "__main__":
    unittest.main()
