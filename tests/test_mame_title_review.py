"""Conservative MAME vs Libretro original-title evidence normalization."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reconcile_mame_titles import normalized_title


class OriginalTitleReviewTests(unittest.TestCase):
    def test_only_region_and_language_suffixes_are_removed(self):
        self.assertEqual(
            normalized_title("Batman & Robin (USA, Europe) (En,Fr)"),
            "batman & robin",
        )
        self.assertEqual(normalized_title("Pokémon (Japan)"), "pokémon")
        self.assertEqual(
            normalized_title("Super Mario (Prototype)"),
            "super mario (prototype)",
        )
        self.assertEqual(normalized_title("Sonic (Revision A)"), "sonic")
        self.assertEqual(normalized_title("  TETRIS  "), "tetris")
        self.assertIsNone(normalized_title(""))


if __name__ == "__main__":
    unittest.main()
