"""Revision candidates are review leads and never automatic game identities."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from triage_identities import revisions_for_platform


def media(sha):
    return [{"name": "fixture.gb", "size": 32768, "sha1": sha * 40}]


def bundle(names):
    return {
        "schema_version": 1,
        "kind": "source-observations",
        "platform": "gb",
        "source_id": "source",
        "source_revision": "revision",
        "source_path": "original/source.dat",
        "source_blob_sha": "blobsha",
        "records": [
            {"source_ordinal": i, "name": name, "roms": media(hex(i)[2:].upper())}
            for i, name in enumerate(names, 1)
        ],
    }


class RevisionReviewTests(unittest.TestCase):
    def test_matches_exact_edition_and_records_provenance(self):
        groups = revisions_for_platform(bundle([
            "Game (World)",
            "Game (World) (Rev A)",
            "Game (World) (Rev B)",
            "Game (USA) (Rev A)",
            "Game 2 (World)",
        ]))
        self.assertEqual(len(groups), 1)
        row = groups[0]
        self.assertEqual(row["edition_label"], "Game (World)")
        self.assertEqual(row["evidence_status"], "review-only")
        self.assertEqual([m["revision"] for m in row["members"]], [None, "A", "B"])
        self.assertEqual([m["evidence"]["source_ordinal"] for m in row["members"]], [1, 2, 3])
        self.assertTrue(all(m["evidence"]["source_path"] == "original/source.dat"
                            for m in row["members"]))

    def test_never_groups_distinct_regions_or_games(self):
        self.assertEqual(revisions_for_platform(bundle([
            "Game (USA)", "Game (Europe) (Rev A)", "Game 2 (USA) (Rev A)"
        ])), [])

    def test_requires_base_and_a_revision(self):
        for names in [
            ["Game (USA) (Rev A)", "Game (USA) (Rev B)"],
            ["Game (USA)", "Game (USA)"],
            ["Game (USA) (Rev A)"],
            ["Game (USA)", "Game (USA) (Rev A) (Beta)"],
        ]:
            with self.subTest(names=names):
                self.assertEqual(revisions_for_platform(bundle(names)), [])

    def test_excludes_beta_hack_pirate_and_virtual_console(self):
        for modifier in ["Beta", "Proto", "Demo", "Hack", "Pirate", "Virtual Console", "Aftermarket"]:
            with self.subTest(modifier=modifier):
                self.assertEqual(revisions_for_platform(bundle([
                    f"Game (World) ({modifier})",
                    f"Game (World) ({modifier}) (Rev A)",
                ])), [])

    def test_excludes_ambiguous_same_byte_fingerprints(self):
        data = bundle(["Game (USA)", "Game (USA) (Rev A)"])
        data["records"][1]["roms"][0]["sha1"] = data["records"][0]["roms"][0]["sha1"]
        self.assertEqual(revisions_for_platform(data), [])

    def test_excludes_mixed_byte_domains_and_duplicate_revision_labels(self):
        # This is common in NES catalogs with paired headered and headerless
        # observations of the same nominal edition.
        data = bundle(["Game (USA)", "Game (USA)",
                       "Game (USA) (Rev 1)", "Game (USA) (Rev 1)"])
        self.assertEqual(revisions_for_platform(data), [])
        data = bundle(["Game (USA)", "Game (USA) (Rev 1)"])
        data["records"][1]["roms"][0]["size"] = 32784
        self.assertEqual(revisions_for_platform(data), [])

    def test_excludes_multifile_or_missing_checksums(self):
        data = bundle(["Game (USA)", "Game (USA) (Rev A)"])
        data["records"][0]["roms"].append(dict(data["records"][0]["roms"][0]))
        self.assertEqual(revisions_for_platform(data), [])
        data = bundle(["Game (USA)", "Game (USA) (Rev A)"])
        data["records"][1]["roms"][0]["sha1"] = None
        self.assertEqual(revisions_for_platform(data), [])

    def test_report_is_deterministic_and_tied_to_catalog_revision(self):
        import json
        import tempfile
        from triage_identities import build_report
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "generated/v1").mkdir(parents=True)
            (root / "generated/v1/catalog.json").write_text(json.dumps({
                "schema_version": 1, "source_revision": "revision",
                "platforms": [{"platform": "gb", "artifact_path": "generated/v1/gb.json"}],
            }))
            (root / "generated/v1/gb.json").write_text(json.dumps(bundle([
                "Game (World)", "Game (World) (Rev 1)"
            ])))
            left = build_report(root)
            right = build_report(root)
            self.assertEqual(left, right)
            self.assertEqual(left["kind"], "exact-edition-revision-review")
            self.assertEqual(left["platforms"][0]["review_groups"], 1)
            self.assertEqual(left["platforms"][0]["source_observations"], 2)
            changed = bundle(["Game (World)", "Game (World) (Rev 1)"])
            changed["source_revision"] = "other"
            (root / "generated/v1/gb.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "revision mismatch"):
                build_report(root)

    def test_rejects_unsupported_schema(self):
        data = bundle([])
        data["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "unsupported"):
            revisions_for_platform(data)


if __name__ == "__main__":
    unittest.main()
