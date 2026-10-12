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

    def test_separate_v3_media_evidence_is_independently_searchable(self):
        supplement = candidate_query(
            ROOT, cohort="v3", libretro_platform="atari5200", limit=2
        )
        self.assertEqual(supplement["total_original_candidate_pairs"], 127)
        self.assertGreater(supplement["total_filtered_candidate_pairs"], 0)
        self.assertEqual(supplement["source_cohorts"], ["v3"])
        self.assertTrue(all(
            row["source_evidence_cohort"] == "v3"
            and row["kind"] ==
            "review-only-v3-mame-libretro-exact-media-sha1-candidate"
            and row["size_corroborated"]
            for row in supplement["pairs"]
        ))
        combined = candidate_query(ROOT, cohort="combined", limit=1)
        self.assertEqual(combined["total_original_candidate_pairs"], 19152)
        self.assertEqual(combined["independent_mame_source_lists"], 69)
        self.assertEqual(combined["source_cohorts"], ["baseline", "v3"])
        with self.assertRaises(ValueError):
            candidate_query(ROOT, cohort="not-a-verified-cohort")

    def test_source_only_acquisition_gaps_are_searchable_without_identity_inference(self):
        report = source_query(ROOT, without_review_leads=True, limit=2)
        self.assertEqual(report["total_filtered_original_records"], 11241)
        self.assertEqual(report["full_source_review_gap_inventory"], 11241)
        self.assertTrue(report["without_any_cross_provider_review_lead"])
        self.assertTrue(all(row["original_xml_sha256"] for row in report["records"]))
        psx = source_query(ROOT, source_list="psx", without_review_leads=True, limit=1)
        self.assertEqual(psx["total_filtered_original_records"], 2915)
        self.assertEqual(psx["returned_original_records"], 1)
        gamecom = source_query(
            ROOT, source_list="gamecom", without_review_leads=True, limit=1
        )
        self.assertEqual(gamecom["total_filtered_original_records"], 0)

    def test_third_original_mame_cohort_stays_separate_and_searchable(self):
        newer = source_query(ROOT, cohort="v3", source_list="casloopy", limit=2)
        self.assertEqual(newer["source_query_cohort"], "v3")
        self.assertEqual(newer["source_software_entries"], 166)
        self.assertEqual(newer["original_source_lists"], 4)
        self.assertGreater(newer["total_filtered_original_records"], 0)
        self.assertTrue(all(
            row["source_list"] == "casloopy" for row in newer["records"]
        ))
        combined = source_query(
            ROOT, cohort="all", source_list="a5200", limit=1
        )
        self.assertEqual(combined["original_source_lists"], 69)
        self.assertEqual(combined["source_software_entries"], 33119)
        self.assertEqual(len(combined["all_original_source_registers"]), 3)
        with self.assertRaises(ValueError):
            source_query(ROOT, cohort="v3", without_review_leads=True)
        with self.assertRaises(ValueError):
            source_query(ROOT, cohort="all", without_review_leads=True)

    def test_original_source_pagination_and_selected_cohort_label(self):
        combined = source_query(ROOT, cohort="all", offset=32951, limit=4)
        self.assertEqual(combined["source_query_cohort"], "all")
        self.assertEqual(combined["source_software_entries"], 33119)
        self.assertEqual(combined["total_filtered_original_records"], 33119)
        self.assertEqual(combined["offset"], 32951)
        self.assertEqual(combined["next_offset"], 32955)
        self.assertEqual(combined["returned_original_records"], 4)
        third_lists = {"a5200", "advision", "casloopy", "crvision"}
        self.assertEqual(
            [row["source_list"] in third_lists for row in combined["records"]],
            [False, False, True, True],
        )
        tail = source_query(
            ROOT, cohort="v3", source_list="casloopy", offset=10, limit=3
        )
        self.assertEqual(tail["source_query_cohort"], "v3")
        self.assertEqual(tail["total_filtered_original_records"], 11)
        self.assertEqual(tail["returned_original_records"], 1)
        self.assertIsNone(tail["next_offset"])
        for offset in (-1, True, "1", 1_000_001):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                source_query(ROOT, offset=offset)

    def test_fourth_cohort_source_records_and_full_77_list_paging(self):
        fourth = source_query(ROOT, cohort="v4", limit=2)
        self.assertEqual(fourth["original_source_lists"], 8)
        self.assertEqual(fourth["source_software_entries"], 373)
        self.assertEqual(fourth["total_filtered_original_records"], 373)
        self.assertEqual(fourth["all_original_source_registers"], [
            "sources/mame-softlists-v4.json"
        ])
        self.assertEqual(fourth["records"][0]["source_list"], "3do")
        supervision = source_query(
            ROOT, cohort="v4", source_list="svision", limit=2
        )
        self.assertEqual(supervision["total_filtered_original_records"], 72)
        self.assertTrue(all(
            record["source_list"] == "svision" and record["original_xml_sha256"]
            for record in supervision["records"]
        ))
        full = source_query(ROOT, cohort="all-pinned", offset=33117, limit=4)
        self.assertEqual(full["source_query_cohort"], "all-pinned")
        self.assertEqual(full["original_source_lists"], 77)
        self.assertEqual(full["source_software_entries"], 33492)
        self.assertEqual(full["total_filtered_original_records"], 33492)
        self.assertEqual(full["next_offset"], 33121)
        self.assertEqual(len(full["all_original_source_registers"]), 4)
        self.assertEqual(
            [record["source_list"] == "3do" for record in full["records"]],
            [False, False, True, True],
        )
        # Historical 69-list cohort retains the same count and order.
        old = source_query(ROOT, cohort="all", offset=33117, limit=4)
        self.assertEqual(old["source_software_entries"], 33119)
        self.assertEqual(old["returned_original_records"], 2)
        self.assertIsNone(old["next_offset"])
        with self.assertRaises(ValueError):
            source_query(ROOT, cohort="v4", without_review_leads=True)

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
