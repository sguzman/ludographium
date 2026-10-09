import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_release import prepare_release, validate_tag


class ReleasePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "dist"
        (self.root / "generated/v1").mkdir(parents=True)
        self.catalog = {
            "schema_version": 1, "kind": "source-catalog",
            "source_id": "test-source", "source_revision": "fixed-commit",
            "platforms": [{"platform": "gb", "artifact_path": "generated/v1/gb.json"}],
        }
        (self.root / "generated/v1/catalog.json").write_text(json.dumps(self.catalog))
        (self.root / "generated/v1/gb.json").write_text('{"game":"fixture"}\n')
        from build_distribution import canonical_bytes
        (self.root / "generated/v1/distribution.json").write_bytes(canonical_bytes(self.root))

    def test_validate_tag(self):
        for tag in ("data-v1.0.0", "data-v1.23.405"):
            validate_tag(tag)
        for tag in ("v1.0.0", "data-v1", "data-v01.0.0", "data-v1.0.0-rc1",
                    "data-v1.0.0\n", "data-v1.0.0/../oops", "data-v1.0.0.0"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                validate_tag(tag)

    def test_deterministic_release_and_checksum(self):
        first, checksum, notes = prepare_release(self.root, "data-v1.0.0", self.out)
        data = first.read_bytes()
        self.assertTrue(data.startswith(b"\x1f\x8b"))
        self.assertEqual(checksum.read_text(),
                         f"{hashlib.sha256(data).hexdigest()}  {first.name}\n")
        self.assertIn("fixed-commit", notes.read_text())
        self.assertIn("METADATA-NOTICE.md", notes.read_text())
        second, _, _ = prepare_release(self.root, "data-v1.0.0", self.out)
        self.assertEqual(second.read_bytes(), data)

    def test_real_pinned_ledger_counts_appear_in_release_notes(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as output:
            archive, checksums, notes = prepare_release(
                project_root, "data-v1.1.0", Path(output)
            )
            content = notes.read_text(encoding="utf-8")
            self.assertIn("8 works, 10 releases, 12 exact media builds\\n", content)
            self.assertTrue(archive.exists())
            self.assertTrue(checksums.exists())

    def test_refuses_stale_manifest_and_tampering(self):
        path = self.root / "generated/v1/gb.json"
        path.write_text('{"game":"different"}\n')
        with self.assertRaisesRegex(ValueError, "out of date"):
            prepare_release(self.root, "data-v1.0.0", self.out)
        self.assertFalse(self.out.exists())

    def test_refuses_malformed_tag_before_output(self):
        with self.assertRaisesRegex(ValueError, "tag"):
            prepare_release(self.root, "data-v1.0.0/../../unsafe", self.out)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
