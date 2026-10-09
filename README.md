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
| [`curated/`](curated/v1/identities.json) | Evidence-backed work, release and build identities (15 works, 17 releases, 28 exact builds) |
| [`platforms/`](platforms/platforms.json) | Platform identifiers |
| [`tools/`](tools/) | Import, lookup, auditing, and verification scripts |
| [`crates/ludographium/`](crates/ludographium/) | Rust metadata reader and CLI |

The [distribution manifest](generated/v1/distribution.json) publishes byte lengths and SHA-256 digests for 25 consumer artifacts, including curated identities, both source registers, and a standalone metadata-attribution notice. A deterministic, metadata-only runtime archive can be built from the manifest; successful main-branch GitHub Actions runs also attach this portable bundle for downstream use. The [latest pinned dataset, **data-v1.3.0**](https://github.com/sguzman/ludographium/releases/tag/data-v1.3.0), contains the expanded reviewed identity graph. Earlier releases remain intact and individually addressable; consult the [release history](docs/DATA-RELEASES.md) for version-specific coverage. Consumers can consult the [dataset release history](docs/DATA-RELEASES.md) and [versioned publication policy](docs/RELEASING.md).

## Complete metadata corpus

**All 41,491 source observations and all 129,008 bibliographic claims can now be queried from one offline SQLite database.** The [full-corpus export](docs/CORPUS.md) automatically combines source records, exact media checksums, and individually attributed field claims across all ten platforms. It retains all unresolved statements, so only the 98,856 safely matched claims are attached to their corresponding source observations. In the current snapshot, **16,937** source records have one or more matched bibliographic claims.

The SQLite export is a complete source-level collection, **not** a hand-selected list of curated game identities. Original source records are kept separate, and no source-title similarity is used to fabricate canonical game identities. Each main-branch validation run generates a downloadable, SHA-256-checked `ludographium-complete-corpus-sqlite` artifact. A versioned SQLite companion will accompany the next published data release, independently of the existing JSON runtime archive.

**Corpus coverage, source acquisition and batch transformation are the priorities.** The 15 optional manually reviewed identity examples are not the ingestion method and do not limit the searchable catalog.

## Use the data

The Rust reader validates the source indexes before returning matches. Consumers may supply a known fingerprint or stream exact local media bytes without storing the file in Ludographium. Explicit NES, SNES, and N64 [byte-domain conversions](docs/BYTE-DOMAINS.md) are available for headered or byte-swapped local files and compatible ZIP members without changing the default exact-byte lookup:

```sh
cargo run --locked -p ludographium -- --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

A downloaded dataset may be checked end-to-end using the Rust command `--verify-runtime --root /path/to/extracted/runtime`, which validates all declared files and source catalog references against the included manifest. Verify the archive checksum from the release first; see the [consumer guide](docs/CONSUMERS.md).

Source-title discovery is also available when no fingerprint is known. Results remain original source records, not merged game identities:

```sh
cargo run --locked -p ludographium -- --platform nes --title "Mario" --limit 5
```

Use `--platform all` to identify media or search titles across **every registered system** when the platform is not known. The Rust library offers the equivalent `CatalogCollection` and `EnrichedCatalogCollection` APIs:

```sh
cargo run --locked -p ludographium -- --platform all --sha1 6B47BB75D16514B6A476AA0C73A683A2A4C18765 --curated
```

For an exact local file, use `--file /path/to/game` instead of a hash. Input is streamed and never added to the catalog. Compressed libraries can use `--zip` to inspect individual ZIP members without extracting them to disk:

```sh
cargo run --locked -p ludographium -- --platform all --zip /path/to/game.zip --enriched
```

Archive entries remain distinct source candidates, with bounds on the number of entries and decoded bytes. The file's representation must exactly match the source checksum; headers, archives, and byte-swapped formats are not silently normalized.

Add `--enriched` to fingerprint, file, or title queries to include matched and unresolved bibliographic claims separately:

```sh
cargo run --locked -p ludographium -- --enriched --platform gba --sha1 FC6163F99B71B05C10686A0D29010B31274E1DC4
```

Python lookup tools offer equivalent access. A match associates a fingerprint with an upstream record; it does not automatically establish a unique game, release, or build identity. Fifteen curated work identities now demonstrate explicitly reviewed revision and regional relationships (17 releases, 28 exact builds), including Nintendo DS, Nintendo 64 and Sega Genesis revisions. Most source records remain uncurated.

## Documentation

- [Scope](docs/SCOPE.md), [data model](docs/MODEL.md), and [media byte domains](docs/BYTE-DOMAINS.md)
- [Curated identity framework](docs/IDENTITIES.md), [revision candidate review](docs/IDENTITY-REVIEW.md), [cross-source field review](docs/CROSS-SOURCE-REVIEW.md), and [dataset release history](docs/DATA-RELEASES.md)
- [Licensing and third-party attribution](docs/LICENSING.md)
- [Provenance and licensing](docs/PROVENANCE.md)
- [Full-corpus SQLite export](docs/CORPUS.md), [offline consumer interface](docs/CONSUMERS.md), and [version compatibility](docs/COMPATIBILITY.md)
- [Importing and validating](docs/IMPORTING.md)
- [Source acquisition strategy](docs/SOURCE-STRATEGY.md)
- [Quality reports](reports/README.md) and [roadmap](docs/ROADMAP.md)
