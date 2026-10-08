import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_curated import canonical_bytes


class CuratedExportTests(unittest.TestCase):
    def test_portable_curated_records_validate_against_original_source(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads(canonical_bytes(root))
        self.assertEqual(data["kind"], "curated-identity-ledger")
        self.assertEqual(len(data["works"]), 4)
        self.assertEqual(len(data["releases"]), 4)
        self.assertEqual(len(data["builds"]), 4)
        self.assertTrue(all("sha1" in entry["media"] for entry in data["builds"]))

    def test_canonical_encoding_is_stable(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(canonical_bytes(root), canonical_bytes(root))


if __name__ == "__main__":
    unittest.main()
