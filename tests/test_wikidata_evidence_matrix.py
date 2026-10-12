"""Regression coverage for the bulk, provenance-preserving evidence matrix."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "audit_wikidata_evidence_matrix.py"
spec = importlib.util.spec_from_file_location("audit_wikidata_evidence_matrix", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WikidataEvidenceMatrixTests(unittest.TestCase):
    def test_all_original_source_families_and_unregistered_scopes(self):
        report = module.build_report(ROOT)
        self.assertEqual(report["registered_source_platform_scopes"], 65)
        self.assertEqual(report["libretro_source_collections"], 75)
        self.assertEqual(report["unregistered_libretro_source_collections"], 10)
        self.assertEqual(
            report["source_family_observation_totals"]["localized"], 154198
        )
        self.assertEqual(
            report["source_family_observation_totals"]["credits"], 58460
        )
        self.assertEqual(
            report["source_family_observation_totals"]["relations"], 113204
        )
        self.assertEqual(len(report["registered_scopes"]), 65)
        self.assertEqual(len({
            item["platform"] for item in report["registered_scopes"]
        }), 65)
        self.assertTrue(all(
            len(row["source_rows"]) == 4 and len(row["source_manifests"]) == 4
            for row in report["registered_scopes"]
        ))
        self.assertIn("not evidence", report["interpretation"])

    def test_v8_is_explicitly_provisional(self):
        report = module.build_report(ROOT)
        additions = [
            scope for scope in report["registered_scopes"]
            if scope["register_cohort"] == "v8"
        ]
        self.assertEqual(len(additions), 12)
        self.assertTrue(all(
            scope["scope_status"] == "provisional-provider-query-target"
            for scope in additions
        ))
        self.assertTrue(any(scope["all_four_families_empty"] for scope in additions))


if __name__ == "__main__":
    unittest.main()
