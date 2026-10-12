"""Offline original-MAME and exact SHA-1 cross-source search smoke tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from query_mame_sources import query as source_query
from query_mame_media import query as candidate_query


class MameQueryTests(unittest.TestCase):
    def test_gamecom_source_records_remain_original_observations(self):
        result = source_query(ROOT, source_list="gamecom", title="Batman", limit=2)
        self.assertGreater(result["total_filtered_original_records"], 0)
        self.assertTrue(all(
            row["source_list"] == "gamecom"
            and row["original_xml_sha256"]
            and row["interpretation"].startswith("original-mame")
            for row in result["records"]
        ))
        with self.assertRaises(ValueError):
            source_query(ROOT, source_list="not-a-real-platform")

    def test_new_software_source_cohort_is_searchable_without_identity_joins(self):
        newer = source_query(ROOT, source_list="wswan", limit=2)
        self.assertGreater(newer["total_filtered_original_records"], 0)
        self.assertEqual(newer["source_software_entries"], 32953)
        self.assertEqual(newer["original_source_lists"], 65)
        self.assertEqual(
            newer["additional_source_register"], "sources/mame-softlists-v2.json"
        )
        self.assertTrue(all(
            item["source_list"] == "wswan" for item in newer["records"]
        ))

    def test_exact_sha1_candidates_keep_original_source_provenance(self):
        result = candidate_query(ROOT, libretro_platform="tigergamecom", limit=2)
        self.assertGreater(result["total_filtered_candidate_pairs"], 0)
        self.assertGreater(result["total_original_candidate_pairs"], 17734)
        self.assertTrue(all(
            row["libretro"]["platform"] == "tigergamecom"
            and row["size_corroborated"]
            and row["interpretation"].startswith("review-only")
            for row in result["pairs"]
        ))
        with self.assertRaises(ValueError):
            candidate_query(ROOT, sha1="not-sha1")


if __name__ == "__main__":
    unittest.main()
