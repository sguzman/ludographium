# Ludographium

**A provenance-first catalog of console and handheld video games.**

Ludographium collects structured metadata about console games and their releases. Original sources remain attributable and unchanged; normalized indexes make the records useful to emulators, library managers, and research tools without depending on a live service.

It catalogs titles, versions, regions, publication facts, product identifiers, and media fingerprints. It is not a ROM archive, cheat collection, or gameplay ontology.

## Collection

The current accession spans ten console and handheld platforms:

| Platform | Source records |
| --- | ---: |
| Super Nintendo | 4,268 |
| Game Boy | 2,254 |
| Game Boy Color | 2,566 |
| Game Boy Advance | 3,692 |
| Nintendo Entertainment System | 14,132 |
| Nintendo DS | 7,701 |
| Nintendo 64 | 1,435 |
| Sega Mega Drive / Genesis | 3,365 |
| Sega Master System | 1,163 |
| Sega Game Gear | 915 |
| **Total** | **41,491** |

These are original source observations, **not a count of distinct games**. Every record has an upstream title and fingerprint information, with additional fields depending on what the source provides.

88 pinned Libretro DATs supply **129,008 bibliographic claims** across developer, publisher, release-year, release-month, genre, franchise, serial, age-rating, player-count, and rumble fields. Strict CRC32-and-title comparison attaches **98,856 claims** to base observations; conflicting or unmatched source statements remain visible rather than being silently assigned to games.

[Source coverage](reports/source-coverage-v1.json) · [Enrichment coverage](reports/enrichment-coverage-v1.json) · [Reconciliation review queue](reports/reconciliation-queue-v1.json) · [Source registers](sources/README.md)

## Repository structure

| Location | Description |
| --- | --- |
| [`archive/`](archive/) | Unmodified original DATs |
| [`sources/`](sources/) | Pinned source revisions, attribution, and reuse information |
| [`generated/`](generated/) | Reproducible identification and bibliographic claim indexes |
| [`curated/`](curated/v1/identities.json) | Evidence-backed work/release/build identity ledger (not yet populated) |
| [`platforms/`](platforms/platforms.json) | Platform identifiers |
| [`tools/`](tools/) | Import, lookup, auditing, and verification scripts |
| [`crates/ludographium/`](crates/ludographium/) | Rust metadata reader and CLI |

The [distribution manifest](generated/v1/distribution.json) publishes byte lengths and SHA-256 digests for 21 consumer artifacts. A deterministic, metadata-only runtime archive can be built from the manifest; successful main-branch GitHub Actions runs also attach this portable bundle for downstream use.

## Use the data

The Rust reader validates the source indexes before returning matches. Consumers may supply a known fingerprint or stream exact local media bytes without storing the file in Ludographium:

```sh
cargo run --locked -p ludographium -- --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

Source-title discovery is also available when no fingerprint is known. Results remain original source records, not merged game identities:

```sh
cargo run --locked -p ludographium -- --platform nes --title "Mario" --limit 5
```

For an exact local file, use `--file /path/to/game` instead of a hash. Input is streamed and never added to the catalog. The file's representation must exactly match the source checksum; headers, archives, and byte-swapped formats are not silently normalized.

Add `--enriched` to fingerprint, file, or title queries to include matched and unresolved bibliographic claims separately:

```sh
cargo run --locked -p ludographium -- --enriched --platform gba --sha1 FC6163F99B71B05C10686A0D29010B31274E1DC4
```

Python lookup tools offer equivalent access. A match associates a fingerprint with an upstream record; it does not automatically establish a unique game, release, or build identity. A future curated layer will make those links explicit, with evidence.

## Documentation

- [Scope](docs/SCOPE.md) and [data model](docs/MODEL.md)
- [Curated identity framework](docs/IDENTITIES.md)
- [Provenance and licensing](docs/PROVENANCE.md)
- [Offline consumer interface](docs/CONSUMERS.md)
- [Importing and validating](docs/IMPORTING.md)
- [Source acquisition strategy](docs/SOURCE-STRATEGY.md)
- [Quality reports](reports/README.md) and [roadmap](docs/ROADMAP.md)
