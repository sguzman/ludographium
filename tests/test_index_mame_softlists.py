"""Regression checks for the full, noncanonical MAME software-list projection."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from index_mame_softlists import build_expected, original_claims


class OriginalMameSoftwareRecordsTest(unittest.TestCase):
    def test_original_media_serial_and_region_evidence_is_attributed(self):
        source = (
            b'<?xml version="1.0"?><!DOCTYPE softwarelist SYSTEM "softwarelist.dtd">'
            b'<softwarelist name="sample">'
            b'<software name="a" cloneof="b"><description>A Game</description>'
            b'<year>19??</year><publisher>A Publisher</publisher>'
            b'<info name="serial" value="ABC-2"/>'
            b'<part name="cart"><dataarea name="rom">'
            b'<rom name="game.bin" sha1="0123456789012345678901234567890123456789"/>'
            b'</dataarea></part></software></softwarelist>'
        )
        rows = original_claims(source, "sample", "a" * 64, "source.xml")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["original_software_ordinal"], 1)
        self.assertEqual(rows[0]["original_year_literal"], "19??")
        self.assertEqual(rows[0]["original_software_attributes"]["cloneof"], "b")
        self.assertEqual(rows[0]["original_info_attributes"][0]["value"], "ABC-2")
        self.assertEqual(rows[0]["original_media_claims"][0]["kind"], "rom")
        self.assertIn("not-canonical", rows[0]["interpretation"])

    def test_full_source_projection_preserves_every_software_record(self):
        _, summary = build_expected(ROOT)
        self.assertEqual(summary["indexed_source_partitions"], 49)
        self.assertEqual(summary["source_observation_totals"]["software_entries"], 31464)
        self.assertEqual(len(summary["partitions"]), 49)


if __name__ == "__main__":
    unittest.main()
