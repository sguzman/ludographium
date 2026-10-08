#!/usr/bin/env python3
"""Fail if any archived source, generated bundle, or manifest diverges."""
import hashlib
import json
import sys
from pathlib import Path
from import_dat import import_dat

ROOT = Path(__file__).resolve().parents[1]

def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def verify():
    source = json.loads((ROOT / 'sources/libretro-no-intro.json').read_text())
    catalog = json.loads((ROOT / 'generated/v1/catalog.json').read_text())
    if catalog['schema_version'] != 1 or catalog['source_revision'] != source['repository_revision']:
        raise ValueError('catalog schema/revision mismatch')
    if len(catalog['platforms']) != len(source['files']):
        raise ValueError('catalog/platform registration mismatch')
    count = 0
    for p in catalog['platforms']:
        platform = p['platform']
        registered = next((x for x in source['files'] if x['platform'] == platform), None)
        if not registered:
            raise ValueError(f'unregistered platform: {platform}')
        raw = (ROOT / p['source_archive_path']).read_bytes()
        if git_blob(raw) != registered['git_blob_sha'] or git_blob(raw) != p['source_git_blob_sha']:
            raise ValueError(f'original source changed: {platform}')
        expected = import_dat(raw, source, platform)
        generated = (ROOT / p['artifact_path']).read_bytes()
        canonical = (json.dumps(expected, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
        if generated != canonical:
            raise ValueError(f'non-reproducible generated index: {platform}')
        if git_blob(generated) != p['artifact_git_blob_sha']:
            raise ValueError(f'generated bundle SHA changed: {platform}')
        if (expected['record_count'], expected['rom_count']) != (p['source_records'], p['rom_fingerprints']):
            raise ValueError(f'manifest counts mismatch: {platform}')
        count += expected['record_count']
        print(f"PASS {platform}: {expected['record_count']} source observations, source and artifact hashes agree")
    print(f'PASS total: {count} source observations in {len(catalog["platforms"])} collections')

if __name__ == '__main__':
    try:
        verify()
    except (OSError, KeyError, ValueError, UnicodeError) as e:
        print(f'FAIL {e}', file=sys.stderr)
        sys.exit(1)
