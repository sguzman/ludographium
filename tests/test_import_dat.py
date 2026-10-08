import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from import_dat import import_dat, fields

DAT = b'''clrmamepro (\n\tname "Nintendo - Game Boy"\n\tversion "2026.08.01"\n)\n\ngame (\n\tname "Sample (USA)"\n\tregion "USA"\n\trom ( name "Sample (USA).gb" size 1024 crc ABCDEF01 md5 00000000000000000000000000000000 sha1 1111111111111111111111111111111111111111 )\n)'''

def source(data=DAT):
    sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    return {'source_id': 'libretro-no-intro', 'repository_revision': 'abcdef', 'declared_repository_license': 'CC-BY-SA-4.0', 'files': [{'platform': 'gb', 'source_path': 'src.dat', 'git_blob_sha': sha}]}

class ImportTests(unittest.TestCase):
    def test_valid(self):
        value = import_dat(DAT, source(), 'gb')
        self.assertEqual(value['record_count'], 1)
        self.assertEqual(value['records'][0]['name'], 'Sample (USA)')
        self.assertEqual(value['records'][0]['roms'][0]['size'], 1024)
        self.assertEqual(value['dat_version'], '2026.08.01')
        self.assertEqual(value['records'][0]['roms'][0]['crc32'], 'ABCDEF01')

    def test_tampered(self):
        with self.assertRaisesRegex(ValueError, 'blob SHA mismatch'):
            import_dat(DAT + b'x', source(), 'gb')

    def test_invalid_hash(self):
        with self.assertRaises(ValueError):
            fields('name "Foo" crc BAD')

    def test_unknown_line_rejected(self):
        changed = DAT.replace(b'\tregion "USA"', b'\tincomprehensible ( stuff )')
        with self.assertRaisesRegex(ValueError, 'unsupported game line'):
            import_dat(changed, source(changed), 'gb')

    def test_unsupported_block_rejected(self):
        changed = DAT.replace(b'game (', b'game (\n\tweird (', 1)
        with self.assertRaisesRegex(ValueError, 'unsupported game line'):
            import_dat(changed, source(changed), 'gb')

if __name__ == '__main__':
    unittest.main()
