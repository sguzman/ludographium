import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "wikidata-p400-platform-gaps-v1.json"


class WikidataScopeCoverageTest(unittest.TestCase):
    def test_pinned_collection_gap_report_is_deterministic(self):
        subprocess.run(
            [sys.executable, "tools/audit_wikidata_platform_gaps.py", "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["libretro_source_collections"], 75)
        self.assertEqual(report["registered_wikidata_p400_platform_scopes"], 53)
        self.assertEqual(report["unregistered_libretro_source_collections"], 22)
        self.assertEqual(report["distribution_partition_research"], 8)
        self.assertEqual(report["platform_or_accessory_research"], 14)
        self.assertEqual(len({row["platform"] for row in report["gaps"]}), 22)
        self.assertIn("no game records", report["policy"])


if __name__ == "__main__":
    unittest.main()
