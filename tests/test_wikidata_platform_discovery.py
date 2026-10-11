import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WikidataPlatformDiscoveryTest(unittest.TestCase):
    def test_candidate_search_queue_covers_unregistered_platform_leads(self):
        config = json.loads(
            (ROOT / "sources/wikidata-platform-discovery-v1.json").read_text()
        )
        gaps = json.loads(
            (ROOT / "reports/wikidata-p400-platform-gaps-v1.json").read_text()
        )
        target_ids = {item["platform"] for item in config["targets"]}
        gap_ids = {
            item["platform"] for item in gaps["gaps"]
            if item["review_class"] == "unregistered-platform-or-accessory"
        }
        self.assertEqual(target_ids, gap_ids)
        self.assertEqual(len(target_ids), 14)
        self.assertTrue(all("wikidata_platform" not in item for item in config["targets"]))
        subprocess.run(
            [sys.executable, "tools/discover_wikidata_platforms.py", "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
