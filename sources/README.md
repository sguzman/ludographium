# Source register

Ludographium's source register records the origin, snapshot identity, and reuse conditions of each imported dataset. It provides the attribution and audit trail behind the machine-readable catalog.

## Accessioned sources

- [Libretro Database / No-Intro-derived DATs](libretro-no-intro.json) — ten pinned Nintendo and Sega platform identification source files, with upstream paths, Git blob hashes, authorship and licensing context.
- [Libretro bibliographic DATs](libretro-enrichment.json): revision-pinned developer, publisher, date, genre, franchise, serial, ESRB rating, player-count, and rumble-support source files.

The [bulk extension source register](bulk-expansion-v1.json) pins 65 additional console/handheld identification DATs; its [field source register](bulk-fields-v1.json) pins 279 additional bibliographic DATs. Their source bytes are preserved inside the [expanded SQLite](../docs/BULK-EXPANSION.md), without changing existing release tags or original ten-system JSON exports.

Original baseline source files are preserved under [`archive/libretro-no-intro/`](../archive/libretro-no-intro/). Their observations are published as [identification indexes](../generated/v1/) and separate [bibliographic claims](../generated/enrichment-v1/).

## Wikidata independent source accession

- [Wikidata CC0 platform mapping](wikidata-v1.json) — registered QIDs for 16 console categories, with original SPARQL queries for entire platform collections.
- [Wikidata snapshot and matching SHA-256 lock](wikidata-accession-v1.json) — full original query-response SHA, offline SQLite SHA, initial source corpus lock, and exact measured coverage. See [independent source interpretation](../docs/WIKIDATA.md).

## Additional providers

Other candidate catalogs and their reuse considerations are described in [metadata source strategy](../docs/SOURCE-STRATEGY.md). Each new accession will receive a source-specific register entry once the evidence, revision and permission requirements have been established.
