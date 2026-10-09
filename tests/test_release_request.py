import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from release_request import parse_release_request, MAX_REQUEST_BYTES


class ReleaseRequestTests(unittest.TestCase):
    def valid(self, tag="data-v1.0.0"):
        return json.dumps({"schema_version": 1, "tag": tag}).encode()

    def test_versioned_tag(self):
        self.assertEqual(parse_release_request(self.valid()), "data-v1.0.0")
        self.assertEqual(parse_release_request(self.valid("data-v12.30.405")), "data-v12.30.405")

    def test_refuses_non_versioned_tag_and_injection(self):
        for tag in ("v1.0.0", "data-v01.0.0", "data-v1.0.0-rc1",
                    "data-v1.0.0\n", "data-v1.0.0/../../bad",
                    "", "data-v1.0.0;echo BAD"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                parse_release_request(self.valid(tag))

    def test_refuses_unknown_keys_and_missing_schema(self):
        for entry in (
            {"schema_version": 1, "tag": "data-v1.0.0", "ref": "malicious"},
            {"tag": "data-v1.0.0"},
            {"schema_version": 2, "tag": "data-v1.0.0"},
            {"schema_version": True, "tag": "data-v1.0.0"},
            {"schema_version": 1, "tag": 123},
            ["data-v1.0.0"],
        ):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                parse_release_request(json.dumps(entry).encode())

    def test_refuses_duplicate_keys_and_excessive_input(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_release_request(b'{"schema_version":1,"tag":"data-v1.0.0","tag":"data-v2.0.0"}')
        with self.assertRaises(ValueError):
            parse_release_request(b" " * (MAX_REQUEST_BYTES + 1))
        with self.assertRaises(ValueError):
            parse_release_request(b"")

    def test_refuses_invalid_json(self):
        with self.assertRaises((ValueError, UnicodeDecodeError)):
            parse_release_request(b"\xff")
        with self.assertRaises(ValueError):
            parse_release_request(b"{broken")


if __name__ == "__main__":
    unittest.main()
