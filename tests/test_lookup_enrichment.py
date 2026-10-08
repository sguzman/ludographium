import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lookup_enrichment import join_claims, lookup


class EnrichedLookupTests(unittest.TestCase):
    def test_matched_and_conflicted_fields_never_merge(self):
        matches = [{
            "platform": "gb",
            "title": "Game",
            "rom": {"crc32": "ABCD1234"},
            "source": {"ordinal": 1}
        }]
        claims = [
            {"field": "developer", "value": "Studio", "source_comment": "Game",
             "source_path": "developer.dat", "source_blob_sha": "blob",
             "source_ordinal": 1, "crc32": "ABCD1234",
             "resolution": {"status": "matched", "base_source_ordinal": 1}},
            {"field": "publisher", "value": "Uncertain", "source_comment": "Other",
             "source_path": "publisher.dat", "source_blob_sha": "blob",
             "source_ordinal": 2, "crc32": "ABCD1234",
             "resolution": {"status": "comment_mismatch", "base_source_ordinal": None}},
        ]
        result = join_claims(matches, claims)
        self.assertEqual([x["field"] for x in result[0]["metadata_claims"]], ["developer"])
        self.assertEqual([x["field"] for x in result[0]["unresolved_source_claims"]], ["publisher"])

    def test_integrity_check_refuses_modified_enrichment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "generated/v1").mkdir(parents=True)
            (root / "generated/enrichment-v1").mkdir(parents=True)
            base = {
                "source_id": "source", "source_revision": "rev", "platform": "gb",
                "records": [{
                    "source_ordinal": 1, "name": "Example", "roms": [{
                        "name": "example.gb", "size": 128, "sha1": "A"*40, "crc32": "ABCDEF01"
                    }]
                }]
            }
            enriched = {
                "base_source_id": "source", "base_source_revision": "rev", "platform": "gb",
                "claims": []
            }
            base_path = root / "generated/v1/gb.json"
            extra_path = root / "generated/enrichment-v1/gb.json"
            base_path.write_text(json.dumps(base))
            extra_path.write_text(json.dumps(enriched))
            dist = {
                "schema_version": 1, "kind": "ludographium-distribution",
                "source_revision": "rev",
                "artifacts": [
                    {"path": p.relative_to(root).as_posix(),
                     "bytes": len(p.read_bytes()),
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for p in (base_path, extra_path)
                ]
            }
            (root / "generated/v1/distribution.json").write_text(json.dumps(dist))
            self.assertEqual(lookup(root, "gb", sha1="A"*40)["match_count"], 1)
            extra_path.write_text(json.dumps(enriched) + "modified")
            with self.assertRaisesRegex(ValueError, "digest/size mismatch"):
                lookup(root, "gb", sha1="A"*40)


if __name__ == "__main__":
    unittest.main()
