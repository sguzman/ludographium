# Ludographium

**A provenance-first catalog of console and handheld video games.**

Ludographium collects structured metadata about console games and their releases. Original sources remain attributable and unchanged; normalized indexes make the records useful to emulators, library managers, and research tools without depending on a live service.

It catalogs titles, versions, regions, publication facts, product identifiers, and media fingerprints. It is not a ROM archive, cheat collection, or gameplay ontology.

**Source data are plain text, not binary databases.** The [Wikidata accession is checked into Git as small per-platform JSONL files](data/wikidata/v1/); SQLite is only an optional derived offline index. See the [source-format policy](docs/DATA-FORMATS.md). The earlier SQLite Release assets remain available for backward compatibility, but new releases will not publish those large binary databases.

## Collection

The original v1 JSON baseline covers ten console and handheld platforms (retained for compatibility). **The Git clone now contains the original text DAT metadata for all 75 platform collections and 117,145 source observations**, with [complete provenance and coverage details](docs/BULK-EXPANSION.md). The 65 added identification DATs and 279 bibliographic DATs are [tracked under `archive/libretro-bulk/metadat/`](archive/libretro-bulk/metadat), not stored exclusively in a generated database or fetched on demand.

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

The original 88 pinned Libretro DATs supply **129,008 bibliographic claims** across developer, publisher, release-year, release-month, genre, franchise, serial, age-rating, player-count, and rumble fields. Strict CRC32-and-title comparison attaches **98,856 claims** to base observations; conflicting or unmatched source statements remain visible rather than being silently assigned to games.

[75-platform bulk expansion](docs/BULK-EXPANSION.md) · [Source coverage](reports/source-coverage-v1.json) · [Enrichment coverage](reports/enrichment-coverage-v1.json) · [Reconciliation review queue](reports/reconciliation-queue-v1.json) · [Source registers](sources/README.md)

## Rust offline source search

The existing Rust CLI can search all **75 cloned identification DAT collections** directly. No Python, SQLite build or network connection is necessary:

```sh
cargo run --locked -- --source-dat --platform all --title "Adventure" --limit 5
cargo run --locked -- --source-dat --platform atari2600 --title "Asteroids"
```

The opt-in `--source-dat` mode reads the original, hash-verified DAT text. It retains original record ordinals, source paths and Git blob hashes. Title results are source observations, not canonical game identities; fingerprint matches are based on literal source SHA-1 or CRC32 plus size. The preexisting generated-JSON/ten-system Rust consumer path remains available unchanged. [Details](docs/BULK-EXPANSION.md).

## Repository structure

| Location | Description |
| --- | --- |
| [`archive/`](archive/) | Unmodified original DATs, including all 344 pinned additional console/handheld sources |
| [`sources/`](sources/) | Pinned source revisions, attribution, and reuse information |
| [`generated/`](generated/) | Reproducible identification and bibliographic claim indexes |
| [`data/wikidata/v1/`](data/wikidata/v1/) | Small, attributed, human-readable Wikidata JSONL source files |
| [`curated/`](curated/v1/identities.json) | Evidence-backed work, release and build identities (15 works, 17 releases, 28 exact builds) |
| [`platforms/`](platforms/platforms.json) | Platform identifiers |
| [`tools/`](tools/) | Import, lookup, auditing, and verification scripts |
| [`crates/ludographium/`](crates/ludographium/) | Rust metadata reader and CLI |

The [distribution manifest](generated/v1/distribution.json) publishes byte lengths and SHA-256 digests for 25 consumer artifacts, including curated identities, both source registers, and a standalone metadata-attribution notice. A deterministic, metadata-only runtime archive can be built from the manifest; successful main-branch GitHub Actions runs also attach this portable bundle for downstream use. The [latest pinned dataset, **data-v1.6.0**](https://github.com/sguzman/ludographium/releases/tag/data-v1.6.0) includes the 75-platform expanded SQLite, a separately attributed Wikidata-enriched database and source snapshot, the ten-platform SQLite, and the integrity-checked JSON runtime. Earlier releases remain intact and individually addressable; consult the [release history](docs/DATA-RELEASES.md) for version-specific coverage. Consumers can consult the [dataset release history](docs/DATA-RELEASES.md) and [versioned publication policy](docs/RELEASING.md).

## Expanded 75-platform dataset

The [released bulk SQLite corpus](https://github.com/sguzman/ludographium/releases/download/data-v1.5.0/ludographium-expanded-data-v1.5.0.sqlite) contains **117,145 source records and media fingerprints** plus **167,640 bibliographic source claims** spanning 75 dedicated console/handheld collections. Of these, **112,948 field claims** are conservatively matched; **19,763 source records** have some attached field metadata. The 65 new identification DATs and 279 additional bibliographic DATs are pinned by source revision and original Git blob hash. All original source files are preserved inside the expanded SQLite artifact, including metadata with missing or ambiguous checksums.

The existing ten-platform release remains an independently reproducible, compatible baseline. Source observations are not asserted to be distinct game identities.

## Independent Wikidata observations

A [separate CC0 Wikidata accession](docs/WIKIDATA.md) adds **15,868 platform-linked item observations** and **29,333 independently attributed publication-date claims** across 16 console mappings. The reproducible bulk matcher generated **8,971 title-based review candidates**, identifying 8,908 existing source observations with possible Wikidata counterparts; **126 links are explicitly ambiguous**. They are **not** accepted work or release identities. The raw query results and SHA-256 values are pinned in the [source accession register](sources/wikidata-accession-v1.json) and published as [the immutable `data-v1.6.0` Wikidata source snapshot](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-source-data-v1.6.0.json). A [Wikidata-enriched, fully offline SQLite download](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-data-v1.6.0.sqlite) is released separately from the 75-system base corpus.

## Complete metadata corpus

**All 41,491 source observations and all 129,008 bibliographic claims can now be queried from one offline SQLite database.** The [full-corpus export](docs/CORPUS.md) automatically combines source records, exact media checksums, and individually attributed field claims across all ten platforms. It retains all unresolved statements, so only the 98,856 safely matched claims are attached to their corresponding source observations. In the current snapshot, **16,937** source records have one or more matched bibliographic claims.

The SQLite export is a complete source-level collection, **not** a hand-selected list of curated game identities. Original source records are kept separate, and no source-title similarity is used to fabricate canonical game identities. Each main-branch validation run generates a downloadable, SHA-256-checked `ludographium-complete-corpus-sqlite` artifact. That database is permanently published as the [`data-v1.4.0` SQLite download](https://github.com/sguzman/ludographium/releases/download/data-v1.4.0/ludographium-corpus-data-v1.4.0.sqlite), with a [separate SHA-256 checksum](https://github.com/sguzman/ludographium/releases/download/data-v1.4.0/ludographium-corpus-data-v1.4.0.sqlite.sha256).

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
- [75-platform bulk data accession](docs/BULK-EXPANSION.md), [full-corpus SQLite export](docs/CORPUS.md), [offline consumer interface](docs/CONSUMERS.md), and [version compatibility](docs/COMPATIBILITY.md)
- [Importing and validating](docs/IMPORTING.md)
- [Source acquisition strategy](docs/SOURCE-STRATEGY.md)
- [Quality reports](reports/README.md) and [roadmap](docs/ROADMAP.md)
