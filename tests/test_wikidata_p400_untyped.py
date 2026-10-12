"""Regression tests for independently pinned direct-P400 discovery probes."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/audit_wikidata_p400_untyped.py"
spec = importlib.util.spec_from_file_location("audit_wikidata_p400_untyped", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class UntypedWikidataProbeTest(unittest.TestCase):
    def test_original_ten_partitions_and_non_game_result_count(self):
        report = module.build_report(ROOT)
        self.assertEqual(report["probed_platform_scopes"], 10)
        self.assertEqual(report["total_original_p400_bindings"], 3)
        self.assertEqual(report["total_distinct_item_scope_observations"], 2)
        self.assertEqual(report["total_original_instance_type_bindings"], 3)
        self.assertEqual(len(report["zero_result_scopes"]), 8)
        self.assertEqual(
            report["nonempty_scopes"], ["gameparkgp32", "tigergamecom"]
        )
        self.assertEqual(
            len({entry["platform"] for entry in report["per_platform"]}), 10
        )
        self.assertIn("not verified", report["interpretation"])


if __name__ == "__main__":
    unittest.main()
