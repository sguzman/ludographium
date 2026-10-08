# Metadata source strategy (2026-10-08)

The initial No-Intro-derived accession is excellent for **image identification**, but it is not a complete bibliographic catalog. Richer work/release metadata requires other sources and, critically, separately evaluated reuse rights. Do not download everything merely because an API makes it possible.

| Provider | Potential value | Access/rights assessment | Current decision |
| --- | --- | --- | --- |
| [Libretro Database](https://github.com/libretro/libretro-database) / [No-Intro](https://datomatic.no-intro.org/) | Cartridge titles, regions, serials, revision hints, CRC32/MD5/SHA-1, occasional date fragments | Libretro repo declares CC BY-SA 4.0; original upstream authors must be credited; check third-party components separately | **First pinned source accession active** |
| [Redump](https://wiki.redump.info/Redump) | Optical media labels, versions, disc checksums and identifiers | Public informational database; a general redistribution license has **not** been established here | Research-only; no bulk mirror until rights review |
| [GameTDB](https://www.gametdb.com/Main/FAQ) | Nintendo platform game metadata, IDs, cover references | FAQ encourages use in software with a GameTDB link and contacting maintainers; explicitly says website reuse requires permission | Seek permission/clarification before redistributing its records in a public repository; art separately |
| [MobyGames API](https://www.mobygames.com/api/subscribe/) | Publishers, developers, dates, editions, platform bibliographic metadata | Subscription/API usage and attribution obligations; explicitly prohibits repackaging/reselling data | **Do not bulk-import or mirror** into Ludographium absent explicit permission |
| [ScreenScraper API](https://www.screenscraper.fr/webapi2.php) | Localized titles, media references, platform and game metadata | Requires developer credentials; free distributed applications or prior authorization; rate limits/quotas | No bulk mirror without project authorization and rights clarification |
| [TheGamesDB API](https://api.thegamesdb.net/) | Publishers, developers, platform descriptions and game dates | API endpoints exist, but redistribution terms require separate review | Candidate; no import until terms reviewed |
| [OpenVGDB](https://github.com/OpenVGDB/OpenVGDB/issues/43) | Large ROM/game metadata cross-reference | Public license ambiguity noted in an unresolved issue | Hold pending clear license |

## Acquisition priorities

1. **Fingerprint reliability:** finish source snapshot parity, explicit header/no-header byte-domain rules, collisions/ambiguity handling.
2. **Bibliographic enrichment:** source independently documented publisher, developer, original release dates and alternate/localized titles. Assert only what each provider actually supports.
3. **Canonical identities:** resolve competing claims with stable work/release/build IDs, documented decisions and unresolved links.
4. **Media:** point to licensed artwork only after asset-specific rights checks; image URLs alone are not permission to rehost.

## Import qualification

For each proposed source, first record authorship/maintainer, scope, update cadence, machine interface and access requirements, license/contract for bulk redistribution, attribution requirements, revision pinning capabilities, and whether raw mirrors are allowed. A service permitting queries from a free frontend does not necessarily permit rebuilding and republishing its entire database.

Avoid treating scraped website entries as public-domain facts without analyzing database rights and terms. **No dataset is approved solely because it is publicly viewable.**

Primary documentation and the source register, not this exploratory matrix alone, govern actual accessions.
