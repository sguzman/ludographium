# Provenance and reuse policy

Every imported snapshot must document the exact upstream organization, repository, revision, source path, Git blob SHA, source revision/version when provided, URL, collection date and declared license. Attribution must survive generated exports.

**Original vs. interpretation:** untouched DAT files go under `archive/<source>/`. Transformed records go under `generated/`; explanatory corrections go in future `curated/`. The original is never silently patched, and a source author's claim never becomes a test result just because it was indexed.

## Initial source

The first collection uses the Libretro Database repository's `metadat/no-intro` DATs. Libretro's repository declares **CC BY-SA 4.0** and explains that the DATs are imported from No-Intro and other groups. Attribution therefore names both Libretro and the No-Intro upstream, and identifies the specific snapshot rather than crediting Ludographium as original author.

- https://github.com/libretro/libretro-database
- https://github.com/libretro/libretro-database/blob/master/LICENSE
- https://github.com/libretro/libretro-database/blob/master/README.md
- https://creativecommons.org/licenses/by-sa/4.0/
- https://datomatic.no-intro.org/

**Caveat:** repository-level licensing does not guarantee that every third-party dataset, image or description carries identical rights. Track component terms and hold back any material whose redistribution rights are unclear. Downloading or indexing an image URL is not a license to redistribute the image. Do not ingest paywalled/API data contrary to contractual terms.

For redistributed material from CC BY-SA sources, comply with attribution, ShareAlike and marking adaptations. Code, if later licensed separately, must clearly distinguish its license from third-party dataset terms. Consumers inheriting source content must preserve attribution. See `sources/` for source-specific attribution.

## Required evidence for each accession

- Source identifier, upstream author/project, repository URL, upstream file path.
- Immutable revision and original file blob hash; content digest when available.
- Retrieval/collection timestamp, tooling/version, source declared license and rights caveats.
- Original files if redistribution is allowed; transformed records tied back to the original ordinal or upstream identifier.
- Counts, validation failures and any deliberate exclusions.

Never present title-based matches as verified, and do not make a claim about publishing date or product code without provenance.
