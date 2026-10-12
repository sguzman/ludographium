"""Fourth-cohort registration stays source-scoped and independently licensed."""
import sys
import tempfile
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from acquire_mame_softlists import source_register


class FourthCohortRegisterTests(unittest.TestCase):
    def test_eight_exact_pinned_xml_source_names(self):
        current = source_register(ROOT, "v4")
        self.assertEqual(current["accession_cohort"], "v4")
        self.assertEqual(current["license"], "CC0-1.0")
        self.assertEqual(current["upstream_repository"], "mamedev/mame")
        self.assertEqual(current["upstream_commit_sha"], "58f90f43e7d1e2ae7078ba8a3c6d9f9cf879cb7a")
        self.assertEqual(current["prior_source_register"], "sources/mame-softlists-v3.json")
        self.assertEqual(current["files"], [
            "3do.xml", "cd32.xml", "gameking.xml", "gameking3.xml",
            "gamepock.xml", "megaduck.xml", "pcfx.xml", "svision.xml",
        ])

    def test_reject_unregistered_cohort(self):
        with self.assertRaises(ValueError):
            source_register(ROOT, "v5")

    def test_reject_duplicate_or_path_traversal_source(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory)
            (fake / "sources").mkdir()
            original = source_register(ROOT, "v4")
            for bad in (["3do.xml"] * 8, ["../outside.xml", *original["files"][1:]]):
                registered = {**original, "files": bad}
                (fake / "sources/mame-softlists-v4.json").write_text(
                    json.dumps(registered), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    source_register(fake, "v4")


if __name__ == "__main__":
    unittest.main()
