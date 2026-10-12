"""Fifth MAME accession must be disjoint from all earlier original source lists."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from acquire_mame_softlists import source_register


class FifthMameSourceRegisterTests(unittest.TestCase):
    def test_six_immutable_cc0_source_partitions_are_new(self):
        fifth = source_register(ROOT, "v5")
        self.assertEqual(fifth["files"], [
            "3do_m2.xml", "cdi.xml", "cdtv.xml",
            "gamate.xml", "megacd.xml", "neogeo.xml",
        ])
        self.assertEqual(fifth["license"], "CC0-1.0")
        self.assertEqual(fifth["upstream_repository"], "mamedev/mame")
        self.assertEqual(fifth["prior_source_register"], "sources/mame-softlists-v4.json")
        previous = {
            file for cohort in ("v1", "v2", "v3", "v4")
            for file in source_register(ROOT, cohort)["files"]
        }
        self.assertTrue(previous.isdisjoint(fifth["files"]))
        self.assertEqual(len(previous), 77)

    def test_unregistered_filename_and_duplicate_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "sources").mkdir()
            original = source_register(ROOT, "v5")
            for files in (
                ["../../outside.xml", *original["files"][1:]],
                [original["files"][0]] * 6,
            ):
                bad = {**original, "files": files}
                (tmp / "sources/mame-softlists-v5.json").write_text(
                    json.dumps(bad), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    source_register(tmp, "v5")


if __name__ == "__main__":
    unittest.main()
