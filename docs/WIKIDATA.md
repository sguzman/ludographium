# Independent Wikidata game-metadata source

Wikidata is a separate, CC0-licensed source of structured game metadata. Its source statements are **not treated as authoritative identity proof** and are not assumed to have originated independently of every other upstream contributor. Unlike the Libretro identification and field-DAT imports, it provides globally resolvable item identifiers, platform associations and publication-date observations.

The [official Wikidata licensing policy](https://www.wikidata.org/wiki/Wikidata:Licensing) places structured item and property data under CC0. No Wikipedia article prose, artwork, game files, cover images, or third-party descriptions are copied.

## Verified first accession

The first completed source capture on **2026-10-09** includes **16 platform mappings, 15,868 original Wikidata item/platform observations, 29,333 literal publication-date statements, 8,971 source-title candidate links, and 8,908 console source observations with a candidate**. Among the candidate links, **126** were explicitly marked ambiguous rather than resolved.

[Snapshot lock and source checksums](../sources/wikidata-accession-v1.json) · [Successful capture, verification and reconciliation](https://github.com/sguzman/ludographium/actions/runs/37968964983) · [Published `data-v1.6.0` release](https://github.com/sguzman/ludographium/releases/tag/data-v1.6.0)

The [published Wikidata-enriched SQLite database](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-data-v1.6.0.sqlite) retained all **117,145** Libretro source observations and **167,640** attributed field claims unchanged. It adds independent Wikidata entities, dates, exact query-response evidence and noncanonical title candidates.

## Additional independently sourced console coverage

A separate, immutable
[platform expansion register](../sources/wikidata-platform-expansion-v1.json)
adds three already accessioned Libretro console collections to the Wikidata
CC0 source universe: Atari 7800 (Q753600), PlayStation Portable (Q170325)
and PlayStation Vita (Q188808). This mapping does **not** imply that all
Libretro source records correspond to a Wikidata item.

The [original source captures](../data/wikidata/platform-expansion-v1/)
retain 3,888 raw game source rows, 2,254 distinct per-platform item QIDs,
3,736 English-label bindings, and 3,699 literal publication-date bindings.
The five additional PlayStation Vita P577 RDF URI bindings are retained
without converting those nonliteral values into historical dates.

Every partition preserves the exact query, response, original JSONL
bindings, SHA-256 hashes and collection timestamp. The Rust
`--wikidata-expanded` CLI independently checks source bytes, each
response/JSONL row, platform QID, and date binding kind. It provides
read-only, bounded title and QID lookup with no network requirement.

This is a separate source accession, not a refresh or silent rewrite of
the preceding 16-platform baseline, and no canonical work, release, port,
edition or Libretro identity is inferred.

The independent source records are additionally comparable with the original
Atari 7800, PSP and Vita Libretro DAT observations using **same-platform
conservative exact title keys**:

```sh
cargo run --locked -- --wikidata-expanded-candidates --platform all --limit 10
```

This emits noncanonical correspondence candidates only, with original DAT
source ordinals and Git hashes, pinned Wikidata title row ordinals and SHA-256,
and explicit multi-QID ambiguity. Repeated Wikidata rows representing
distinct date claims are grouped under the same QID/title candidate without
discarding their original row ordinals. There is no automatic game identity,
edition, port, or regional-release assignment.

## Fifth additive platform expansion: six specialized systems

The independent [v5 platform register](../sources/wikidata-platform-expansion-v5.json)
records source queries for Casio Loopy, Casio PV-1000, Watara Supervision,
NEC SuperGrafx, Sega Pico, and Nintendo Satellaview.

The [six original source snapshots](../data/wikidata/platform-expansion-v5/)
preserve **35 response rows**, **22 per-platform game QIDs**, and
**34 literal publication-date bindings**. Importantly, Casio Loopy returned
**zero** results under the explicitly selected direct P31 video game and
P400 Casio Loopy query. Its original empty response, empty JSONL file,
query, byte counts and SHA-256 are preserved rather than silently omitted.
This establishes only *query-specific noncoverage at the capture time*,
not that Wikidata or Casio Loopy lacks games.

Rust's v5 source reader accepts exactly attributable zero-row partitions
while independently validating the original response and manifest.
All six platform source scopes remain visible and searchable offline:

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v5 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v5 --platform casioloopy
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v5 --platform all --limit 5
```

The [v5 title correspondence audit](../reports/wikidata-expanded-platform-v5-title-review-v1.json)
recorded **10 noncanonical title candidate links** and **zero ambiguous
links** across the six scopes. Casio Loopy and Satellaview had no exact
title correspondences under this matching rule. These counts neither
validate identities nor establish that their full game catalog is absent.

The matched source-title pairs remain noncanonical evidence, with no
inferred work, release or media identities.

## Fourth additive platform expansion: six legacy systems

A separate [v4 console-source register](../sources/wikidata-platform-expansion-v4.json)
records original Wikidata platform mappings for Atari 5200, ColecoVision,
GCE Vectrex, Mattel Intellivision, Magnavox Odyssey 2, and Nintendo Pokémon
Mini. These were previously uncovered within the pinned Libretro collections.

The [six immutable P400 source partitions](../data/wikidata/platform-expansion-v4/)
contain **482 original response rows**, **356 item/platform QID observations**
and **425 literal publication-date assertions**, with no nonliteral P577
bindings. Each has the original SPARQL request, full response, exact JSONL
source text, SHA-256 manifests and collection timestamp. Earlier platform
expansions remain unchanged.

The Rust reader verifies source bytes and can list the original evidence or
review same-platform source-title candidates without assigning identities:

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v4 --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v4 --platform all --limit 5
```

The [v4 review report](../reports/wikidata-expanded-platform-v4-title-review-v1.json)
records **238 links**, with no multiple-QID title ambiguity.
A title correspondence is **review evidence only**, not a source-confirmed
work, region, edition, port, release or media identity.

## Third additive platform expansion: six more consoles

The separately pinned [v3 platform register](../sources/wikidata-platform-expansion-v3.json)
extends original CC0 source coverage to Famicom Disk System, Neo Geo Pocket,
Neo Geo Pocket Color, SG-1000, Sega 32X, and PC Engine/TurboGrafx-16.

The [six original source partitions](../data/wikidata/platform-expansion-v3/)
retain **1,148 raw query response rows**, **655 distinct per-platform QIDs**,
and **1,114 literal P577 publication-date statements**, with no nonliteral
publication bindings in this batch. Every capture preserves the actual
query, JSON response, original JSONL rows, SHA-256 hashes, and timestamp.
No existing source observations were rewritten.

Both the Rust original evidence lookup and conservative same-platform
Libretro title-candidate review support the new source version:

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v3 --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v3 --platform all --limit 5
```

The [v3 review report](../reports/wikidata-expanded-platform-v3-title-review-v1.json)
records **290 links** (288 Libretro records; four ambiguous links).
As with v1 and v2, a candidate is title correspondence evidence, not
a canonical work, region, edition, port, release or media relationship.

## Second additive platform expansion: Atari and WonderSwan

The separate [v2 source register](../sources/wikidata-platform-expansion-v2.json)
adds Atari Jaguar (Q650601), Atari Lynx (Q753657), WonderSwan (Q1065792)
and WonderSwan Color (Q1048035). The complete
[v2 raw source accession](../data/wikidata/platform-expansion-v2/)
preserves **305 original response rows, 206 item/platform QID observations
and 282 literal publication-date bindings**, each with independently hashed
query/response/JSONL sources.

The Rust hash verifier and same-platform conservative title-candidate reader
support both immutable expansions. `--expansion-source v1` remains the default;
v2 is an explicit, read-only selection:

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v2 --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v2 --platform all --limit 5
```

A title candidate is review evidence, never an accepted work, edition,
regional-release or Libretro media identity.

## Committed text corpus

The primary imported Wikidata data now lives in [16 per-platform JSONL files](../data/wikidata/v1/) and a [plain-text provenance manifest](../data/wikidata/v1/manifest.json), approximately **4.2 MB total in Git**. Each item retains its Wikidata QID, English label and captured date statements. `tools/export_wikidata_text.py` deterministically rebuilds and verifies these files from the pinned original JSON source snapshot. SQLite is an optional locally generated search index, not the committed data format. See the [data-format policy](DATA-FORMATS.md).

## Second independent CC0 property accession — 2026-10-11

The repository now also preserves **47,144 original Wikidata structured property
statements across all 16 existing platform scopes**, covering **14,759
game-item/platform observations**. This is separate from and does not rewrite
the prior immutable 15,868-item/29,333-date Wikidata snapshot.

This new [plain-text source accession](../data/wikidata/properties-v1/) collects
original statements for **P178 (developer), P123 (publisher), and P136 (genre)**.
Each platform directory preserves the complete original SPARQL JSON response,
exact query text, one original binding per JSONL line, and a checksum/capture
manifest. **Three non-entity RDF values** are retained literally instead of
being cast into QIDs or silently discarded.

The source was acquired in verified platform-scoped batches through
[GitHub Actions](../.github/workflows/wikidata-properties.yml). Existing pinned
platform captures are checksum-verified and never implicitly overwritten on a
rerun. A live Wikidata query is not a stable source revision; the independently
captured bytes and their per-platform SHA-256 digests are the reproducibility
boundary.

Rust verifies the raw response, JSONL row-by-row equivalence, source hashes,
platform registration, property scope, observation counts and source ordinals.
It can list statements offline or select one Wikidata game QID and property:

```sh
cargo run --locked -- --wikidata-properties --platform all --limit 5
cargo run --locked -- --wikidata-properties --platform atari2600 --qid Q379915 --property P178
```

A QID-valued developer/publisher/genre claim describes what Wikidata
currently asserted at collection time. **It does not resolve the organization's
identity, establish release-specific credits, authenticate Wikidata assertions,
or prove the game's correspondence to any Libretro media record**.
Exact same-platform title candidates remain separate review evidence.

## English labels for referenced company and genre QIDs

The third CC0 accession captures English labels for the distinct entity QIDs
referenced by the new P178/P123/P136 claims, using exact QID VALUES queries
rather than textual or fuzzy game-name matching.

- **2,768** distinct QID-valued references, all retained in a sorted plain-text
  inventory.
- **2,614** QIDs with captured English labels and **154** without one.
- **28** complete source query/response partitions (100 QIDs maximum each),
  including original per-item JSONL bindings and SHA-256 manifests.

[Preserved source snapshots](../data/wikidata/property-labels-v1/) and
[successful capture](https://github.com/sguzman/ludographium/actions/runs/38164894590).

The Rust reader checks SHA-256 and byte lengths for every pinned source file,
query/response/JSONL consistency, QID inventory, label language, exact
cross-references to the original property claims, and missing-label evidence.

Use the opt-in `--with-entity-labels` flag to include separately attributed
label evidence alongside original property claims:

```sh
cargo run --locked -- --wikidata-properties --with-entity-labels --platform all --limit 5
cargo run --locked -- --wikidata-properties --with-entity-labels --platform atari2600 --qid Q379915
```

The entity label is a source claim about a QID, not a canonical developer,
publisher, genre, or game identity. Missing labels remain missing.

## Bulk accession

The [source register](../sources/wikidata-v1.json) declares 16 Wikidata platform IDs across the existing 75-platform console corpus. It includes original ten-system families and selected additional Atari, Nintendo, Xbox and PlayStation collections.

The [independent-source acquisition tool](../tools/wikidata_source.py) issues one *whole-platform* query per declared hardware ID. It does not issue a request for each game, and it does not do regex/fuzzy scraping of titles.

Each query selects Wikidata entities asserted to be video games (`P31:Q7889`) on the declared platform (`P400:Q...`), requesting English item labels and publication dates (`P577`). The raw JSON responses, exact SPARQL query text, SHA-256 digests, timestamp, row count, and originating platform QID are all retained. Entity labels and publication-date facts are source claims; dates without territory qualifiers are **not** silently converted into region-specific release dates.

The [Wikidata Query Service documentation](https://www.wikidata.org/wiki/Wikidata:Data_access) advises against using broad regex-based search or large, expensive queries; the [query service manual](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual) describes timeouts and rate limits. This importer partitions by platform, sends a meaningful User-Agent, accesses sequentially with delay, retries retryable responses, limits response bytes, and **rejects** result sets that reach the configured row ceiling. A failed or truncated snapshot is not considered a completed accession.

A live Wikidata query endpoint is not an immutable upstream revision. Reproducibility begins when the **complete raw query results** have been captured, checksummed, and stored as a snapshot. The resulting SQLite database can be regenerated from exactly that snapshot and the immutable expanded `data-v1.5.0` source corpus. Re-running the live query later may yield different source content.

## Rust-native, offline source observations

The Rust CLI reads the **16 Git-committed CC0 JSONL collections** directly. It cross-checks the source register and the checked-in manifest, verifies each accessed file's byte length and SHA-256, preserves QIDs and every literal publication-date observation, and never generates a SQLite database or requires Python:

```sh
cargo run --locked -- --wikidata-text --platform atari2600 --qid Q379915
cargo run --locked -- --wikidata-text --platform all --title "Adventure" --limit 5
cargo run --locked -- --wikidata-text --platform gb --limit 10
```

The returned original observations include the declared CC0 license, pinned source revision, exact JSONL path, source SHA-256, capture timestamp and original snapshot SHA-256. `--qid` is an exact Wikidata-item identifier lookup; `--title` searches the source's English labels without attempting a Libretro join. A queryless listing is bounded by `--limit`. Historical SQLite correspondence candidates remain separate and are not promoted to canonical identities by this reader. The full-corpus Rust test checks **15,868 item observations** and **29,333 date claims**.

## Rust-native correspondence review

The independent Wikidata and Libretro text sources can now be reconciled by a
**read-only Rust comparison** without Python, SQLite, network access, or altering
any source observation:

```sh
cargo run --locked -- --wikidata-candidates --platform all --limit 5
cargo run --locked -- --wikidata-candidates --platform atari2600 --qid Q379915
cargo run --locked -- --wikidata-candidates --platform snes --title "Mario" --limit 10
```

The comparison only accepts a shared declared platform and equal conservative
title keys. It strips recognized *trailing* region, language and revision tags
while retaining significant parentheses, accents, punctuation and original
titles. Every candidate carries its source ordinal, original DAT source hash,
Wikidata QID, label and pinned JSONL hash. If more than one QID shares the
platform/title key, all resulting links are explicitly
`ambiguous_wikidata_title`, not automatically merged.

The full-corpus aggregation runs **before** applying the displayed result
limit and reports all candidate links, distinct source observations with
candidates, and ambiguous links. This is a deterministic **review index**,
not a canonical game identity or a claim of independent factual confirmation.

## Attributed publication-year evidence comparison

Use `--compare-years` with the Rust title-candidate search to compare the
source's literal year assertions without fabricating agreement or declaring
different years to be historical errors:

```sh
cargo run --locked -- --wikidata-candidates --compare-years --platform all --limit 5
cargo run --locked -- --wikidata-candidates --compare-years --platform atari2600 --qid Q379915
```

The opt-in audit reads the pinned original identification DATs, all selected
original bibliographic field DATs, and original CC0 Wikidata JSONL files. It
includes identification-record `releaseyear` fields and **only conservatively
attached** `releaseyear` bibliographic assertions. Every retained Libretro
claim includes its source kind, original raw year, DAT path, Git blob SHA and
source ordinal. Wikidata date records keep raw values, RDF kind and datatype;
URI-valued or unparseable bindings are never silently interpreted as years.

Status categories distinguish `overlapping_observed_years`,
`different_observed_years`, `libretro_year_missing`,
`wikidata_literal_year_missing` and `both_years_missing`.
Whole-corpus counts are computed before the requested result limit.
A difference can reflect a release territory, platform port, prototype, version
or incomplete Wikidata qualifiers, **not necessarily a source error**.
Cross-provider title matches and matching years remain review evidence,
not independently verified work or regional-release identities.

## Original GameFAQs platform qualifier evidence

The original [GameFAQs P4769 statement-level source accession](../data/wikidata/gamefaqs-qualifiers-v1/)
preserves **23,623 statement observations** across 16 platforms. Unlike
a direct P4769 identifier query, it captures each exact Wikidata statement
URI and its optional P400 **statement qualifier**. All query, response,
JSONL and manifest hashes are pinned. No qualifier is inferred for unqualified
statements.

A [reproducible review report](../reports/wikidata-gamefaqs-platform-qualifier-review-v1.json)
measures how those source qualifiers relate to the *item-level* P400
platform used to select each partition:

| Source observation type | Rows |
| --- | ---: |
| Explicit statement qualifier equals partition's platform | 9,042 |
| Explicit statement qualifier names another platform | 14,084 |
| Missing statement-level platform qualifier | 497 |
| **Original source observation rows** | **23,623** |

The same source item may belong to multiple platforms, so a statement
qualifier naming another platform is **not necessarily an error**. The
correct interpretation is that the *game-item platform scope* and the
*external-ID statement's platform qualifier* are distinct kinds of evidence.

The Rust reader independently verifies full query/response/JSONL fidelity,
the raw statement URIs and qualifier counts. It exposes a bounded offline
lookup by exact original GameFAQs value and/or Wikidata item QID:

```sh
cargo run --locked -- --wikidata-gamefaqs-qualifiers --platform all --limit 5
cargo run --locked -- --wikidata-gamefaqs-qualifiers --platform atari2600 --qid Q1014915 --external-id 579332
```

This is original CC0 Wikidata evidence only, **not GameFAQs API verification**
or an accepted release/edition identity.

## Independent third-party game authority ID source claims

The fourth structured-data source expansion captures **65,182 original Wikidata
third-party identifier claims** for 13,609 game-item/platform observations
across all 16 previously declared platforms. Original [query responses,
literal identifier strings, JSONL and SHA-256 manifests](../data/wikidata/authority-ids-v1/)
are preserved without contacting or copying the third-party databases.

| Property | Wikidata claim meaning | Source claims |
| --- | --- | ---: |
| P11688 | MobyGames game ID (numeric) | 16,800 |
| P1933 | MobyGames game ID (legacy slug) | 15,725 |
| P4769 | GameFAQs game ID | 23,606 |
| P2816 | HowLongToBeat ID | 6,718 |
| P2864 | OpenCritic ID | 1,214 |
| P2451 | MAME ROM name | 620 |
| P4857 | AtariAge ID | 427 |
| P2606 | PlayStation ID | 59 |
| P1712 | Metacritic ID | 13 |

The former MobyGames slug (P1933) and numeric ID (P11688) are different
identifier namespaces. A GameFAQs ID can be platform-scoped while a
MobyGames numeric ID can describe a broader game entity; these source
assertions are never silently equated or promoted into definitive release
identities.

Offline Rust lookup verifies all pinned source files and exposes exact
provider-qualified reverse lookup and source QID filtering:

```sh
cargo run --locked -- --wikidata-authority-ids --platform all --limit 5
cargo run --locked -- --wikidata-authority-ids --platform all --property P4769 --limit 5
cargo run --locked -- --wikidata-authority-ids --platform all --property P11688 --external-id 39536
```

The matching scope is **exact identifier string plus explicit property**.
The original source game QID, platform, ordinal, query, response and text
hashes stay attached. Different QIDs sharing one claimed external identifier
are review leads; there is no assertion that the external provider actually
assigns that identifier to the linked game.

## Third Wikidata property expansion: series, titles, game modes and external IDs

A further **92,621 original source statements** across all **16 registered
platforms** and **14,772 item/platform observations** are pinned in
[original plain-text SPARQL captures](../data/wikidata/relations-v1/).

| Wikidata property | Claim meaning | Captured source statements |
| --- | --- | ---: |
| P179 | Part of series | 6,232 |
| P404 | Game mode | 18,199 |
| P407 | Language of work or name | 14,551 |
| P495 | Country of origin | 13,180 |
| P437 | Distribution format | 16,493 |
| P750 | Distributed by | 15,152 |
| P1476 | Published title (including language tags) | 5,532 |
| P1733 | Steam application ID | 2,624 |
| P2725 | GOG application ID | 658 |

Each original platform directory preserves the exact SPARQL query, full
untruncated JSON response, one raw RDF binding per JSONL line and a
SHA-256/source-byte manifest. All properties remain raw source statements,
including language tags and string-valued third-party identifiers. Large
query partitions used an increased, explicitly recorded 30,000-row ceiling;
capturing exactly the limit is considered incomplete, never accessioned.

The Rust CLI hash-checks every source file and compares the original
response to JSONL line by line, verifies property and RDF-type totals and
supports read-only bounded queries with no Python/SQLite/network dependency:

```sh
cargo run --locked -- --wikidata-relations --platform all --limit 5
cargo run --locked -- --wikidata-relations --platform all --property P1733 --limit 5
cargo run --locked -- --wikidata-relations --platform atari2600 --qid Q100701966
```

P1733/P2725 strings are externally assigned **identifier claims in
Wikidata**, not independently verified Steam/GOG records. Series,
language, game mode and distribution claims likewise do not establish a
canonical work, release, edition or geographic availability. No external
provider contents were scraped or redistributed.

## Independent labels for new relation QIDs

A fourth independent Wikidata CC0 source capture pins **1,837 referenced
entity QIDs** with **1,639 English labels** in 19 original SPARQL query and
response batches. The **198 unlabeled references** retain their original QID
and source evidence without invented names.

[Original source evidence](../data/wikidata/relation-labels-v1/) is captured
and checksummed independently of the source relation statements.
[Acquisition succeeded](https://github.com/sguzman/ludographium/actions/runs/38169376017).

The Rust source reader validates every original query, response, JSONL
binding, SHA-256 digest and exact inventory of relation-valued QIDs. Entity
English labels are shown as **separate evidence**, not substituted for raw
RDF values or treated as authenticated series, country, language, distributor,
or format identities:

```sh
cargo run --locked -- --wikidata-relations --with-entity-labels --platform all --limit 5
cargo run --locked -- --wikidata-items --platform atari2600 --qid Q100701966
```

## Original multilingual labels and alternate game titles

A fourth independent CC0 Wikidata accession contains **124,690 language-tagged
source name observations** over all **16 platform collections** and 15,731
item/platform observations: `rdfs:label` (81,593 names) and
`skos:altLabel` (43,097 alternate-name assertions).

The pinned source scope includes `en`, `ja`, `es`, `zh`, `fr`,
`de`, `it`, `ko`, `ar` and `pt`, including available subtags. Exactly
**25 language-tag variants** appeared in the preserved originals, including
`es-419`, `pt-br`, `zh-hans`, `zh-hant` and `en-gb`.
The source contains 16,606 Chinese-, 12,991 Japanese- and 10,937
Spanish-tagged observations.

The [original SPARQL queries and complete source responses](../data/wikidata/localized-titles-v1/)
are pinned per platform, with SHA-256 and size manifests. The Rust reader
checks every source response against each JSONL row, all language-tag and
name-kind totals, exact platform mapping and source file hashes.

```sh
cargo run --locked -- --wikidata-localized-titles --platform all --limit 5
cargo run --locked -- --wikidata-localized-titles --platform snes --language es --limit 5
cargo run --locked -- --wikidata-localized-titles --platform all --title "Mario" --limit 5
```

The language filter matches an exact language prefix and its subtags,
without changing returned source tags. These are attributed names, **not
confirmed canonical titles for a territory or a game edition**. Different
aliases do not establish independent work or release identities.

## Exact reverse lookup for external ID source strings

The Rust source query can now start from a literal Steam (P1733) or GOG
(P2725) ID and find every original QID/platform attribution without
interpreting the identifier as a number or claiming game/release identity.
The result reports the **full number of distinct QIDs and platforms before
limiting displayed source rows**, to prevent hidden multi-QID ambiguity.

```sh
cargo run --locked -- --wikidata-relations --platform all --external-id 15750 --property P1733
```

This identifier appears under **two distinct source game QIDs** in the
captured Wikidata evidence. Such assignments remain explicit review leads,
not automatically adjudicated errors or a basis to merge game identities.

## Cross-platform Steam/GOG identifier ambiguity audit

The [source-derived external-ID report](../reports/wikidata-external-identifier-review-v1.json)
is generated by the [pinned-source audit workflow](../.github/workflows/review-external-ids.yml).
It inventories every P1733 and P2725 source claim, retaining platform, QID,
original identifier string and source path for ambiguous assignments.

| Evidence category | Count |
| --- | ---: |
| Original Steam/GOG identifier claims | 3,282 |
| Distinct provider-qualified identifier strings | 1,972 |
| Identifier strings appearing across multiple console platform captures | 911 |
| Provider-qualified IDs attached to more than one distinct game QID | 10 |
| Distinct Wikidata game QIDs carrying both Steam and GOG claims | 358 |

The **10 multiply assigned provider identifiers** are review leads, not
automatically erroneous external IDs, merged game identities or accepted
cross-provider correspondences. The **911 cross-platform repeats** often
describe one Wikidata game item on multiple consoles; they are not duplicate
errors. Source claims were **not verified against Steam or GOG's own data**,
and these distributions cannot independently establish a false-positive rate.

## Unified read-only Wikidata game-item observations

The Rust `--wikidata-items` mode constructs an exact-QID, per-platform,
**noncanonical source projection** from all five independently pinned data captures:
original English game labels and date statements; original developer,
publisher and genre claims; separately captured company/genre entity
English labels; original series/language/distribution/title/Steam-GOG source
claims; and the new source-only MobyGames/GameFAQs/HowLongToBeat/OpenCritic/
MAME/AtariAge/PlayStation/Metacritic identifier claims. Source provenance
and capture boundaries remain visible.

```sh
cargo run --locked -- --wikidata-items --platform all --limit 10
cargo run --locked -- --wikidata-items --platform atari2600 --qid Q379915
cargo run --locked -- --wikidata-items --platform snes --title "Mario" --limit 10
```

Per-item `source_membership` lists exactly which independently captured
source families contain the same platform/QID. The
`source_membership_counts` histogram distinguishes all observed combinations,
rather than claiming a record is "source only" when it also appears in
another accession. The summary's "source only" counters now denote
**strictly exclusive** source membership.

The union preserves and counts records found only in the original title/date
capture, only in the company/genre property capture, or only in the relation
capture, as well as records appearing in multiple snapshots. Every relation
claim retains its own original query response and binding hashes.
No Libretro work/media identity or source correction is inferred.
The reader requires no SQLite, Python, or network.

## Independent exact-title review from localized names and aliases

An opt-in Rust comparison separately indexes the **124,690 original
language-tagged Wikidata labels and aliases** and matches them against
original Libretro game title observations on the **same platform** by
strict conservative title-key equality. It preserves every contributing
original label/alias claim, language tag, predicate, source ordinal and
SHA-256 digest. Multiple labels from one QID are grouped into one candidate
pair; competing QIDs remain ambiguous instead of auto-resolved.

```sh
cargo run --locked -- --wikidata-localized-candidates --platform all --limit 10
cargo run --locked -- --wikidata-localized-candidates --platform atari2600 --qid Q379915
```

Summary counts include distinct source-occurrence-to-QID pairs, ambiguous
pairs and pairs **not already present in the original English-label
candidate set**. Those additions are review leads, *not* a validated increase
in correct game identities. No fuzzy matching or translation is performed;
matching the same name across language tags cannot establish a region,
locale-specific edition, media hash, or work identity. The historical
8,971 English-label candidate baseline and its audits remain unchanged.

## Cross-source developer and publisher credit review

The Rust candidate pipeline can now compare **original Libretro developer and
publisher text claims** with the independent Wikidata P178/P123 value QIDs and
their separately captured English labels. The comparison is only applied to
the previously declared same-platform title candidates, retaining the
original source occurrence, QID ambiguity and both providers' hashes.

```sh
cargo run --locked -- --wikidata-candidates --compare-credits --platform all --limit 10
cargo run --locked -- --wikidata-candidates --compare-credits --platform atari2600 --qid Q379915
```

Every one of the **8,971 existing title candidates** receives a separate
developer and publisher review classification (17,942 review comparisons).
Statuses distinguish identical observed names, different names, missing
Libretro claims, missing Wikidata credits, and missing Wikidata English labels.
Case and whitespace are normalized for name comparison, but punctuation,
accents and compound company names are **not** silently merged.

A matching organization name is additional evidence, **not proof** of the
game work identity or definitive release-specific credit. A difference may
represent developer divisions, regional publishers, collaborative credits,
different releases, incomplete claims, or source errors. Original raw values
remain visible; no company IDs or canonical work relationships are created.

## Published cross-provider review counts

The [reproducible source-evidence report](../reports/wikidata-cross-provider-review-v1.json)
is generated by a [Rust-only source-audit workflow](../.github/workflows/review-source-evidence.yml)
from the committed original DATs and Wikidata source snapshots. Each of the
8,971 title candidates has two credit comparisons and one publication-year
comparison. These are source-claim observations, **not validated work matches**.

| Source review category | Developer | Publisher | Release year |
| --- | ---: | ---: | ---: |
| Identical observed names / overlapping observed years | 1,355 | 1,604 | 2,483 |
| Different observed names / different years | 2,130 | 1,530 | 584 |
| Missing/incomplete source evidence | 5,486 | 5,837 | 5,904 |
| **All noncanonical candidate links** | **8,971** | **8,971** | **8,971** |

The missing/incomplete category includes both-sources-missing claims,
one-provider-missing claims and source references lacking English company
labels. Neither agreement nor disagreement alone measures identity quality.
**An empirical false-positive rate cannot be computed without independently
adjudicated ground truth.** Source disagreement is a useful review target;
it is not automatically a source error or a game-identity rejection.

## Conservative correspondence

The [bulk reconciliation tool](../tools/reconcile_wikidata.py) adds independent source evidence to an existing offline expanded SQLite database. It adds:

| Relation | Purpose |
| --- | --- |
| `wikidata_queries` | Original query, timestamp, raw source response, SHA and platform QID |
| `wikidata_items` | Every returned Wikidata QID and English label, including unmatched records |
| `wikidata_dates` | Each distinct source publication-date statement and RDF datatype |
| `wikidata_link_candidates` | Same-platform, exact title-key *review candidate*, with source ordinal and QID |
| `wikidata_candidate_detail` | Queryable join showing titles, QIDs and source locators |

Only explicit trailing source tags (such as `(USA)`, `(World)`, `(Rev 1)` or a recognized language tag) are stripped from identification titles for candidate comparison. The importer retains punctuation, accents, spelling and significant title parentheses. No phonetic, edit-distance, or translated-name equivalence is inferred.

When multiple Wikidata QIDs share a title key on the same platform, every potential link is retained as `ambiguous_wikidata_title`; none is promoted to a resolved identity. Even a single QID match is labeled `title_candidate`, **never** "verified identity." Every imported observation and previously attributed field claim is preserved. Original source data are not rewritten.

This is a bulk correspondence pipeline and a pool of independently checkable claims; it does not yet create Wikidata-backed canonical works, releases, or media builds.

## Reproducible offline workflow

The [GitHub Actions accession](../.github/workflows/wikidata.yml) uses a normal source-level batch:

```sh
python3 tools/wikidata_source.py --fetch --snapshot /tmp/wikidata-snapshot.json
python3 tools/wikidata_source.py --verify --snapshot /tmp/wikidata-snapshot.json

python3 tools/reconcile_wikidata.py --build \
  --from-db /path/to/verified-data-v1.5.0-expanded.sqlite \
  --snapshot /tmp/wikidata-snapshot.json \
  --db /tmp/ludographium-with-wikidata.sqlite

python3 tools/reconcile_wikidata.py --verify \
  --snapshot /tmp/wikidata-snapshot.json \
  --db /tmp/ludographium-with-wikidata.sqlite
```

The underlying expanded database is pinned to its published SHA-256. Source query bodies and results have independent digests. CI asserts unchanged original identification and bibliographic record counts, performs SQLite and foreign-key checks, verifies query evidence, tests ambiguous cases using synthetic fixtures, and uploads the resulting snapshot plus complete offline enriched database.

The first successful batch covers 16 explicitly mapped platform categories, not all 75. Other platforms require grounded Wikidata platform IDs and should be added in **batches**, with coverage and ambiguous-candidate statistics, never per-game data entry.

## Sixth verified platform cohort (v6)

The pinned [v6 source register](../sources/wikidata-platform-expansion-v6.json)
and [original source snapshots](../data/wikidata/platform-expansion-v6/)
add six independently captured P31 video-game/P400 platform query scopes:
Sega Game Gear, New Nintendo 3DS, Nintendo DSi, Nintendo 64DD,
Tiger Game.com and Fairchild Channel F. The capture contains **662 original
query rows** representing **309 distinct item/platform observations**,
**575 English-label-bearing rows**, **642 literal publication bindings**,
and **two nonliteral publication bindings**. These are source observations,
not verified releases or distinct game works.

The Tiger Game.com query returned **zero** rows. Its manifest, original
query, zero-binding JSON response, and empty JSONL evidence remain independently
hash-checked. This is a result for that precise query, not an assertion that
the platform had no games. New Nintendo 3DS has the two nonliteral publication
bindings; they are retained as RDF values rather than interpreted as dates.

The offline Rust reader and its bounded conservative title comparison
support `--expansion-source v6`, without overwriting earlier captures:

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v6 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v6 --platform gg --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v6 --platform all --limit 5
```

The title comparison exposes provisional review candidates only, preserving
source paths, original ordinals, QIDs, SHA-256 evidence, and ambiguity. Neither
the existence of an exact same-platform title nor the absence of returned
rows proves canonical work/release identity or platform-complete coverage.

## Seventh verified platform cohort (v7)

The independent [v7 source register](../sources/wikidata-platform-expansion-v7.json)
and [original query captures](../data/wikidata/platform-expansion-v7/)
cover six more Libretro source collections: Emerson Arcadia 2001,
Epoch Super Cassette Vision, GamePark GP32, Interton VC 4000,
RCA Studio II, and Sega Advanced Pico Beena.

The six hash-pinned P31/P400 Wikidata queries returned **20 original rows**
representing **14 per-platform item observations**, with **18 English-label
rows** and **20 literal P577 publication bindings**. No nonliteral publication
bindings were returned. The GP32 and Interton VC 4000 query scopes returned
**zero** rows and are separately pinned as verified noncoverage for those
queries, without implying anything about the consoles' actual game libraries.

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v7 --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v7 --platform all --limit 5
```

The original source records are immutable and independent of the prior six
cohorts. Source-label title review remains noncanonical; unknown dates,
unverified identities and unmatched source occurrences are not silently
resolved.

## Expanded independent developer, publisher and genre credits

The separate [19-platform credited-source accession](../data/wikidata/expanded-credits-v1/)
records **10,269 P178/P123/P136 statements**, representing **3,150
item/platform observations**. These are additional console scopes from
platform expansions v1 through v4, not a modification to the previous
sixteen-platform company/genre snapshot.

The [bulk acquisition workflow](../.github/workflows/wikidata-expanded-credits-v1.yml)
retains original query text, source response, complete per-binding JSONL
and individual SHA-256 digests. The offline Rust reader verifies
manifest values, platform scopes, statement RDF types and response-to-JSONL
equality before returning a record. It does not resolve game-work identities
or assign publisher/developer aliases.

```sh
cargo run --locked -- --wikidata-properties --expanded-credits --platform all --limit 5
cargo run --locked -- --wikidata-properties --expanded-credits --platform sonyplaystationvita --property P123 --limit 5
```

Expanded-source claims deliberately cannot use the original baseline's
`--with-entity-labels` option: the old English-label inventory was captured
for different source scopes and does not verify this cohort's complete
set of referenced company/genre entities. Unlabeled QIDs remain unlabeled
until separately sourced label evidence is available.

## Completed expanded-credit and relation acquisition across 37 additional scopes

The two [developer/publisher/genre claim batches](../data/wikidata/expanded-credits-v1/)
and [second-source cohort](../data/wikidata/expanded-credits-v2/) contain
**11,231 original P178/P123/P136 statements**. The first nineteen
platform-query partitions supply 10,269 statements (3,150 per-platform
item observations); the remaining eighteen supply 962 statements (312
item/platform observations). Empty results are retained as hash-pinned
query-specific noncoverage, not as assertions that the associated hardware
lacks games.

The independent [first relation cohort](../data/wikidata/expanded-relations-v1/)
and [second relation cohort](../data/wikidata/expanded-relations-v2/)
contain **20,460 original source statements**, comprising 18,999 and
1,461 bindings respectively. Both use the same nine-property scope as the
original sixteen-platform relation accession (P179, P404, P407, P495,
P437, P750, P1476, P1733, P2725). Taken together they contain 653
Steam (P1733) and 193 GOG (P2725) identifier assertions. Repeated
provider ID strings and cross-platform claims are **not** independently
authenticated external-provider records.

All four capture batches preserve their separate original query, response,
JSONL, manifest, platform QID, timestamps, and SHA-256 evidence. The Rust
reader rechecks those records before returning them. The CLI retains the
original baseline as the default and permits source-specific reads:

```sh
cargo run --locked -- --wikidata-properties --metadata-cohort expanded-v1 --platform all --limit 5
cargo run --locked -- --wikidata-properties --metadata-cohort expanded-v2 --platform all --limit 5
cargo run --locked -- --wikidata-relations --metadata-cohort expanded-v1 --platform all --limit 5
cargo run --locked -- --wikidata-relations --metadata-cohort expanded-v2 --platform all --limit 5
```

Expanded source partitions deliberately do not reuse the original
sixteen-platform entity-label inventory. Label provenance requires a
separate applicable acquisition; missing labels and ambiguous values are
left unresolved.

## Accuracy and source-rights boundaries

Wikidata's CC0 statements can support independently *attributed* comparisons. They are not automatically independent factual corroboration: Wikidata contributors may have consulted the same upstream references as Libretro contributors. Label correspondence alone has no power to authenticate media hashes, identify a regional edition, or establish that two products are the same canonical work.

The Libretro/No-Intro-derived metadata and their CC BY-SA attribution remain governed by their original notices; Wikidata's CC0 grant does not relicense third-party source data. The offline database includes neither game files nor copyrighted cover art.
