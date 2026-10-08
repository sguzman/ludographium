import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_docs import validate_markdown


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "docs").mkdir()
        (self.root / "docs/SCOPE.md").write_text("# Scope\n")

    def test_local_link_and_code_fence(self):
        file = self.root / "README.md"
        ticks = chr(96) * 3
        file.write_text("[Documentation](docs/SCOPE.md)\n" + ticks +
                        "sh\n[example](missing)\n" + ticks + "\n")
        self.assertEqual(validate_markdown(self.root, [file]), [])

    def test_broken_relative_link(self):
        file = self.root / "README.md"
        file.write_text("[Broken](docs/missing.md)\n")
        self.assertIn("broken", validate_markdown(self.root, [file])[0])

    def test_unclosed_code_fence(self):
        file = self.root / "README.md"
        file.write_text(chr(96) * 3 + "sh\n# Sample\n")
        self.assertIn("unclosed", validate_markdown(self.root, [file])[0])

    def test_outside_root_cannot_be_linked(self):
        file = self.root / "README.md"
        file.write_text("[Outside](../../etc/passwd)\n")
        self.assertIn("unsafe", validate_markdown(self.root, [file])[0])


if __name__ == "__main__":
    unittest.main()
