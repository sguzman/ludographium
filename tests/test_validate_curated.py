import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from validate_curated import validate_ledger

WORK = "ldg:w:11111111-1111-4111-8111-111111111111"
RELEASE = "ldg:r:22222222-2222-4222-8222-222222222222"
BUILD = "ldg:b:33333333-3333-4333-8333-333333333333"
REF = {"source_id": "src", "source_revision": "rev", "source_path": "x.dat",
       "source_blob_sha": "abc", "source_ordinal": 1}
KEY = ("src", "rev", "x.dat", "abc", 1)


def fixture():
    return {
        "schema_version": 1, "kind": "curated-identity-ledger",
        "works": [{"id": WORK, "preferred_title": "Sample",
                   "rationale": "Identified from cited source evidence", "evidence": [dict(REF)]}],
        "releases": [{"id": RELEASE, "work_id": WORK, "platform": "gb",
                      "release_label": "Sample (USA)",
                      "rationale": "Publication on the named platform",
                      "evidence": [dict(REF)]}],
        "builds": [{"id": BUILD, "release_id": RELEASE,
                    "build_label": "Source ROM revision",
                    "rationale": "Specific source-observed media fingerprint",
                    "evidence": [dict(REF)]}],
    }


class CuratedTests(unittest.TestCase):
    def test_valid_hierarchy(self):
        self.assertEqual(validate_ledger(fixture(), {"gb"}, {KEY}),
                         {"works": 1, "releases": 1, "builds": 1})

    def test_no_title_based_keys(self):
        ledger = fixture()
        ledger["works"][0]["id"] = "ldg:w:sample"
        with self.assertRaisesRegex(ValueError, "stable identity"):
            validate_ledger(ledger, {"gb"}, {KEY})

    def test_unknown_evidence(self):
        ledger = fixture()
        ledger["works"][0]["evidence"][0]["source_ordinal"] = 2
        with self.assertRaisesRegex(ValueError, "unknown source occurrence"):
            validate_ledger(ledger, {"gb"}, {KEY})

    def test_wrong_platform_and_missing_parents(self):
        ledger = fixture()
        ledger["releases"][0]["platform"] = "invalid"
        with self.assertRaisesRegex(ValueError, "unknown platform"):
            validate_ledger(ledger, {"gb"}, {KEY})
        ledger = fixture()
        ledger["builds"][0]["release_id"] = WORK
        with self.assertRaisesRegex(ValueError, "unknown release"):
            validate_ledger(ledger, {"gb"}, {KEY})

    def test_bad_evidence_fails_closed(self):
        ledger = fixture()
        ledger["works"][0]["evidence"][0]["extra"] = "inferred"
        with self.assertRaisesRegex(ValueError, "exact source"):
            validate_ledger(ledger, {"gb"}, {KEY})

    def test_empty_ledger_does_not_fabricate_games(self):
        ledger = {"schema_version": 1, "kind": "curated-identity-ledger",
                  "works": [], "releases": [], "builds": []}
        self.assertEqual(validate_ledger(ledger, {"gb"}, set()),
                         {"works": 0, "releases": 0, "builds": 0})


if __name__ == "__main__":
    unittest.main()
