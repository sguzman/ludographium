# Dataset release history

Ludographium data tags identify immutable metadata snapshots independently of the Rust client, JSON schema versions, and upstream source revisions. Each published release carries a deterministic metadata-only runtime archive, a SHA-256 checksum, the original source registers, and attribution notices.

| Dataset | Published | Curated works | Curated releases | Exact builds | Summary |
| --- | --- | ---: | ---: | ---: | --- |
| [`data-v1.0.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.0.0) | 2026-10-09 | 4 | 4 | 4 | First durable offline dataset, ten platforms, source claims and provenance, original single-observation identity examples |
| [`data-v1.1.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.1.0) | 2026-10-09 | 8 | 10 | 12 | Four additional reviewed works with distinct same-platform revisions and regional releases |
| [`data-v1.2.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.2.0) | 2026-10-09 | 11 | 13 | 19 | Three additional revision families, including the first curated Nintendo DS title, and conservative review tooling |
| [`data-v1.3.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.3.0) | 2026-10-09 | 15 | 17 | 28 | Four additional exact revision families and source-linked field-claim audit infrastructure |

## Changes in data-v1.3.0

- Curated **Super Mario Advance 4** for Game Boy Advance: source-labelled Japan original, Rev 1, and Rev 2 are separately fingerprinted media builds.
- Curated **Donkey Kong Country 2: Diddy's Kong Quest** for SNES: USA English/French original and Rev 1 have distinct exact SHA-1 media builds.
- Curated **Banjo-Kazooie** for Nintendo 64: USA original and Rev 1 are preserved as separate 16 MiB media builds under a narrowly scoped edition.
- Curated **Golden Axe** for Genesis: World original and Rev A are preserved as separate exact 512 KiB media builds.
- Added a [cross-source evidence audit](CROSS-SOURCE-REVIEW.md) for curated builds and a **prioritized revision review** with field-DAT coverage. These tools are read-only and never promote bibliographic claims or revision leads into verified game identities.
- Brought the Rust offline curated reader's parent-evidence and unique source-occurrence rules into parity with the Python ledger validator. New tests reject competing source ownership, missing parent evidence, title/CRC mismatches, and unsupported implicit joins.

The pinned Libretro source revision and all 41,491 base source observations are unchanged. The release updates the curated identity projection and its manifest digest, not the source DAT archives or underlying bibliographic claim dataset.

## Changes in data-v1.2.0

- Curated **The Legend of Zelda: Link's Awakening** for Game Boy, preserving the original, Rev 1, and Rev 2 as three distinct media builds under one narrowly scoped USA/Europe release label.
- Curated **Advance Wars** for Game Boy Advance, preserving the original USA and Rev 1 media images separately.
- Curated **Animal Crossing: Wild World** for Nintendo DS, preserving the original USA and Rev 1 media images separately. This introduces the first curated Nintendo DS work.
- Added a deterministic [revision candidate review workflow](IDENTITY-REVIEW.md) that scans all ten platform source catalogs and flags only exact edition-name pairs, with single observation per revision qualifier, equal byte lengths, distinct SHA-1 values, and complete upstream evidence locators. Review candidates are not automatically accepted work/release/build identities.
- Strengthened curation validation to reject conflicting ownership of source occurrences across curated works or releases.

The original Libretro revision and the 41,491 base source observations are unchanged. The newly curated identities are additional attributed editorial records, not a retroactive claim of game verification. The runtime archive still contains no game ROMs or firmware.

## Changes in data-v1.1.0

- Added **Super Mario Land** (Game Boy): original World-labelled media and Rev 1, two builds attached to a single narrowly bounded release.
- Added **Pokémon Crystal Version** (Game Boy Color): USA and USA/Europe Rev 1 records, linked at the work level while retaining different release identities.
- Added **Alex Kidd in Miracle World** (Master System): separate USA/Europe and USA/Europe/Brazil Rev 1 release records under an evidence-backed work.
- Added **Columns** (Game Gear): original Japan (En) and Rev A images, represented as separate builds of a bounded release.
- Strengthened curation validation: each release's cited observations must belong to its parent work, and each build's evidence must belong to its parent release. SHA-1 plus byte length remain exact media evidence, not general proof that two games are equivalent.
- Added black-box CLI regression checks for curated revision and territorial links and expanded release notes to report work/release/build counts.

The underlying source collection remains pinned to Libretro revision `fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90`. The 41,491 identification observations, ten platform indexes, and 129,008 bibliographic claims did not change. The curated source-ledger projection and the containing integrity manifest **did** change; consumers must not substitute the newer files into the older release.

## Version compatibility

Both releases use the same v1 metadata serialization contract. A higher data minor version may add curated records and change artifact digests even when the original source snapshot remains unchanged. Stable UUIDs in `data-v1.0.0` are preserved without reminting in `data-v1.1.0`; downstream consumers may add the new entities without silently merging unrelated work or revision identities.

Applications should pin and verify a complete tagged release. Consult the [consumer migration guide](COMPATIBILITY.md) and the [publication policy](RELEASING.md). Source-specific rights, archival attribution and license obligations travel with each archive.
