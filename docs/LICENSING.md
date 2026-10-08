# Licensing and attribution

Ludographium combines independently developed software with attributed external metadata. These parts do not all have identical licensing terms.

## Original software and documentation

The project's original software tooling, Rust library, tests, and independently authored documentation are offered under the standard [MIT License](../LICENSE), to the extent the project contributors have the rights to license them.

## Imported and derived metadata

The preserved DAT sources in [`archive/`](../archive/) originate from external contributors. The [Libretro Database](https://github.com/libretro/libretro-database) declares [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/) for its repository at the pinned accession revision. Libretro and the upstream No-Intro and other contributing data authors retain their own rights.

The generated identification and enrichment indexes are transformations of those source DATs. Their contents are **not automatically relicensed under MIT** merely because the tools that process them are MIT-licensed. Attribution, ShareAlike, and other applicable source-specific obligations must be preserved when redistributing derived data.

Original metadata archives, their indexes, and the portable distribution manifest include the source revisions and immutable file identities listed in:

- [Identification source register](../sources/libretro-no-intro.json)
- [Bibliographic metadata source register](../sources/libretro-enrichment.json)
- [Provenance details](PROVENANCE.md)

No blanket claim is made that all upstream database records, descriptions, trademarks, or other third-party material are free of independent restrictions. Future source accessions must assess their own terms before redistribution.

## Consumer guidance

Applications may use Ludographium's MIT-licensed software independently of the data collection. When distributing catalog data or a [portable runtime archive](CONSUMERS.md), preserve the metadata's source attribution and comply with the applicable external licensing conditions. Consumers can inspect the original source registry entries without needing game binaries.

This document explains project licensing boundaries; it does not grant rights on behalf of third-party data authors.
