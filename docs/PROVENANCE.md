# Provenance and reuse

A useful game catalog must let readers distinguish an original observation, an imported source claim, and a later editorial interpretation. Ludographium keeps that evidence chain explicit.

## Source accession

Each accession identifies the upstream project and authors, repository or distribution URL, immutable snapshot revision, original file path, source-file identity, retrieval date, and stated rights information. Generated records retain their source identity and ordinal so an individual claim can be traced to its original context.

Original source files reside in `archive/`; source registers in `sources/`; and reproducible transformations in `generated/`. Curated corrections will use separate records rather than changing the evidence archive.

## First collection: Libretro and No-Intro

The current collection comes from the [Libretro Database](https://github.com/libretro/libretro-database), using the `metadat/no-intro` DAT files derived from the work of [No-Intro](https://datomatic.no-intro.org/).

- **Repository revision:** `fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90`
- **DAT header version:** `2026.08.01`
- **Collection date:** 2026-10-08 UTC
- **Declared Libretro repository license:** [Creative Commons Attribution-ShareAlike 4.0](https://creativecommons.org/licenses/by-sa/4.0/), per the [upstream license file](https://github.com/libretro/libretro-database/blob/fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90/LICENSE)
- **File-level source identities:** [`sources/libretro-no-intro.json`](../sources/libretro-no-intro.json)

Additional [Libretro field metadata DATs](../sources/libretro-enrichment.json) supply developer, publisher, release-year, release-month, genre, franchise, serial, ESRB rating, player-count, and rumble-support claims. Each imported claim retains its original file, Git blob, ordinal, revision, and parsed source fields. Consumers receive those locators and the enclosing source identity without needing the original archive at runtime. Both Libretro contributors and upstream No-Intro contributors are credited. The repository-level license statement is not automatically proof that every third-party component, description, or media asset is covered by the same terms. Source-specific rights and permitted reuse are assessed before expanding the archive.

The current JSON indexes are transformations of the DAT inputs. Attribution and ShareAlike obligations associated with eligible CC BY-SA material apply to redistributed adaptations. Separately sourced descriptions and images require their own rights assessment.

## Evidence quality

An imported name, date, serial, or fingerprint is attributed to its source; importing it does not independently verify it. Two providers may disagree, or may be describing different releases of the same work. Such differences remain visible until supported curation resolves them.

Future curated assertions will record their evidence and decision basis. Lookup results from the current exports are specifically **source fingerprint associations**, not authentication certificates or verified work identities.

## Integrity

The [source register](../sources/libretro-no-intro.json) includes each original DAT's Git blob SHA. The [catalog manifest](../generated/v1/catalog.json) records those identities alongside the generated JSON blob identities and record counts. The [verification tool](../tools/verify_catalog.py) reproduces the exports and checks all registered identities.

See [importing and validation](IMPORTING.md) for the rebuild procedure and [source evaluation](SOURCE-STRATEGY.md) for prospective providers.
