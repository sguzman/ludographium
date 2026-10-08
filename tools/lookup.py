#!/usr/bin/env python3
"""Read-only checksum lookup in the offline Ludographium source index."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def make_match(data, record, rom):
    return {
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
    }


def find_title_matches(data, query, limit=50):
    """Discover original source titles, never merge or infer game identities."""
    if not isinstance(query, str) or not query.strip() or not 1 <= limit <= 200:
        raise ValueError('title must be nonempty; limit must be 1..200')
    needle = query.strip().casefold()
    total = 0
    matches = []
    for record in data['records']:
        if needle not in record['name'].casefold():
            continue
        total += 1
        if total <= limit:
            matches.extend(make_match(data, record, rom) for rom in record['roms'])
    return {
        'query_kind': 'source-title-substring',
        'total_source_records': total,
        'match_count': len(matches),
        'matches': matches,
    }


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
            matches.append(make_match(data, record, rom))
    return matches

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--platform', required=True)
    p.add_argument('--root', type=Path, default=ROOT)
    h = p.add_mutually_exclusive_group(required=True)
    h.add_argument('--sha1')
    h.add_argument('--crc32')
    h.add_argument('--title')
    p.add_argument('--limit', type=int, default=50)
    p.add_argument('--size', type=int, help='exact media length in bytes')
    a = p.parse_args()
    if not re.fullmatch(r'[a-z0-9]+', a.platform):
        p.error('invalid platform identifier')
    manifest = json.loads((a.root / 'generated/v1/catalog.json').read_bytes())
    registered = {entry['platform'] for entry in manifest['platforms']}
    if a.platform not in registered:
        p.error(f'unknown platform: {a.platform}; available: {", ".join(sorted(registered))}')
    data = json.loads((a.root / f'generated/v1/{a.platform}.json').read_bytes())
    if a.title is not None:
        if a.size is not None:
            p.error('--size is not meaningful for title discovery')
        output = find_title_matches(data, a.title, limit=a.limit)
    else:
        if a.limit != 50:
            p.error('--limit only applies to title discovery')
        matches = find_matches(data, sha1=a.sha1, crc32=a.crc32, size=a.size)
        output = {'match_count': len(matches), 'matches': matches}
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
