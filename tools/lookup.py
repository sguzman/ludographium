#!/usr/bin/env python3
"""Read-only checksum lookup in the offline Ludographium source index."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def find_matches(data, *, sha1=None, crc32=None, size=None):
    if bool(sha1) == bool(crc32):
        raise ValueError('specify exactly one of SHA-1 or CRC32')
    if crc32 and size is None:
        raise ValueError('CRC32 matching requires byte size to reduce collisions')
    checksum = (sha1 or crc32).upper()
    length = 40 if sha1 else 8
    if not re.fullmatch(r'[0-9A-F]{' + str(length) + '}', checksum):
        raise ValueError('invalid checksum')
    matches = []
    for record in data['records']:
        for rom in record['roms']:
            if rom.get('sha1' if sha1 else 'crc32') != checksum:
                continue
            if size is not None and rom.get('size') != size:
                continue
            matches.append({
                'platform': data['platform'],
                'title': record['name'],
                'region_claim': record.get('region'),
                'serial_claim': record.get('serial'),
                'rom': rom,
                'source': {
                    'id': data['source_id'],
                    'revision': data['source_revision'],
                    'path': data['source_path'],
                    'ordinal': record['source_ordinal'],
                    'blob_sha': data['source_blob_sha'],
                },
                'interpretation': 'source-fingerprint-association-not-verified-game-identity',
            })
    return matches

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform', choices=('snes', 'gb', 'gbc', 'gba', 'nes', 'nds'), required=True)
    h = p.add_mutually_exclusive_group(required=True)
    h.add_argument('--sha1')
    h.add_argument('--crc32')
    p.add_argument('--size', type=int, help='exact media length in bytes')
    a = p.parse_args()
    data = json.loads((ROOT / f'generated/v1/{a.platform}.json').read_text())
    matches = find_matches(data, sha1=a.sha1, crc32=a.crc32, size=a.size)
    print(json.dumps({'match_count': len(matches), 'matches': matches}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
