import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_distribution import build_distribution, canonical_bytes


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "generated/v1").mkdir(parents=True)
        (self.root / "generated/v1/gb.json").write_bytes(b'{"sample":"game"}\n')
        self.catalog = {
            "schema_version": 1,
            "kind": "source-catalog",
            "source_id": "test-source",
            "source_revision": "commit",
            "platforms": [{"platform": "gb", "artifact_path": "generated/v1/gb.json"}],
        }
        self.write_catalog()

    def write_catalog(self):
        (self.root / "generated/v1/catalog.json").write_text(json.dumps(self.catalog))

    def test_digest_and_sorted_entries(self):
        result = build_distribution(self.root)
        self.assertEqual([x["path"] for x in result["artifacts"]],
                         ["generated/v1/catalog.json", "generated/v1/gb.json"])
        self.assertEqual(result["artifacts"][1]["sha256"],
                         hashlib.sha256(b'{"sample":"game"}\n').hexdigest())
        self.assertEqual(result["artifacts"][1]["bytes"], len(b'{"sample":"game"}\n'))

    def test_register_requires_attribution_notice(self):
        (self.root / "sources").mkdir()
        (self.root / "sources/libretro-no-intro.json").write_text('{"source_id":"upstream"}')
        with self.assertRaisesRegex(ValueError, "METADATA-NOTICE"):
            build_distribution(self.root)
        (self.root / "METADATA-NOTICE.md").write_text("# Metadata attribution")
        manifest = build_distribution(self.root)
        paths = {entry["path"] for entry in manifest["artifacts"]}
        self.assertIn("METADATA-NOTICE.md", paths)
        self.assertIn("sources/libretro-no-intro.json", paths)

    def test_modification_changes_output(self):
        original = canonical_bytes(self.root)
        (self.root / "generated/v1/gb.json").write_bytes(b"changed")
        self.assertNotEqual(original, canonical_bytes(self.root))

    def test_rejects_unsafe_path(self):
        self.catalog["platforms"][0]["artifact_path"] = "../secret"
        self.write_catalog()
        with self.assertRaises(ValueError):
            build_distribution(self.root)


if __name__ == "__main__":
    unittest.main()
