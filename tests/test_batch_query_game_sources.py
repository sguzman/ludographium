"""Bounds and schema validation for source-only JSONL batch queries."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from batch_query_game_sources import load_requests


class OriginalSourceBatchTests(unittest.TestCase):
    def read_case(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "queries.jsonl"
            path.write_text(content, encoding="utf-8")
            return load_requests(path)

    def test_independent_title_and_hash_requests(self):
        rows = self.read_case(
            '{"id":"tetris","title":"Tetris","limit":2}\n'
            '{"id":"sha","sha1":"a' + "0" * 39 + '"}\n'
        )
        self.assertEqual([row["id"] for row in rows], ["tetris", "sha"])
        self.assertEqual(rows[0]["limit"], 2)
        self.assertEqual(rows[1]["limit"], 5)

    def test_invalid_batch_inputs_are_rejected_before_db_access(self):
        for value in (
            "",
            '{"id":"empty"}\n',
            '{"id":"duplicate","title":"Mario"}\n'
            '{"id":"duplicate","title":"Tetris"}\n',
            '{"id":"wrong","title":"Mario","platform":"nes"}\n',
            '{"id":"dupk","title":"Mario","title":"Sonic"}\n',
            '{"id":"invalid-sha","sha1":"bad"}\n',
            '{"id":"limit","title":"Mario","limit":51}\n',
            '{"id":"unterminated","title":"Mario"}',
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.read_case(value)


if __name__ == "__main__":
    unittest.main()
