"""Bibliographic coverage is evidence availability, not automatic identity."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prioritize_identity_review import compare_platform, curation_status

SHA1 = "A" * 40
SHA2 = "B" * 40


def ref(n):
    return {
        "source_id": "base", "source_revision": "pinned",
        "source_path": "base.dat", "source_blob_sha": "blob", "source_ordinal": n,
    }


def fixture():
    base = {
        "platform": "gb", "source_id": "base", "source_revision": "pinned",
        "records": [
            {"source_ordinal": 1, "name": "Game (World)",
             "roms": [{"sha1": SHA1, "size": 1024, "crc32": "11223344"}]},
            {"source_ordinal": 2, "name": "Game (World) (Rev A)",
             "roms": [{"sha1": SHA2, "size": 1024, "crc32": "55667788"}]},
        ],
    }
    enriched = {
        "platform": "gb", "base_source_id": "base", "base_source_revision": "pinned",
        "source_id": "field-series", "source_revision": "field-revision",
        "claims": [{
            "field": "publisher", "value": "Acme",
            "source_comment": title, "crc32": crc,
            "source_ordinal": i, "source_path": "publisher.dat",
            "source_blob_sha": "publisher-blob",
            "resolution": {"status": "matched", "base_source_ordinal": i},
        } for i, title, crc in [
            (1, "Game (World)", "11223344"),
            (2, "Game (World) (Rev A)", "55667788"),
        ]],
    }
    group = {
        "platform": "gb", "edition_label": "Game (World)",
        "members": [
            {"source_title": "Game (World)", "revision": None,
             "sha1": SHA1, "size": 1024, "evidence": ref(1)},
            {"source_title": "Game (World) (Rev A)", "revision": "A",
             "sha1": SHA2, "size": 1024, "evidence": ref(2)},
        ],
    }
    ledger = {"works": [], "releases": []}
    return base, enriched, group, ledger


class BibliographicPrioritizationTests(unittest.TestCase):
    def test_field_coverage_never_confers_curated_identity(self):
        base, enriched, group, ledger = fixture()
        result = compare_platform(base, enriched, [group], ledger)[0]
        self.assertEqual(result["curation_status"], "uncurated")
        self.assertEqual(result["evidence_status"], "review-only")
        self.assertEqual(result["shared_field_names"], ["publisher"])
        self.assertEqual(result["fields_with_different_source_values"], [])
        self.assertEqual(result["member_count"], 2)
        self.assertEqual(result["members"][0]["bibliographic_claims"][0]["source"]["source_path"], "publisher.dat")

    def test_reports_value_variation_without_merging(self):
        base, enriched, group, ledger = fixture()
        enriched["claims"][1]["value"] = "Other Co"
        result = compare_platform(base, enriched, [group], ledger)[0]
        self.assertEqual(result["fields_with_different_source_values"], ["publisher"])
        self.assertEqual(result["evidence_status"], "review-only")

    def test_crc_only_does_not_attach_unmatched_claim(self):
        base, enriched, group, ledger = fixture()
        enriched["claims"][1]["resolution"] = {
            "status": "ambiguous_crc", "base_source_ordinal": None
        }
        result = compare_platform(base, enriched, [group], ledger)[0]
        self.assertEqual(result["shared_field_names"], [])
        self.assertEqual(result["members"][1]["field_claim_count"], 0)

    def test_curation_status_is_cited_occurrence_based(self):
        _, _, group, ledger = fixture()
        self.assertEqual(curation_status(group, ledger), "uncurated")
        ledger["releases"] = [{"id": "r", "evidence": [ref(1)]}]
        self.assertEqual(curation_status(group, ledger), "partially-curated")
        ledger["releases"][0]["evidence"].append(ref(2))
        self.assertEqual(curation_status(group, ledger), "already-curated")
        ledger["releases"] = [
            {"id": "r1", "evidence": [ref(1)]},
            {"id": "r2", "evidence": [ref(2)]},
        ]
        self.assertEqual(curation_status(group, ledger), "conflicting-curation")

    def test_rejects_wrong_claim_resolution_or_candidate_record(self):
        base, enriched, group, ledger = fixture()
        enriched["claims"][0]["source_comment"] = "Wrong title"
        with self.assertRaisesRegex(ValueError, "source title"):
            compare_platform(base, enriched, [group], ledger)
        base, enriched, group, ledger = fixture()
        group["members"][0]["source_title"] = "Wrong title"
        with self.assertRaisesRegex(ValueError, "stale"):
            compare_platform(base, enriched, [group], ledger)

    def test_does_not_mutate_original_evidence(self):
        base, enriched, group, ledger = fixture()
        original = copy.deepcopy((base, enriched, group, ledger))
        compare_platform(base, enriched, [group], ledger)
        self.assertEqual((base, enriched, group, ledger), original)


if __name__ == "__main__":
    unittest.main()
