"""Unit validation for strict, source-only SHA-1 correspondence helpers."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reconcile_mame_media import mame_size, valid_sha1


class MameMediaFingerprintTests(unittest.TestCase):
    def test_media_size_parses_hex_and_decimal_without_guessing(self):
        self.assertEqual(mame_size("0x200000"), 2097152)
        self.assertEqual(mame_size("65536"), 65536)
        self.assertIsNone(mame_size(None))
        with self.assertRaises(ValueError):
            mame_size("0xZZ")

    def test_sha1_requires_exact_hex_fingerprint(self):
        self.assertEqual(valid_sha1("A" * 40), "a" * 40)
        self.assertIsNone(valid_sha1(None))
        self.assertIsNone(valid_sha1(""))
        with self.assertRaises(ValueError):
            valid_sha1("G" * 40)
        with self.assertRaises(ValueError):
            valid_sha1("1234")


if __name__ == "__main__":
    unittest.main()
