# Scope

Ludographium is a reusable catalog of **console and handheld video-game metadata**. Its core purpose is to identify and describe games across regions, platforms, releases, and revisions while preserving the evidence for each recorded fact.

## Cataloged information

The scope includes platform identifiers; original and localized titles; publication and release information; regional and language variants; developers and publishers; product and serial codes; edition or revision indicators; and media-identification metadata such as file sizes and cryptographic or legacy checksums.

References to cover artwork, screenshots, and packaging may be cataloged when their provenance and reuse conditions are understood. Asset descriptions and links are distinct from hosting or redistributing those assets.

Game binaries, disc images, firmware, executable patches, and cheat-code collections are outside the catalog. Ludographium also does not attempt an ontology of gameplay mechanics, narrative concepts, or the meaning of games as cultural works.

## Three levels of identity

| Level | Meaning | Example distinction |
| --- | --- | --- |
| **Work** | The underlying game as an identified creative work | A game across several platforms or localized editions |
| **Release** | A publication on a particular platform, in a territory, edition, or language configuration | North American and Japanese editions |
| **Build / media variant** | A particular revision or identifiable byte representation | Revision A and Revision B cartridge images |

These levels are a **curation target**, not yet a claim that every imported record has been assigned a canonical identity. The current source-observation layer preserves the assertions of the original provider without merging them.

Titles, filenames, product codes, and hashes have different identifying power. A checksum may characterize an exact file; it does not identify an abstract work. Likewise, similar regional titles do not establish that two records refer to the same release.

## Interoperability

The catalog exports platform-scoped records for offline lookup by emulators, frontends, library managers, and preservation tools. Platform identifiers can align with other game-related datasets, including Cheatarium; cross-catalog links require explicit evidence for game and build identity rather than matching title slugs.

See [the data model](MODEL.md) for record definitions and [the consumer guide](CONSUMERS.md) for the current export format.
