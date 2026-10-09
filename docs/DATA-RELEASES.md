# Dataset release history

Ludographium data tags identify immutable metadata snapshots independently of the Rust client, JSON schema versions, and upstream source revisions. Each published release carries a deterministic metadata-only runtime archive, a SHA-256 checksum, the original source registers, and attribution notices. Since `data-v1.4.0`, releases also contain a complete, SHA-256-verified SQLite corpus asset for offline SQL access to every source observation. Since `data-v1.5.0`, a separately versioned expanded SQLite companion includes 75 collections and all additional pinned original source bytes.

| Dataset | Published | Curated works | Curated releases | Exact builds | Summary |
| --- | --- | ---: | ---: | ---: | --- |
| [`data-v1.0.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.0.0) | 2026-10-09 | 4 | 4 | 4 | First durable offline dataset, ten platforms, source claims and provenance, original single-observation identity examples |
| [`data-v1.1.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.1.0) | 2026-10-09 | 8 | 10 | 12 | Four additional reviewed works with distinct same-platform revisions and regional releases |
| [`data-v1.2.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.2.0) | 2026-10-09 | 11 | 13 | 19 | Three additional revision families, including the first curated Nintendo DS title, and conservative review tooling |
| [`data-v1.3.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.3.0) | 2026-10-09 | 15 | 17 | 28 | Four additional exact revision families and source-linked field-claim audit infrastructure |
| [`data-v1.4.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.4.0) | 2026-10-09 | 15 | 17 | 28 | Full, queryable SQLite corpus across ten platforms; 41,491 source records, 129,008 preserved metadata claims |
| [`data-v1.5.0`](https://github.com/sguzman/ludographium/releases/tag/data-v1.5.0) | 2026-10-09 | 15 | 17 | 28 | Bulk accession of 75 platform collections, 117,145 source records, and 167,640 metadata claims; expanded SQLite with original DAT bytes |

## Changes in data-v1.5.0

- **Corpus-wide expansion:** 65 additional pinned identification DAT files contribute 75,654 new original source observations. Total coverage is **75 console and handheld platform collections**, **117,145 source observations**, and **117,145 media fingerprints**.
- **Bulk bibliographic metadata:** 279 additional pinned field-DAT files contribute **38,632** original claims. The expanded database preserves **167,640** source claims, of which **112,948** match conservatively to exact source occurrences; **19,763** source records have one or more attached bibliographic claims.
- **Preservation of ambiguous cases:** optical-media DATs without CRC32 retain their original serials and source attributes as explicitly unresolved `missing_crc` claims; unrelated records are never joined by title similarity.
- **Fully reproducible source lineage:** the extended SQLite includes original source bytes for all 65 new identification DATs and 279 field DATs, with file paths, revision identity and original Git blob checksums. The full source set is registered in [bulk expansion provenance](../sources/bulk-expansion-v1.json) and [bibliographic provenance](../sources/bulk-fields-v1.json).
- **Permanent expanded download:** [`ludographium-expanded-data-v1.5.0.sqlite`](https://github.com/sguzman/ludographium/releases/download/data-v1.5.0/ludographium-expanded-data-v1.5.0.sqlite) and its [SHA-256](https://github.com/sguzman/ludographium/releases/download/data-v1.5.0/ludographium-expanded-data-v1.5.0.sqlite.sha256), alongside the unchanged ten-system SQLite and JSON runtime. All release jobs passed.

These are **source observations, not a number of distinct canonical game works**. The 15 optional manually curated identity fixtures remain unchanged. No new identity relationships were minted during this expansion. See [the consumer and reproducibility guide](BULK-EXPANSION.md).

## Changes in data-v1.4.0

- **Complete offline SQLite corpus:** one normalized, indexed database covering all **41,491** identification source observations, **41,491** media fingerprints, and **129,008** attributed bibliographic claims across ten platforms. Unlike the separate curated examples, every original record is included.
- **Conservative metadata association:** **98,856** claims are linked to original source observations by the pinned, exact title-and-unique-CRC resolution rules; **16,937** source observations have one or more matched field claims. All other claims retain their unresolved statuses and original upstream evidence.
- **Self-contained provenance:** source repository revisions, original DAT file paths and blob SHA identifiers, original source fields, source notices and declared licensing are retained in the database.
- **Offline query and tests:** SQLite indexes support title and media-fingerprint lookups, an explicit matched-claims view, and unrestricted examination of unresolved claims. Tests verify complete counts, attribution, preservation, tamper rejection, SQLite foreign-key integrity, and deterministic rebuild.
- **Durable published asset:** `ludographium-corpus-data-v1.4.0.sqlite` and a SHA-256 companion sit beside the existing JSON runtime archive. Both were verified by the release pipeline. See [full-corpus use](CORPUS.md).

The pinned source revision and optional curated work/release/build ledger are unchanged from `data-v1.3.0`. This is a **corpus-wide consumer capability**, not a new batch of individually entered game identities.

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
