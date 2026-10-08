#!/usr/bin/env python3
"""Import an immutable, pinned clrmamepro DAT as source observations. No ROM access."""
import argparse
import hashlib
import json
import re
from pathlib import Path

GAME = re.compile(r'^game \(\r?\n(.*?)^\)\r?$', re.M | re.S)
SCALAR = re.compile(r'^\s*([a-z0-9_]+)\s+"((?:\\.|[^"\\])*)"\s*$', re.I)
ROM = re.compile(r'^\s*rom\s*\(\s*(.*?)\s*\)\s*$', re.I)
PAIR = re.compile(r'\s*([a-z0-9_]+)\s+(?:"((?:\\.|[^"\\])*)"|([^\s"]+))', re.I)
HEADER_VERSION = re.compile(r'^\s*version\s+"([^"]+)"\s*$', re.M)


def unquote(value):
    return re.sub(r'\\([\\"])', r'\1', value)


def fields(text):
    out = {}
    pos = 0
    while pos < len(text):
        m = PAIR.match(text, pos)
        if not m:
            raise ValueError(f"unsupported ROM field syntax: {text[pos:pos + 80]!r}")
        key = m[1].lower()
        if key in out:
            raise ValueError(f"duplicate field: {key}")
        out[key] = unquote(m[2]) if m[2] is not None else m[3]
        pos = m.end()
    if 'size' in out:
        out['size'] = int(out['size'])
    if 'crc' in out:
        out['crc32'] = out.pop('crc').upper()
    for h, length in (('crc32', 8), ('md5', 32), ('sha1', 40)):
        if h in out:
            if len(out[h]) != length or not re.fullmatch('[a-fA-F0-9]+', out[h]):
                raise ValueError(f"bad {h}: {out[h]}")
            out[h] = out[h].upper()
    return out


def import_dat(data, source, platform):
    data_file = next((f for f in source['files'] if f['platform'] == platform), None)
    if data_file is None:
        raise ValueError(f"unregistered platform: {platform}")
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != data_file['git_blob_sha']:
        raise ValueError(f"source blob SHA mismatch: {blob} != {data_file['git_blob_sha']}")
    decoded = data.decode('utf-8')
    matches = list(GAME.finditer(decoded))
    declared_count = len(re.findall(r'^game \(\r?$', decoded, re.M))
    if len(matches) != declared_count:
        raise ValueError(f"unsupported game blocks: parsed {len(matches)} of {declared_count}")
    records = []
    for ordinal, match in enumerate(matches, 1):
        record = {'source_ordinal': ordinal, 'roms': []}
        for line in match.group(1).splitlines():
            if not line.strip():
                continue
            rm = ROM.fullmatch(line)
            if rm:
                record['roms'].append(fields(rm[1]))
            else:
                sm = SCALAR.fullmatch(line)
                if not sm:
                    raise ValueError(f"unsupported game line {ordinal}: {line!r}")
                key = sm[1].lower()
                if key in record:
                    raise ValueError(f"duplicate game field {ordinal}: {key}")
                record[key] = unquote(sm[2])
        if not record.get('name') or not record['roms']:
            raise ValueError(f"missing title or ROM fingerprint: record {ordinal}")
        records.append(record)
    ver = HEADER_VERSION.search(decoded.split('game (', 1)[0])
    return {
        'schema_version': 1,
        'kind': 'source-observations',
        'platform': platform,
        'source_id': source['source_id'],
        'source_revision': source['repository_revision'],
        'source_path': data_file['source_path'],
        'source_blob_sha': blob,
        'source_license': source['declared_repository_license'],
        'dat_version': ver[1] if ver else None,
        'record_count': len(records),
        'rom_count': sum(len(r['roms']) for r in records),
        'records': records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--platform', required=True)
    parser.add_argument('--dat', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding='utf-8'))
    output = import_dat(args.dat.read_bytes(), source, args.platform)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f"{args.platform}: {output['record_count']} source records, {output['rom_count']} media fingerprints")


if __name__ == '__main__':
    main()
