import hashlib
import json
import sys
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package_runtime import build_archive, runtime_files


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "generated/v1").mkdir(parents=True)
        (self.root / "generated/enrichment-v1").mkdir(parents=True)
        self.path = "generated/v1/catalog.json"
        data = b'{"catalog":"example"}\n'
        (self.root / self.path).write_bytes(data)
        self.manifest = {
            "schema_version": 1, "kind": "ludographium-distribution",
            "artifacts": [{
                "path": self.path, "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }],
        }
        self.write_manifest()

    def write_manifest(self):
        (self.root / "generated/v1/distribution.json").write_text(json.dumps(self.manifest))

    def test_deterministic_bundle_and_no_archive_sources(self):
        first = build_archive(self.root)
        self.assertEqual(first, build_archive(self.root))
        with tarfile.open(fileobj=BytesIO(first), mode="r:gz") as tar:
            self.assertEqual(sorted(tar.getnames()), [
                "generated/v1/catalog.json", "generated/v1/distribution.json"
            ])
            for entry in tar.getmembers():
                self.assertEqual(entry.mtime, 0)
                self.assertEqual(entry.uid, 0)
                self.assertEqual(entry.mode, 0o644)
            self.assertEqual(tar.extractfile("generated/v1/catalog.json").read(),
                             b'{"catalog":"example"}\n')

    def test_attribution_files_travel_with_runtime_index(self):
        payloads = {
            "sources/libretro-no-intro.json": b'{"source_id":"pinned"}\n',
            "sources/libretro-enrichment.json": b'{"source_id":"fields"}\n',
            "METADATA-NOTICE.md": b"# Source attribution\n",
        }
        for name, data in payloads.items():
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            self.manifest["artifacts"].append({
                "path": name, "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
        self.write_manifest()
        with tarfile.open(fileobj=BytesIO(build_archive(self.root)), mode="r:gz") as tar:
            names = set(tar.getnames())
            self.assertEqual(names, set(payloads) | {
                "generated/v1/catalog.json", "generated/v1/distribution.json"
            })
            self.assertEqual(tar.extractfile("METADATA-NOTICE.md").read(),
                             payloads["METADATA-NOTICE.md"])
        (self.root / "sources/libretro-no-intro.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
            build_archive(self.root)

    def test_rejects_corrupted_artifact(self):
        (self.root / self.path).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
            build_archive(self.root)

    def test_rejects_unsafe_manifest_paths(self):
        self.manifest["artifacts"][0]["path"] = "generated/v1/../../secret.json"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "incomplete runtime distribution"):
            build_archive(self.root)

    def test_rejects_non_json_or_duplicate_paths(self):
        item = dict(self.manifest["artifacts"][0])
        self.manifest["artifacts"].append(item)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            runtime_files(self.root)


if __name__ == "__main__":
    unittest.main()
