"""Validate the entire provisional v8 cohort against pinned Wikidata discovery."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "sources/wikidata-platform-expansion-v8.json"
DISCOVERY = ROOT / "data/wikidata/platform-discovery-v1"
DATA = ROOT / "data/wikidata/platform-expansion-v8"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ProvisionalV8SourceTest(unittest.TestCase):
    def test_all_scope_qids_are_present_in_independent_discovery_responses(self):
        register = read(REGISTER)
        self.assertEqual(len(register["platforms"]), 12)
        seen = set()
        for target in register["platforms"]:
            platform = target["platform"]
            qid = target["wikidata_platform"]
            self.assertNotIn(platform, seen)
            seen.add(platform)
            result = read(DISCOVERY / platform / "response.json")
            self.assertIn(qid, {candidate["id"] for candidate in result["search"]})
            self.assertEqual(
                target["review_status"],
                "provisional-p400-query-target-not-externally-verified-platform-identity",
            )

    def test_all_raw_p400_responses_are_pinned_and_noncoverage_is_preserved(self):
        register = read(REGISTER)
        totals = {"rows": 0, "items": 0, "english": 0, "dates": 0}
        empty = 0
        for target in register["platforms"]:
            platform = target["platform"]
            folder = DATA / platform
            manifest = read(folder / "manifest.json")
            self.assertEqual(manifest["platform"], platform)
            self.assertEqual(manifest["wikidata_platform"], target["wikidata_platform"])
            for key, filename in [
                ("query", "query.rq"),
                ("response", "response.json"),
                ("bindings", "bindings.jsonl"),
            ]:
                content = (folder / filename).read_bytes()
                self.assertEqual(manifest[f"source_{key}_bytes"], len(content))
                self.assertEqual(
                    manifest[f"source_{key}_sha256"],
                    hashlib.sha256(content).hexdigest(),
                )
            totals["rows"] += manifest["source_rows"]
            totals["items"] += manifest["distinct_item_qids"]
            totals["english"] += manifest["rows_with_english_label"]
            totals["dates"] += manifest["rows_with_publication_date"]
            if manifest["source_rows"] == 0:
                empty += 1
                self.assertEqual(manifest["distinct_item_qids"], 0)
                self.assertEqual((folder / "bindings.jsonl").read_bytes(), b"")
        self.assertEqual(totals, {"rows": 53, "items": 27, "english": 49, "dates": 50})
        self.assertEqual(empty, 6)


if __name__ == "__main__":
    unittest.main()
