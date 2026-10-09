"""Check committed Wikidata source text without downloading or building SQLite."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/wikidata/v1"
QID = re.compile(r"Q[1-9]\d*\Z")


class SourceTextTests(unittest.TestCase):
    def test_text_corpus_manifest_and_original_source_lineage(self):
        manifest = json.loads((FOLDER / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["kind"], "wikidata-console-text-corpus")
        self.assertEqual(manifest["platform_collections"], 16)
        self.assertEqual(manifest["item_platform_observations"], 15868)
        self.assertEqual(manifest["literal_date_claims"], 29333)
        self.assertEqual(manifest["original_query_rows"], 30341)
        self.assertEqual(manifest["source_snapshot_sha256"],
                         "db9d4c66041de776438b4316b34e1c648671889aea944efc6268446252f68734")
        files = {p.name for p in FOLDER.iterdir() if p.is_file()}
        self.assertEqual(files, {r["text_path"] for r in manifest["files"]} | {"manifest.json"})
        total = count = 0
        for info in manifest["files"]:
            raw = (FOLDER / info["text_path"]).read_bytes()
            total += len(raw)
            self.assertEqual(len(raw), info["text_bytes"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), info["text_sha256"])
            records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
            self.assertEqual(len(records), info["distinct_items"])
            qids = [r["qid"] for r in records]
            self.assertTrue(all(QID.fullmatch(q) for q in qids))
            self.assertEqual(qids, sorted(set(qids), key=lambda q: int(q[1:])))
            self.assertTrue(all(isinstance(r["dates"], list) for r in records))
            count += len(records)
        self.assertEqual(count, 15868)
        self.assertLess(total, 5_000_000)

    def test_no_binary_in_text_directory(self):
        for path in FOLDER.iterdir():
            self.assertIn(path.suffix, (".json", ".jsonl"))


if __name__ == "__main__":
    unittest.main()
