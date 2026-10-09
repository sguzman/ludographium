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

# Additional source-backed, same-region variants curated from the revision queue.
# A triple keeps base, Rev 1, and Rev 2 separately identifiable by exact bytes.
ADDITIONAL = {
    ("gb", "The Legend of Zelda: Link's Awakening"): (
        "602167F897B4F56FE8CEE837933DA3BED5882BBD",
        "5259E68522225A7A830E29EA17DFDDC33263CED5",
        "5AB63DEF958728933571C3B4F6AF54DB14F3F8B2",
    ),
    ("gba", "Advance Wars"): (
        "D0A0A4CFE9B95AC7118F7EF476F014CA0242EB65",
        "15053499D5B3F49128A941D7F2D84876F5424D0C",
    ),
    ("nds", "Animal Crossing: Wild World"): (
        "F1BEF752B30DC158D55B48518C80840A7C4586AF",
        "77FDE3E30E1E6068395D1F96EA63BE569B61C351",
    ),
    ("gba", "Super Mario Advance 4"): (
        "19F7928BC4FFD733D71884DAE9AD9B7F4007D38D",
        "FB38A1284013AB4E2480A1AADCEC9400D3A63A1D",
        "B3349AD79D20F1AE77D3E120F60D60EDDDBBC2D2",
    ),
    ("snes", "Donkey Kong Country 2: Diddy's Kong Quest"): (
        "3EC2035962918B5523D8B4745406F46F2A739B8D",
        "69D0F91BFD05837B44023E33A6699AA28FCA19CB",
    ),
    ("n64", "Banjo-Kazooie"): (
        "1FE1632098865F639E22C11B9A81EE8F29C75D7A",
        "DED6EE166E740AD1BC810FD678A84B48E245AB80",
    ),
    ("genesis", "Golden Axe"): (
        "564E51F6B7FE5281F281D5FCB66767AB83ECF7B9",
        "2CE17105CA916FBBE3AC9AE3A2086E66B07996DD",
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

    for (platform, title), sha1s in ADDITIONAL.items():
        nodes = [query(platform, sha, enriched=False) for sha in sha1s]
        assert {node["work"]["preferred_title"] for node in nodes} == {title}
        assert len({node["work"]["id"] for node in nodes}) == 1
        assert len({node["release"]["id"] for node in nodes}) == 1
        assert len({node["build"]["id"] for node in nodes}) == len(sha1s)
        assert [node["build"]["media"]["sha1"] for node in nodes] == list(sha1s)
        enriched = query(platform, sha1s[-1], enriched=True)
        assert enriched["work"]["id"] == nodes[-1]["work"]["id"]
        assert enriched["release"]["id"] == nodes[-1]["release"]["id"]
        assert enriched["build"]["id"] == nodes[-1]["build"]["id"]

    images = sum(len(shas) for shas in ADDITIONAL.values()) + 2 * len(SAMPLES)
    print(f"PASS: {images} revised exact-media images across "
          f"{len(ADDITIONAL) + len(SAMPLES)} curated work groups")


if __name__ == "__main__":
    main()
