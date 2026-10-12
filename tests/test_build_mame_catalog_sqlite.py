"""Safety checks for the optional local MAME source-evidence database."""
import argparse
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_mame_catalog_sqlite import (
    numeric_size, optional_sha1, query, query_libretro, query_review, unicode_casefold,
    unsupported_mode_filters
)


class SqliteMameSourceGuards(unittest.TestCase):
    def test_media_size_has_no_guessing(self):
        self.assertEqual(numeric_size("0x200000"), 2097152)
        self.assertEqual(numeric_size("65536"), 65536)
        self.assertIsNone(numeric_size(None))
        with self.assertRaises(ValueError):
            numeric_size("unknown")

    def test_multilingual_titles_casefold_without_modifying_literals(self):
        self.assertEqual(unicode_casefold("POKÉMON"), "pokémon")
        self.assertEqual(unicode_casefold("ＡＢＣ"), "abc")
        self.assertEqual(unicode_casefold("Σ"), unicode_casefold("σ"))
        self.assertEqual(unicode_casefold(None), "")

    def test_source_digest_needs_strict_hex(self):
        self.assertEqual(optional_sha1("AB" * 20), "ab" * 20)
        with self.assertRaises(ValueError):
            optional_sha1("z" * 40)

    def test_query_rejects_unbounded_or_invalid_input_before_sql(self):
        for kwargs in ({"limit": 0}, {"limit": 201}, {"media_sha1": "xyz"},
                       {"source_list": " "}, {"title": "x" * 251}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query(None, **kwargs)

    def test_source_mode_rejects_cross_provider_flags(self):
        values = {
            "list": None, "publisher": None, "year": None,
            "libretro_platform": None, "platform": None,
            "region": None, "title": None, "serial": None,
            "sha1": None, "linked_only": False,
        }
        mame = argparse.Namespace(**values, query=True, query_libretro=False)
        mame.platform = "gb"
        self.assertEqual(unsupported_mode_filters(mame), ["platform"])
        libretro = argparse.Namespace(**values, query=False, query_libretro=True)
        libretro.publisher = "Nintendo"
        self.assertEqual(unsupported_mode_filters(libretro), ["publisher"])
        review = argparse.Namespace(
            **values, query=False, query_libretro=False, query_review=True
        )
        review.sha1 = "a" * 40
        self.assertEqual(unsupported_mode_filters(review), ["sha1"])
        builds = argparse.Namespace(**values, query=False, query_libretro=False)
        builds.title = "unwanted"
        self.assertEqual(unsupported_mode_filters(builds), ["title"])

    def test_stable_source_review_rejects_unsupported_filters(self):
        for kwargs in ({"limit": 0}, {"limit": 201},
                       {"review_id": "lgreview:v1:wrong"},
                       {"priority_class": "canonical-game"},
                       {"source_list": " "}, {"evidence_type": "guessed"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query_review(None, **kwargs)

    def test_libretro_query_filters_fail_before_database_access(self):
        for kwargs in ({"limit": 0}, {"limit": 201}, {"sha1": "xyz"},
                       {"platform": " "}, {"region": "x" * 251}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                query_libretro(None, **kwargs)


if __name__ == "__main__":
    unittest.main()
