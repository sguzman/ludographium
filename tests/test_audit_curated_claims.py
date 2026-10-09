"""Curated enrichment audits must not infer game identities from CRC alone."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_curated_claims import audit_platform

REF = {
    "source_id": "base", "source_revision": "revision",
    "source_path": "base.dat", "source_blob_sha": "base-blob",
    "source_ordinal": 1,
}
MEDIA = {"sha1": "A" * 40, "size": 1024}
CRC = "ABCD1234"


def fixture():
    base = {
        "source_id": "base", "source_revision": "revision",
        "source_path": "base.dat", "source_blob_sha": "base-blob",
        "platform": "gb",
        "records": [
            {"source_ordinal": 1, "name": "Game (World)",
             "roms": [{**MEDIA, "crc32": CRC}]},
            {"source_ordinal": 2, "name": "Other (World)",
             "roms": [{"sha1": "B" * 40, "size": 1024, "crc32": CRC}]},
        ],
    }
    enriched = {
        "source_id": "field-provider", "source_revision": "field-revision",
        "base_source_id": "base", "base_source_revision": "revision",
        "platform": "gb",
        "claims": [{
            "field": "publisher", "value": "Example Corp", "crc32": CRC,
            "source_comment": "Game (World)",
            "source_path": "publisher.dat", "source_blob_sha": "claim-blob",
            "source_ordinal": 5,
            "resolution": {"status": "matched", "base_source_ordinal": 1},
        }, {
            "field": "genre", "value": "Puzzle", "crc32": CRC,
            "source_comment": "Other (World)",
            "source_path": "genre.dat", "source_blob_sha": "other-blob",
            "source_ordinal": 7,
            "resolution": {"status": "comment_mismatch", "base_source_ordinal": None},
        }],
    }
    builds = [{
        "id": "build-1", "release_id": "release-1", "media": dict(MEDIA),
        "evidence": [dict(REF)],
    }]
    return base, enriched, builds


class CuratedClaimAuditTests(unittest.TestCase):
    def test_matches_by_exact_record_and_crc_with_fully_attributed_claim(self):
        base, enriched, builds = fixture()
        result = audit_platform(base, enriched, builds)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_fields"], ["publisher"])
        self.assertEqual(result[0]["matched_claim_count"], 1)
        claim = result[0]["source_claims"][0]
        self.assertEqual(claim["value"], "Example Corp")
        self.assertEqual(claim["base_source_ordinal"], 1)
        self.assertEqual(claim["source"]["source_id"], "field-provider")
        self.assertEqual(claim["source"]["source_path"], "publisher.dat")
        self.assertEqual(claim["source"]["source_ordinal"], 5)
        self.assertEqual(result[0]["sha1"], "A" * 40)

    def test_unresolved_claim_does_not_become_attached_by_crc(self):
        base, enriched, builds = fixture()
        enriched["claims"][0]["resolution"] = {
            "status": "ambiguous_crc", "base_source_ordinal": None
        }
        rows = audit_platform(base, enriched, builds)
        self.assertEqual(rows[0]["matched_claim_count"], 0)

    def test_rejects_claim_source_comment_drift(self):
        base, enriched, builds = fixture()
        enriched["claims"][0]["source_comment"] = "Other (World)"
        with self.assertRaisesRegex(ValueError, "source title"):
            audit_platform(base, enriched, builds)

    def test_rejects_wrong_media_even_when_crc_matches(self):
        base, enriched, builds = fixture()
        builds[0]["media"]["sha1"] = "B" * 40
        with self.assertRaisesRegex(ValueError, "build media absent"):
            audit_platform(base, enriched, builds)

    def test_rejects_wrong_revision_or_base_source_evidence(self):
        base, enriched, builds = fixture()
        enriched["base_source_revision"] = "wrong"
        with self.assertRaisesRegex(ValueError, "source identities"):
            audit_platform(base, enriched, builds)
        base, enriched, builds = fixture()
        builds[0]["evidence"][0]["source_blob_sha"] = "another"
        with self.assertRaisesRegex(ValueError, "source locator mismatch"):
            audit_platform(base, enriched, builds)

    def test_rejects_stale_resolved_crc(self):
        base, enriched, builds = fixture()
        enriched["claims"][0]["crc32"] = "00000000"
        with self.assertRaisesRegex(ValueError, "claim CRC32"):
            audit_platform(base, enriched, builds)

    def test_source_input_is_unchanged(self):
        base, enriched, builds = fixture()
        before = copy.deepcopy((base, enriched, builds))
        audit_platform(base, enriched, builds)
        self.assertEqual((base, enriched, builds), before)


if __name__ == "__main__":
    unittest.main()
