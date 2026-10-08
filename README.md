# Ludographium

**A provenance-first catalog of console and handheld video games.**

Ludographium collects and organizes the metadata needed to identify games across platforms, regions, editions, and revisions. It preserves original source records alongside structured, machine-readable indexes so emulators, library managers, and research tools can use the same evidence without depending on a live service.

The catalog focuses on game metadata: names, platforms, publication details, product identifiers, media fingerprints, and provenance. Game binaries, firmware, cheats, and executable modifications belong outside this collection.

## The collection

The first accession comes from a pinned [Libretro Database](https://github.com/libretro/libretro-database) snapshot of No-Intro-derived DAT files.

| Platform | Source records |
| --- | ---: |
| Super Nintendo Entertainment System | 4,268 |
| Game Boy | 2,254 |
| Game Boy Color | 2,566 |
| Game Boy Advance | 3,692 |
| **Total** | **12,780** |

These counts represent **source records**, not unique games or independently verified releases. Current records include source titles and available regions, serials, date fields, file sizes, and CRC32/MD5/SHA-1 fingerprints. Coverage will expand to richer bibliographic information and additional systems.

## How it is organized

| Location | Purpose |
| --- | --- |
| [`archive/`](archive/libretro-no-intro/) | Original, unchanged source DAT files |
| [`sources/`](sources/) | Source register, authorship, pinned revisions, and rights information |
| [`generated/v1/`](generated/v1/) | Deterministic per-platform JSON indexes and a [catalog manifest](generated/v1/catalog.json) |
| [`platforms/`](platforms/platforms.json) | Platform identifiers |
| [`tools/`](tools/) | Import, verification, and local lookup utilities |
| [`docs/`](docs/SCOPE.md) | Data model, provenance, consumer guidance, and plans |

An imported record is a **source observation**. It is kept distinct from the curated identities planned for individual games, releases, and builds. That separation preserves conflicting evidence instead of prematurely merging games that happen to share a title or serial.

## Use the catalog

The initial indexes are readable offline. For example, the following checks the archive and looks up a known Game Boy media fingerprint:

```sh
python3 tools/verify_catalog.py
python3 tools/lookup.py --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

The lookup returns matching source observations and their provenance. Fingerprint matching identifies a particular byte representation in the source database; it does not by itself establish a canonical game identity.

Ludographium is designed to be consumed independently by emulator frontends such as Starbyte and other applications. Its current interchange format is described in the [consumer guide](docs/CONSUMERS.md).

## Documentation

- [Scope and identity boundaries](docs/SCOPE.md)
- [Data model](docs/MODEL.md)
- [Provenance and reuse](docs/PROVENANCE.md)
- [Consumer guide](docs/CONSUMERS.md)
- [Import and validation](docs/IMPORTING.md)
- [Source evaluation](docs/SOURCE-STRATEGY.md)
- [Roadmap](docs/ROADMAP.md)
