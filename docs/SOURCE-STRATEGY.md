# Metadata source strategy

*Research status: 2026-10-09.*

The original pinned No-Intro-derived accession covers ten Nintendo and Sega systems. A separate [bulk accession](BULK-EXPANSION.md) now includes 65 additional console/handheld sources and 279 additional bibliographic DATs at the same pinned Libretro revision. An independently sourced [Wikidata CC0 accession](WIKIDATA.md) has now captured 15,868 item/platform observations and 29,333 literal publication-date claims on 16 declared platform mappings. Exact title comparisons remain review candidates, not accepted identities. Bibliographic completeness requires different kinds of evidence: publication history, localizations, publisher and developer credits, alternate titles, and edition relationships. New providers are assessed on both data quality and permitted redistribution.

## Candidate sources

| Provider | Relevant metadata | Reuse considerations | Status |
| --- | --- | --- | --- |
| [Libretro Database](https://github.com/libretro/libretro-database) / [No-Intro](https://datomatic.no-intro.org/) | Cartridge titles, serials, regions, revisions and CRC32/MD5/SHA-1 fingerprints | Libretro declares CC BY-SA 4.0; original contributors and third-party content require attribution and source-specific review | **Imported:** 75 identification DATs and 367 bibliographic DATs across original and bulk-expanded collections |
| [Wikidata structured data](https://www.wikidata.org/wiki/Wikidata:Licensing) | Entity QIDs, console platform P400, English item labels and publication dates P577 | Structured items and statements declared CC0; underlying statements still need verification | **Imported:** 16 platform-wide batches with immutable raw query snapshots, 8,971 conservative correspondence candidates |
| [Redump](https://wiki.redump.info/Redump) | Disc identifiers, media revisions and fingerprints | Publicly accessible reference material; bulk redistribution rights are not established by this assessment | Research candidate |
| [GameTDB](https://www.gametdb.com/Main/FAQ) | Nintendo release identifiers, labels and art references | Terms differentiate software use, site reuse and artwork; clarification is needed for redistribution in this repository | Permission review |
| [MobyGames API](https://www.mobygames.com/api/subscribe/) | Publisher/developer credits, release history, platforms and editions | API terms and attribution requirements constrain redistribution and repackaging | Rights review before import |
| [ScreenScraper](https://www.screenscraper.fr/webapi2.php) | Localized titles, platform records and media references | API access, rate limits and developer/application authorizations apply; metadata and image rights need separate review | Authorization review |
| [TheGamesDB](https://api.thegamesdb.net/) | Titles, companies, release dates and descriptions | Redistribution permission and API terms need further review | Research candidate |
| [OpenVGDB](https://github.com/OpenVGDB/OpenVGDB/issues/43) | Game and ROM-metadata cross-references | Public reuse license remains insufficiently clear from the material reviewed | Rights review |

This table records *research leads*, not approved import sources. The specific terms and source versions will be rechecked at accession time.

## Selection criteria

A useful upstream collection should provide:

- Clear authorship and stable, citable record identities.
- Coverage of fields missing from the existing fingerprint archive.
- A reliable update history or immutable downloadable snapshots.
- Provenance sufficient to distinguish claims from independently checked facts.
- Permitted access, transformation, attribution, and redistribution under stated terms.
- Identifiers or correspondence evidence that support conservative reconciliation.

Public availability and an available API are different from permission to publish an independent database. Metadata licenses and image/media rights are evaluated separately.

## Order of work

**First, reliable identity evidence.** Maintain fidelity to imported source records, validate exact byte domains, and make collisions or uncertain joins visible.

**Second, bibliographic enrichment.** Extend the existing Libretro company, date, and genre claims with localized titles, more precise release histories, and independent corroboration where permitted.

**Third, canonical curation.** Resolve sources into stable work, release, and build entities with explicit supporting evidence and a record of unresolved disagreements.

**Finally, media references.** Develop an asset-reference layer once the provenance and rights for each asset category are defined.

Provider approvals and actual snapshot identities are maintained in the [source register](../sources/), rather than inferred from this research matrix.
