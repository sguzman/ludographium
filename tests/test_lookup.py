import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from lookup import find_matches

DATA = {'platform':'gb', 'source_id':'libretro-no-intro','source_revision':'abc',
        'source_path':'archive.dat','source_blob_sha':'hash', 'records':[
        {'source_ordinal':1,'name':'Sample','roms':[{'sha1':'A'*40,'crc32':'DEADBEEF','size':1024}]},
        {'source_ordinal':2,'name':'Collision','roms':[{'sha1':'B'*40,'crc32':'DEADBEEF','size':1024}]}
        ]}

class Lookups(unittest.TestCase):
    def test_sha1(self):
        matches=find_matches(DATA,sha1='a'*40)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['title'], 'Sample')
    def test_crc_collision_not_hidden(self):
        matches=find_matches(DATA,crc32='deadbeef',size=1024)
        self.assertEqual(len(matches),2)
    def test_crc_needs_size(self):
        with self.assertRaises(ValueError):
            find_matches(DATA,crc32='deadbeef')
    def test_checksum_validation(self):
        with self.assertRaises(ValueError):
            find_matches(DATA,sha1='bad')
    def test_absent(self):
        self.assertEqual(find_matches(DATA,sha1='C'*40), [])

if __name__ == '__main__':
    unittest.main()
