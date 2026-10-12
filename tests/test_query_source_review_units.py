"""Verified search over stable-ID source review units and original evidence."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_source_review_units import query


class StableReviewQueryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = query(ROOT, limit=1)

    def test_full_source_queue_and_unadjudicated_read(self):
        result = self.summary
        self.assertEqual(result["total_pinned_source_review_units"], 21712)
        self.assertEqual(result["returned_source_review_units"], 1)
        first = result["units"][0]
        self.assertTrue(first["stable_review_id"].startswith("lgreview:v1:"))
        self.assertEqual(first["review_status"], "unreviewed-original-evidence")
        self.assertIn("not accepted games", result["interpretation"])

    def test_stable_id_query_and_original_evidence_lookup(self):
        first_id = self.summary["units"][0]["stable_review_id"]
        result = query(ROOT, review_id=first_id, include_evidence=True, limit=1)
        self.assertEqual(result["total_filtered_source_review_units"], 1)
        first = result["units"][0]
        self.assertEqual(first["stable_review_id"], first_id)
        self.assertEqual(
            len(first["original_media_evidence"]) + len(first["original_title_evidence"]),
            len(first["media_evidence_jsonl_source_ordinals"])
            + len(first["title_evidence_jsonl_source_ordinals"]),
        )

    def test_ambiguity_and_distinct_evidence_types(self):
        self.assertGreater(query(ROOT, ambiguous_only=True, limit=1)[
            "total_filtered_source_review_units"
        ], 0)
        self.assertGreater(query(ROOT, evidence_type="title", limit=1)[
            "total_filtered_source_review_units"
        ], 0)
        self.assertGreater(query(ROOT, evidence_type="media", limit=1)[
            "total_filtered_source_review_units"
        ], 0)

    def test_additive_source_review_cohort_is_searchable_without_conflation(self):
        third = query(ROOT, cohort="v3", limit=2, include_evidence=True)
        self.assertEqual(third["total_pinned_source_review_units"], 133)
        self.assertEqual(third["returned_source_review_units"], 2)
        self.assertTrue(all(
            item["mame"]["source_cohort"] == "v3"
            and item["review_status"] == "unreviewed-original-evidence"
            and (
                len(item["original_media_evidence"])
                + len(item["original_title_evidence"])
            ) > 0
            for item in third["units"]
        ))
        self.assertEqual(
            query(ROOT, cohort="v3", ambiguous_only=True, limit=1)[
                "total_filtered_source_review_units"
            ], 2
        )
        combined = query(ROOT, cohort="combined", limit=1)
        self.assertEqual(combined["total_pinned_source_review_units"], 21845)
        self.assertEqual(combined["source_cohorts"], ["baseline", "v3"])
        with self.assertRaises(ValueError):
            query(ROOT, cohort="unsafe")

    def test_pages_across_original_and_additive_review_cohorts(self):
        # Deterministic original-source order, including the cross-cohort
        # boundary. No previously assigned stable review ID is reissued.
        boundary = query(ROOT, cohort="combined", offset=21710, limit=5)
        self.assertEqual(boundary["total_filtered_source_review_units"], 21845)
        self.assertEqual(boundary["offset"], 21710)
        self.assertEqual(boundary["next_offset"], 21715)
        self.assertEqual(
            [r["source_evidence_cohort"] for r in boundary["units"]],
            ["baseline", "baseline", "v3", "v3", "v3"],
        )
        self.assertEqual(
            len({r["stable_review_id"] for r in boundary["units"]}), 5
        )
        # Pagination is over matching rows, including filters, not raw ordinals.
        filtered = query(
            ROOT, cohort="v3", evidence_type="title", offset=1, limit=2,
            include_evidence=True,
        )
        self.assertEqual(filtered["total_filtered_source_review_units"], 6)
        self.assertEqual(filtered["offset"], 1)
        self.assertEqual(filtered["next_offset"], 3)
        self.assertEqual(len(filtered["units"]), 2)
        self.assertTrue(all(
            row["original_title_evidence"]
            and not row["original_media_evidence"]
            for row in filtered["units"]
        ))
        last = query(ROOT, cohort="v3", offset=132, limit=5)
        self.assertEqual(last["returned_source_review_units"], 1)
        self.assertIsNone(last["next_offset"])
        past_end = query(ROOT, cohort="v3", offset=133, limit=5)
        self.assertEqual(past_end["returned_source_review_units"], 0)
        self.assertIsNone(past_end["next_offset"])

    def test_rejects_unsafe_offsets(self):
        for value in (-1, True, "10", 1_000_001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                query(ROOT, cohort="combined", offset=value)

    def test_rejects_unsafe_filters(self):
        for args in (
            {"review_id": "lgreview:v1:x"},
            {"priority_class": "canonical-game"},
            {"evidence_type": "guessed"},
            {"limit": 0},
            {"title": " "},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                query(ROOT, **args)


if __name__ == "__main__":
    unittest.main()
