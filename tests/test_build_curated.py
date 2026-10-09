import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_curated import canonical_bytes


class CuratedExportTests(unittest.TestCase):
    def test_portable_curated_records_validate_against_original_source(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads(canonical_bytes(root))
        self.assertEqual(data["kind"], "curated-identity-ledger")
        self.assertEqual(len(data["works"]), 8)
        self.assertEqual(len(data["releases"]), 10)
        self.assertEqual(len(data["builds"]), 12)
        self.assertTrue(all("sha1" in entry["media"] for entry in data["builds"]))

    def test_multi_revision_evidence_relations_are_explicit(self):
        root = Path(__file__).resolve().parents[1]
        data = json.loads(canonical_bytes(root))
        works = {work["id"]: work for work in data["works"]}
        releases = {release["id"]: release for release in data["releases"]}
        builds_by_release = {}
        for build in data["builds"]:
            builds_by_release.setdefault(build["release_id"], []).append(build)
        def occurrences(row):
            return {(e["source_id"], e["source_revision"], e["source_path"],
                     e["source_blob_sha"], e["source_ordinal"])
                    for e in row["evidence"]}

        for release in data["releases"]:
            self.assertTrue(occurrences(release) <= occurrences(works[release["work_id"]]))
        for build in data["builds"]:
            self.assertTrue(occurrences(build) <= occurrences(releases[build["release_id"]]))

        mario = next(x for x in data["works"] if x["preferred_title"] == "Super Mario Land")
        mario_releases = [r for r in data["releases"] if r["work_id"] == mario["id"]]
        self.assertEqual(len(mario_releases), 1)
        variants = builds_by_release[mario_releases[0]["id"]]
        self.assertEqual(len(variants), 2)
        self.assertEqual({b["media"]["size"] for b in variants}, {65536})
        self.assertEqual(len({b["media"]["sha1"] for b in variants}), 2)

        crystal = next(x for x in data["works"]
                       if x["preferred_title"] == "Pokemon - Crystal Version")
        crystal_releases = [r for r in data["releases"] if r["work_id"] == crystal["id"]]
        self.assertEqual(len(crystal_releases), 2)
        self.assertEqual({len(builds_by_release[r["id"]]) for r in crystal_releases}, {1})

    def test_canonical_encoding_is_stable(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(canonical_bytes(root), canonical_bytes(root))


if __name__ == "__main__":
    unittest.main()
