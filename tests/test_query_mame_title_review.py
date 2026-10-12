"""Offline title-review search guards and provenance assertions."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_mame_title_review import INDEX, SUMMARY, query


class ConservativeTitleQueryTests(unittest.TestCase):
    def test_full_verified_title_review_inventory(self):
        result = query(ROOT, limit=2)
        self.assertEqual(result["original_source_candidate_pairs"], 6825)
        self.assertEqual(result["distinct_original_mame_records_with_candidates"], 2699)
        self.assertEqual(result["returned_candidate_pairs"], 2)
        self.assertTrue(all(
            row["interpretation"].startswith("review-only-")
            and row["source_scope_pair_sha1_supported_mame_records"] >= 3
            for row in result["pairs"]
        ))
        self.assertIn("not a verified game", result["interpretation"])

    def test_scope_evidence_is_independently_checked_after_rehashing(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / INDEX.parent).mkdir(parents=True)
            (base / SUMMARY.parent).mkdir(parents=True, exist_ok=True)
            lines = (ROOT / INDEX).read_bytes().splitlines()
            first = json.loads(lines[0])
            first["source_scope_pair_sha1_supported_mame_records"] += 1
            lines[0] = json.dumps(
                first, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")
            ).encode("utf-8")
            altered = b"\n".join(lines) + b"\n"
            (base / INDEX).write_bytes(altered)
            report = json.loads((ROOT / SUMMARY).read_text(encoding="utf-8"))
            report["candidate_sha256"] = hashlib.sha256(altered).hexdigest()
            report["candidate_bytes"] = len(altered)
            (base / SUMMARY).write_text(
                json.dumps(report), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                query(base, limit=1)

    def test_additive_title_review_remains_separate_from_original_65_lists(self):
        third = query(ROOT, cohort="v3", limit=3)
        self.assertEqual(third["original_source_candidate_pairs"], 8)
        self.assertEqual(third["distinct_original_mame_records_with_candidates"], 6)
        self.assertTrue(all(
            item["mame"]["source_cohort"] == "v3"
            and item["source_evidence_cohort"] == "v3"
            for item in third["pairs"]
        ))
        combined = query(ROOT, cohort="combined", limit=1)
        self.assertEqual(combined["source_cohorts"], ["baseline", "v3"])
        self.assertEqual(combined["original_source_candidate_pairs"], 6833)
        self.assertEqual(combined["distinct_original_mame_records_with_candidates"], 2705)
        with self.assertRaises(ValueError):
            query(ROOT, cohort="unknown")

    def test_bounded_pages_cross_original_and_additive_title_leads(self):
        combined = query(ROOT, cohort="combined", offset=6823, limit=4)
        self.assertEqual(combined["original_source_candidate_pairs"], 6833)
        self.assertEqual(combined["total_filtered_candidate_pairs"], 6833)
        self.assertEqual(combined["returned_candidate_pairs"], 4)
        self.assertEqual(combined["next_offset"], 6827)
        self.assertEqual(
            [r["source_evidence_cohort"] for r in combined["pairs"]],
            ["baseline", "baseline", "v3", "v3"],
        )
        last = query(ROOT, cohort="v3", offset=7, limit=3)
        self.assertEqual(last["returned_candidate_pairs"], 1)
        self.assertIsNone(last["next_offset"])
        empty = query(ROOT, cohort="v3", offset=8, limit=3)
        self.assertEqual(empty["returned_candidate_pairs"], 0)
        self.assertIsNone(empty["next_offset"])
        for offset in (-1, True, "1", 1_000_001):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                query(ROOT / "nonexistent", offset=offset)

    def test_ambiguity_and_filters_keep_all_provenance(self):
        result = query(ROOT, ambiguous_only=True, limit=4)
        self.assertGreater(result["total_filtered_candidate_pairs"], 0)
        self.assertTrue(all(
            row["is_ambiguous_among_source_review_candidates"]
            and row["source_review_alternatives_for_same_mame_record"] > 1
            for row in result["pairs"]
        ))
        with self.assertRaises(ValueError):
            query(ROOT, min_scope_support=2)
        with self.assertRaises(ValueError):
            query(ROOT, title=" ")


if __name__ == "__main__":
    unittest.main()
