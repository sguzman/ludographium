"""Conservative fourth-cohort SHA1 reconciliation: no size guessing."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reconcile_mame_v4_media import size_status


class FourthCohortMediaGuards(unittest.TestCase):
    def test_only_equal_declared_byte_sizes_are_corroborated(self):
        self.assertEqual(size_status(32768, 32768), "corroborated")
        self.assertEqual(size_status(32768, 65536), "size-conflict")
        self.assertEqual(size_status(None, 32768), "uncorroborated-size")
        # Optical-disc SHA1 entries lack a MAME byte-size declaration.
        self.assertEqual(size_status(None, 0), "uncorroborated-size")

    def test_reject_malformed_declared_media_size(self):
        for mame, dat in ((-1, 1), (1, -1), ("1024", 1024),
                          (1024, "1024"), (True, 1), (1024, None)):
            with self.subTest(mame=mame, dat=dat):
                with self.assertRaises(ValueError):
                    size_status(mame, dat)


if __name__ == "__main__":
    unittest.main()
