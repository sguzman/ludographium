#!/usr/bin/env python3
"""End-to-end provenance regression checks for curated regional and revision links.

Uses known SHA-1 claims from the pinned source catalog. No ROM files are needed.
"""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = {
    "gb": (
        "3A4DDB39B234A67FFB361EE7ABC3D23E0A8B1C89",
        "418203621B887CAA090215D97E3F509B79AFFD3E",
    ),
    "gbc": (
        "F4CD194BDEE0D04CA4EAC29E09B8E4E9D818C133",
        "F2F52230B536214EF7C9924F483392993E226CFB",
    ),
    "sms": (
        "8CECF8ED0F765163B2657BE1B0A3CE2A9CB767F4",
        "6D052E0CCA3F2712434EFD856F733C03011BE41C",
    ),
    "gg": (
        "8B39BA23132AF102B8DC313C5C1C211F4A4F27E1",
        "D83FD16BD23C51750555A692535DAA171ED41AF0",
    ),
}


def query(platform: str, sha1: str, *, enriched: bool):
    command = [
        "cargo", "run", "--locked", "--quiet", "-p", "ludographium", "--",
        "--platform", platform, "--sha1", sha1, "--curated",
    ]
    if enriched:
        command.append("--enriched")
    p = subprocess.run(command, cwd=ROOT, check=True, text=True, capture_output=True)
    result = json.loads(p.stdout)
    assert result["match_count"] >= 1, (platform, sha1)
    matches = [m for m in result["matches"] if m["curated_identities"]]
    assert len(matches) == 1, (platform, sha1, result)
    identity = matches[0]["curated_identities"]
    assert len(identity) == 1, (platform, sha1, identity)
    value = identity[0]
    assert value["release"]["platform"] == platform
    assert value["build"]["media"]["sha1"] == sha1
    return value


def main():
    for platform, (base_sha, revised_sha) in SAMPLES.items():
        base = query(platform, base_sha, enriched=False)
        revised = query(platform, revised_sha, enriched=False)
        assert base["work"]["id"] == revised["work"]["id"], platform
        assert base["build"]["id"] != revised["build"]["id"], platform
        if platform in {"gb", "gg"}:
            assert base["release"]["id"] == revised["release"]["id"], platform
        else:
            assert base["release"]["id"] != revised["release"]["id"], platform

        # Bibliographic enrichment must preserve the same stable graph links.
        enriched = query(platform, revised_sha, enriched=True)
        for layer in ("work", "release", "build"):
            assert enriched[layer]["id"] == revised[layer]["id"], (platform, layer)

    print("PASS: eight curated exact-media variants, four works, release distinctions, enrichment")


if __name__ == "__main__":
    main()
