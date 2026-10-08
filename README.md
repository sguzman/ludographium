# Ludographium

**A provenance-first catalog of console and handheld video games.**

Ludographium collects structured metadata about console games and their releases. Original sources remain attributable and unchanged; normalized indexes make the records useful to emulators, library managers, and research tools without depending on a live service.

It catalogs titles, versions, regions, publication facts, product identifiers, and media fingerprints. It is not a ROM archive, cheat collection, or gameplay ontology.

## Collection

The initial accession spans four Nintendo platforms:

| Platform | Source records |
| --- | ---: |
| Super Nintendo | 4,268 |
| Game Boy | 2,254 |
| Game Boy Color | 2,566 |
| Game Boy Advance | 3,692 |
| **Total** | **12,780** |

These are original source observations, **not a count of distinct games**. Every record has an upstream title and fingerprint information, with additional fields depending on what the source provides.

Twenty more pinned Libretro DATs supply **44,683 bibliographic claims** across developer, publisher, release year, release month, and genre. Strict CRC32-and-title comparison attaches **40,875 claims** to base observations; conflicting or unmatched source statements remain visible rather than being silently assigned to games.

[Source coverage](reports/source-coverage-v1.json) · [Enrichment coverage](reports/enrichment-coverage-v1.json) · [Source registers](sources/README.md)

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

The [distribution manifest](generated/v1/distribution.json) publishes byte lengths and SHA-256 digests for nine consumer artifacts.

## Use the data

The Rust reader validates the source indexes before returning matches:

```sh
cargo run --locked -p ludographium -- --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

Add `--enriched` to include matched and unresolved bibliographic claims separately:

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
