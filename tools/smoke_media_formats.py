#!/usr/bin/env python3
"""Black-box tests of opt-in conversion without real games or firmware."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def invoke(*args: str, expect_ok=True):
    p = subprocess.run(
        ["cargo", "run", "--locked", "--quiet", "-p", "ludographium", "--", *args],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    if expect_ok and p.returncode != 0:
        raise AssertionError(f"CLI failed: {p.stderr}")
    if not expect_ok:
        if p.returncode == 0:
            raise AssertionError(f"CLI unexpectedly accepted: {args}")
        return
    return json.loads(p.stdout)


def check_mode(path: Path, platform: str, media_format: str, expected: bytes):
    d = invoke("--platform", platform, "--file", str(path), "--media-format", media_format)
    assert d["input_kind"] == "explicit-normalized-local-file-bytes", d
    assert d["media_format"] == media_format, d
    assert d["normalized_sha1"] == hashlib.sha1(expected).hexdigest().upper(), d
    assert d["normalized_size"] == len(expected), d
    assert d["match_count"] == 0 and d["matches"] == [], d
    e = invoke("--platform", platform, "--file", str(path), "--media-format", media_format, "--enriched")
    assert e["normalized_sha1"] == d["normalized_sha1"], e
    assert e["normalized_size"] == d["normalized_size"], e
    assert "enrichment_source" in e, e


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        nes_rom = bytes([0x42]) * 16_384
        header = b"NES\x1a" + bytes([1, 0]) + bytes(10)
        nes = root / "synthetic.nes"
        nes.write_bytes(header + nes_rom)
        check_mode(nes, "nes", "nes-ines", nes_rom)

        snes_rom = bytes([0x81]) * 32_768
        snes = root / "synthetic.smc"
        snes.write_bytes(bytes([0xff]) * 512 + snes_rom)
        check_mode(snes, "snes", "snes-copier512", snes_rom)

        n64_rom = bytes([0x80, 0x37, 0x12, 0x40, 0x10, 0x11, 0x12, 0x13])
        v64_bytes = bytearray(n64_rom)
        for i in range(0, len(v64_bytes), 2):
            v64_bytes[i], v64_bytes[i + 1] = v64_bytes[i + 1], v64_bytes[i]
        v64 = root / "synthetic.v64"
        v64.write_bytes(v64_bytes)
        check_mode(v64, "n64", "n64-v64", n64_rom)
        n64_bytes = bytearray(n64_rom)
        for i in range(0, len(n64_bytes), 4):
            n64_bytes[i:i + 4] = n64_bytes[i:i + 4][::-1]
        n64 = root / "synthetic.n64"
        n64.write_bytes(n64_bytes)
        check_mode(n64, "n64", "n64-n64", n64_rom)

        # Default matching does not silently strip headers or reverse byte order.
        unconverted = invoke("--platform", "nes", "--file", str(nes))
        assert unconverted["input_kind"] == "exact-local-file-bytes"
        assert unconverted["match_count"] == 0

        invoke("--platform", "all", "--file", str(nes),
               "--media-format", "nes-ines", expect_ok=False)
        invoke("--platform", "n64", "--file", str(nes),
               "--media-format", "nes-ines", expect_ok=False)
        invoke("--platform", "nes", "--title", "Mario",
               "--media-format", "nes-ines", expect_ok=False)
        invoke("--platform", "nes", "--file", str(nes),
               "--media-format", "n64-v64", expect_ok=False)

        corrupted = root / "corrupt.nes"
        corrupted.write_bytes(header + nes_rom + b"\x00")
        invoke("--platform", "nes", "--file", str(corrupted),
               "--media-format", "nes-ines", expect_ok=False)
    print("PASS: explicit media-format CLI smoke tests, validation, and raw-byte isolation")


if __name__ == "__main__":
    main()
