"""Verify source grouping rules without asserting platform/game identities."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_libretro_cross_scope_sha1 import normalized_group


def claim(platform, ordinal, size):
    return {
        "platform": platform,
        "source_record_ordinal": ordinal,
        "source_media_ordinal": 1,
        "source_title": "Source Name",
        "media_name": "original.rom",
        "media_size_bytes": size,
        "source_dat_path": f"archive/{platform}.dat",
        "source_dat_blob_sha": "b" * 40,
    }


class CrossScopeMediaTest(unittest.TestCase):
    def test_cross_scope_source_sha1_and_size_are_not_game_identity(self):
        result = normalized_group("a" * 40, [
            claim("nes", 1, 1024),
            claim("famicom", 2, 1024),
            claim("nes", 3, 2048),
        ])
        self.assertEqual(result["distinct_source_scope_count"], 2)
        self.assertEqual(result["original_source_media_claim_count"], 3)
        self.assertTrue(result["declared_size_disagreement"])
        self.assertEqual(result["distinct_declared_media_sizes_bytes"], [1024, 2048])
        self.assertIn("no-canonical", result["interpretation"])

    def test_single_platform_or_duplicate_ordinals_are_not_accepted(self):
        with self.assertRaises(ValueError):
            normalized_group("a" * 40, [claim("nes", 1, 10)])
        with self.assertRaises(ValueError):
            normalized_group("a" * 40, [
                claim("nes", 1, 10), claim("nes", 1, 10), claim("gb", 2, 10),
            ])


if __name__ == "__main__":
    unittest.main()
