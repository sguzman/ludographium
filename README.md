# Ludographium

**A provenance-first catalog of console and handheld video games.**

Ludographium collects structured metadata about console games and their releases. Original sources remain attributable and unchanged; normalized indexes make the records useful to emulators, library managers, and research tools without depending on a live service.

It catalogs titles, versions, regions, publication facts, product identifiers, and media fingerprints. It is not a ROM archive, cheat collection, or gameplay ontology.

**Source data are plain text, not binary databases.** The [Wikidata accession is checked into Git as small per-platform JSONL files](data/wikidata/v1/); SQLite is only an optional derived offline index. See the [source-format policy](docs/DATA-FORMATS.md). The earlier SQLite Release assets remain available for backward compatibility, but new releases will not publish those large binary databases.

## CC0 MAME software-list bulk accession

A separate [source register](sources/mame-softlists-v1.json) pins **49
original console and handheld software-list XML files** to a single immutable
upstream MAME commit. The [acquisition tool](tools/acquire_mame_softlists.py)
and [workflow](.github/workflows/mame-softlists-v1.yml) verify per-file
CC0-1.0 headers, original XML structure, source bytes and SHA-256 checksums.
The [source-yield report](reports/mame-softlists-v1-summary.json) records
original software, year, publisher, and media-digest observations. MAME's
software-list statements are independent evidence: matching ROM hashes,
titles, and years will **not** automatically merge MAME, Libretro and
Wikidata game, release, or media identities. No ROM/media binaries are
downloaded.

A [deterministic source-only software index](data/mame/software-observations-v1/)
projects the **31,464 original XML entries** to provenance-linked JSONL with
original software identifiers, literal titles, original publisher/year fields,
serials, shared features, and ROM/disk fingerprint attributes. It preserves
one-based original entry and media ordinals, source XML SHA-256 and original
attributes; the [aggregate report](reports/mame-software-observations-v1-summary.json)
remains separate from canonical game or release identity. Build/verify with
`python tools/index_mame_softlists.py --build` or `--check`.

### Direct original Libretro DAT search without SQLite

The [blob-verified Libretro source reader](tools/query_libretro_sources.py)
searches the **75 pinned CC-BY-SA Libretro DAT collections directly**,
without building SQLite or fetching game binaries. It verifies the original
Git blob SHA for each selected source and returns unchanged title, serial,
region, source ordinal and media-hash assertions with attribution.

```sh
python tools/query_libretro_sources.py --platform tigergamecom --limit 5
python tools/query_libretro_sources.py --platform n64 --title Mario --limit 5
python tools/query_libretro_sources.py --platform n64 --without-review-leads --limit 5
```

The optional missing-review-lead filter checks the original, SHA-256-pinned
21,712-unit cross-provider review ledger. Unlinked means no current
correspondence evidence, never a missing or rejected game.

### Offline source-only MAME search

The two lightweight read-only consumers query all **65 MAME source lists
(32,953 software observations)** and source correspondence records without
mixing provider licenses or promoting identities:

```sh
python tools/query_mame_sources.py --list gamecom --title Batman --limit 5
python tools/query_mame_sources.py --publisher "Tiger Electronics" --limit 5
python tools/query_mame_sources.py --without-review-leads --list nes --limit 5
python tools/query_mame_media.py --platform tigergamecom --limit 5
python tools/query_mame_media.py --cohort v3 --platform atari5200 --limit 5
python tools/query_mame_media.py --cohort combined --limit 5
python tools/query_mame_media.py --cohort combined --offset 19023 --limit 4
python tools/query_mame_media.py --mame-list gameboy --limit 5
```

These tools verify their source index SHA-256 and retain original supplier
attribution, media size evidence, and review-only matching semantics.

The media query defaults to the original **65-list** pinned source snapshot,
preserving existing results. Choose `--cohort v3` for four independently
registered newer MAME lists (127 source-media candidates) or
`--cohort combined` for **19,152 observations across 69 MAME lists**. Each
combined result explicitly identifies its original evidence cohort; source
fields and conflicting-size exclusions are not overwritten or promoted to
accepted game or release identities.
Use `--offset` with `--limit` to traverse the complete filtered
SHA-1 evidence inventory in baseline-first order, including across the
65-list/4-list boundary. Results report `offset` and `next_offset`
(null when exhausted) alongside full filtered and source totals.

The `--without-review-leads` source filter cross-checks the complete
[bulk acquisition gap audit](reports/source-review-acquisition-gaps-v1.json).
It surfaces the **11,241 original MAME records** not represented by current
hash-supported or exact-title review leads, retaining their original
publishers, years and source metadata. This means *no current cross-provider
correspondence*, never that a game is missing or its identity is disproven.

### Second CC0 MAME handheld and console source wave

A [second immutable source register](sources/mame-softlists-v2.json) adds
16 independently selected software-list XML partitions from the same pinned
MAME revision. The [source accession workflow](.github/workflows/mame-softlists-v2.yml)
verifies the original 49 lists remain intact before capturing Neo Geo Pocket
and Color, WonderSwan and Color, Pokémon Mini, SG-1000, Pico, PV-1000,
Super A'Can, Videopac, Studio II and other dedicated-console source sets.
Every source retains its own manifest, original bytes and CC0 header.
These new sources are **not** automatically game-identity joins. The
[second source-yield report](reports/mame-softlists-v2-summary.json) verifies
**1,489 additional original software entries** with 1,543 ROM SHA-1 and
two disk SHA-1 assertions.

The [second software-observation projection workflow](.github/workflows/index-mame-softlists-v2.yml)
builds an additional verified, read-only JSONL index with exact source titles,
publisher/year literals, serials, original XML checksums, and media attributes,
without modifying the first 31,464-entry index.

### Cross-source media SHA-1 correspondence

A [provenance-preserving bulk SHA-1 comparator](tools/reconcile_mame_media.py)
has a dedicated [GitHub Actions accession
workflow](.github/workflows/reconcile-mame-libretro-sha1-v1.yml). It checks
original files and compares source-declared SHA-1 digests across the **65 MAME
software lists and 75 original Libretro DAT collections**, retaining source
ordinals, titles, media names, source paths, and SHA-256/Git-blob provenance.
The [current cross-source report](reports/mame-libretro-media-sha1-v1-summary.json)
records **19,025 size-corroborated exact media-fingerprint candidate pairs**,
retaining one contradictory declared-size observation separately. A
[source-coverage audit](reports/mame-libretro-source-coverage-v1.json)
prioritizes independent provider-acquisition gaps without treating
nonmatching dumps as absent games.

Matching a media part/chip digest is review evidence **only**, not a confirmed
game, edition, release or platform identity. Unlike title matching, this
comparison does not infer a game correspondence from spelling or localization.

### Optional complete offline SQLite source-evidence reader

The [derived source-evidence SQLite builder](tools/build_mame_catalog_sqlite.py)
locally materializes **32,953 pinned MAME software observations** and
**117,145 separate original Libretro DAT records**, including both providers'
original media, serial and provenance fields, plus **19,025 exact SHA-1
media-evidence links** and **6,825 separately flagged review-only
exact-title candidates**. The index preserves the 65 CC0 MAME partitions and
75 CC-BY-SA-4.0 Libretro collections as independent sources, together with
the separately rejected declared-size conflict. Build atomically from checked-in text:

```sh
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --build
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --verify
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query --title "Batman" --limit 5
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query --libretro-platform tigergamecom --limit 5
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query-libretro --platform gb --title Tetris --limit 5
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query-libretro --platform n64 --without-review-leads --limit 5
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query-all --title "Tetris" --limit 5
```

The `--query-all` mode accepts only `--title` and/or `--sha1`
and returns **two independently attributed source-result sets**. It does
not merge provider records, accept extra provider-specific filters, or
infer canonical game/release identities.

For **bulk offline lookups**, use the
[bounded JSONL batch-search reader](tools/batch_query_game_sources.py).
It opens and verifies the local source database once, then streams separately
attributed provider results for up to 1,000 title/SHA-1 queries. Example
input lines:

```jsonl
{"id":"tetris","title":"Tetris","limit":2}
{"id":"mario","title":"Mario","limit":2}
```

Run `python tools/batch_query_game_sources.py --db /tmp/ludographium-mame.sqlite
--input queries.jsonl > results.jsonl`. Inputs are bounded to 1 MiB,
require unique request IDs, and reject unknown fields rather than ignoring
constraints. No database or generated results are committed automatically.

Title and publisher substring searches use Unicode NFKC normalization and
casefolding for **lookup only**, preserving source literals verbatim (including
accented titles and scripts outside ASCII).

Search also accepts `--list`, `--publisher`, `--year`, `--serial`,
`--sha1`, `--linked-only`, and `--without-review-leads`. The last filter
selects only original source records lacking a current cross-provider review
lead, independently for MAME or Libretro; it cannot be combined with
`--linked-only`. Both source search modes display exact media
links and unverified title-review alternatives separately; the separate
`--query-libretro` mode accepts `--platform`, `--region`, `--serial`,
`--title`, and `--linked-only`. Results remain original source claims
with optional review-only media links. Each mode rejects filters
belonging to the other provider instead of silently ignoring constraints.
This is an **optional local cache**,
not a canonical game or release identity registry. The
[full-corpus CI verification](.github/workflows/verify-mame-sqlite-v1.yml)
builds and tests it temporarily and deletes the binary afterward; SQLite
files are not committed or published.

### Third independent CC0 platform-source wave

Four original MAME software-list files at the same immutable upstream
revision supply additional Atari 5200, Entex Adventure Vision, Casio
Loopy and VTech CreatiVision evidence. The
[third cohort register](sources/mame-softlists-v3.json) and
[acquisition/index workflow](.github/workflows/mame-softlists-v3.yml)
capture the original CC0 XML, original hashes, publisher/year/serial facts,
media SHA-1 and standalone source-faithful JSONL observations. The
[third original source-yield report](reports/mame-softlists-v3-summary.json)
is kept **separate** from the first two cohorts until its evidence has been
verified and downstream 65-list views are explicitly upgraded. None of
these source captures changes or silently deduplicates the prior corpus.

The third cohort contributes **166 original software entries**, **199 ROM
SHA-1 source assertions**, and 137 original serial-bearing entries. Query
those four lists independently, or opt into searching all 69 original
MAME lists, without altering the default 65-list search:

```sh
python tools/query_mame_sources.py --cohort v3 --list casloopy --limit 5
python tools/query_mame_sources.py --cohort all --list a5200 --limit 5
```

The older `--without-review-leads` filter remains restricted to v1–v2
because the third cohort has not been through the cross-provider reviewer.

The [separate third-cohort SHA-1 matcher](tools/reconcile_mame_v3_media.py)
compares the new four CC0 software lists against all 75 original Libretro
DAT sources while preserving both providers' originals. Its
[pinned source report](reports/mame-libretro-sha1-v3-summary.json) and
[raw evidence index](data/reconciliation/mame-libretro-sha1-v3/links.jsonl)
are kept independent from the existing 19,025-pair, 65-list baseline.
Matching SHA-1/size evidence is a **candidate**, not an accepted cross-provider
game, edition, release or platform identity.

An additive [69-list provider coverage report](reports/three-provider-source-coverage-v2.json)
incorporates these four lists' **127 corroborated SHA-1 media
observations** while preserving the original
[65-list report](reports/three-provider-source-coverage-v1.json) unchanged.
The two generations of source relationships remain separately attributable;
the new report shows precisely which original Libretro collections gained
secondary evidence.




### Three-provider bulk acquisition coverage

The [three-provider source coverage auditor](tools/audit_three_provider_source_coverage.py)
cross-tabulates all **75 original Libretro collection scopes** with
**65 registered Wikidata P400 source scopes** and the **65 independent MAME
software lists**. MAME list-to-Libretro associations are recorded **only
when original SHA-1 and media byte sizes already agree**. The
[pinned per-collection coverage matrix](reports/three-provider-source-coverage-v1.json)
retains separate Wikidata language, fact, credits, relations and MAME media
source-evidence yields, explicit missing registrations, and original DAT
record counts. Its four evidence-coverage classes guide future bulk source
acquisition; they do not establish game or platform identity or imply
that games are absent from zero-row source queries.

Use the [offline coverage query](tools/query_three_provider_source_coverage.py)
to search or prioritize the original scopes from the reproducible report:

```sh
python tools/query_three_provider_source_coverage.py --class neither-secondary-source-family-observed --limit 20
python tools/query_three_provider_source_coverage.py --wikidata-registered no --limit 20
python tools/query_three_provider_source_coverage.py --platform arduboyincarduboy
```

Every query rebuild-checks the underlying source SHA-1 evidence before returning
claims. No platform/game correspondence is added or accepted.


### Independent Libretro collections sharing original media fingerprints

The [cross-scope source auditor](tools/audit_libretro_cross_scope_sha1.py)
rebuilds all **117,145 original Libretro media SHA-1 claims** from 75
blob-pinned DAT sources and records fingerprint groups appearing in more
than one independent platform collection. The
[source-level report](reports/libretro-cross-scope-sha1-v1.json)
and [pinned claim groups](data/reconciliation/libretro-cross-scope-sha1-v1/groups.jsonl)
retain every source title, DAT path, blob SHA, media ordinal, declared
media size, and the exact shared fingerprint. Equal hashes across different
collections are evidence of byte-identical media claims, **not** verified
game equality, platform compatibility, or a platform-assignment error.
Declared-size discrepancies remain explicit.

The [read-only cross-scope query](tools/query_libretro_cross_scope_sha1.py)
reproduces this original-source audit and permits bounded searches by
platform, media SHA-1, title, minimum independent scope count, or
contradictory declared sizes:

```sh
python tools/query_libretro_cross_scope_sha1.py --platform n64 --limit 5
python tools/query_libretro_cross_scope_sha1.py --conflicting-sizes-only --limit 5
```


### Source-name variance among exact media fingerprint observations

A [cross-provider title-variance auditor](tools/audit_mame_title_variance.py)
examines the 19,025 original media SHA-1/size correspondence rows and
classifies the **original source display names** as literal-equal,
equal after conservative region/language normalization, contained phrase,
or different. Its [pinned report](reports/mame-libretro-media-title-variance-v1.json)
and [separate review evidence](data/reconciliation/mame-libretro-title-variance-v1/differences.jsonl)
preserve original titles, source checksums and the one-based media-evidence
record number, without rewriting source metadata. Distinct names can reflect
localization, conventions or other source choices; **this is not a verified
naming error or a canonical game-identity decision**.

The [read-only variance query](tools/query_mame_title_variance.py) verifies
all original 19,025 media candidates and the exact pinned variance projection
before returning bounded source evidence. The current audit preserves
**9,373 title-variance records**; the search accepts provider scope, name,
variance class, SHA-1 or exact evidence-row coordinate:

```sh
python tools/query_mame_title_variance.py --platform genesis --limit 5
python tools/query_mame_title_variance.py --class different-normalized-titles --title "Mario" --limit 5
python tools/query_mame_title_variance.py --mame-list gamecom --limit 5
```


### Source-grounded exact-title review without ROM hashes

The [conservative cross-source title auditor](tools/reconcile_mame_titles.py)
analyzes original MAME and Libretro source-name observations **only when
the two source scopes already have at least three distinct MAME entries
corroborated by equal-SHA-1/equal-size media evidence**. It considers MAME
entries not already linked by SHA-1, normalizes case and whitespace, removes
recognized trailing region/language/revision tags, and retains **only exact
remaining title equalities**. The
[audit workflow](.github/workflows/audit-mame-libretro-titles-v1.yml)
publishes an independent [review report](reports/mame-libretro-title-review-v1-summary.json)
and source-ordained candidates without asserting game, platform, release,
region, translation or edition identity. Unsupported source-scope pairings
are not guessed. The current pinned run found **6,825 candidate pairs**
involving **2,699 MAME observations** without an exact media overlap.
These are not accepted title identities. The additive third MAME
cohort has a separate [review report](reports/mame-libretro-title-review-v3-summary.json):
**8 additional exact-name review leads** across 6 original MAME software
observations, derived from four independently SHA-1-supported source scopes.
The original 6,825 rows remain unchanged. The
[read-only query interface](tools/query_mame_title_review.py) checks
the complete source SHA-256 before searching:

```sh
python tools/query_mame_title_review.py --title "Mario" --limit 5
python tools/query_mame_title_review.py --ambiguous-only --limit 5
python tools/query_mame_title_review.py --platform nes --min-scope-support 10 --limit 5
python tools/query_mame_title_review.py --cohort v3 --limit 5
python tools/query_mame_title_review.py --cohort combined --limit 5
```

Each returned lead includes the number of competing candidate records for
its source MAME entry. Unique leads remain unverified.

### Stable-ID corpus-wide source-evidence review queue

The [evidence-only review-unit builder](tools/build_source_review_units.py)
groups independently pinned exact-media candidates (19,025 rows) and
conservative exact-title leads (6,825 rows) by their **original MAME source
occurrence**, without joining game identities or duplicating the full raw
evidence. Each unit gets an immutable-snapshot-qualified
`lgreview:v1:` identifier from its original list, XML SHA-256 and ordinal.
It retains every competing Libretro source-record target and the precise
one-based evidence JSONL row coordinates.

The [versioned review report](reports/source-review-units-v1-summary.json)
groups cases into single/multiple-target source evidence with separate
media- and title-supported categories. Even one-target, equal-SHA-1
records are **unreviewed evidence, not canonical works or releases**.
The [CI source queue workflow](.github/workflows/build-source-review-units-v1.yml)
rebuilds and validates this text-only review queue from the original sources.

The [additive third-cohort review builder](tools/build_source_review_units_v3.py)
and [source report](reports/source-review-units-v3-summary.json) pin
**133 additional original-source review tasks** from four independently
captured MAME lists: 127 SHA-1/size-evidence units and 6 title-only
units. Two of those six retain multiple competing source targets.
The preceding 21,712 review-unit records and their stable IDs remain
unchanged; the combined number of separately pinned review units is
**21,845**. Neither a source review ID nor a unique candidate certifies
a game or release identity.

The [stable-ID source review query](tools/query_source_review_units.py)
verifies the entire queue and both parent evidence indexes before returning
source-scoped results. It searches by stable review ID, original MAME list,
Libretro collection, title, ambiguity and evidence class. Optional
`--include-evidence` expands original SHA-1 and exact-title JSONL evidence
without implying confirmed game identities:

```sh
python tools/query_source_review_units.py --ambiguous-only --limit 3
python tools/query_source_review_units.py --platform nes --evidence-type title --limit 3
python tools/query_source_review_units.py --mame-list gamecom --include-evidence --limit 2
python tools/query_source_review_units.py --cohort v3 --platform atari5200 --include-evidence --limit 2
python tools/query_source_review_units.py --cohort combined --ambiguous-only --limit 2
python tools/query_source_review_units.py --cohort combined --offset 21710 --limit 5
python tools/query_source_review_units.py --review-id lgreview:v1:<64-hex-digest> --include-evidence
```

The default CLI query preserves the original 21,712-unit result.
`--cohort v3` verifies the separately pinned 133-unit accession and its
parent evidence row hashes; `--cohort combined` searches **21,845
source-only review tasks** without changing any original stable IDs.
The bounded `--offset`/`--limit` pair pages through filtered source review
units in a stable, baseline-first order, including across the third-cohort
boundary. Each result reports `offset` and `next_offset` (null at the end),
while `total_filtered_source_review_units` remains the full filtered count.
Filters are applied before pagination; `--include-evidence` only expands the
returned page. The original evidence and stable review IDs are unchanged.
Every returned unit remains unreviewed, including single-target matches.

A complementary [Libretro-first source-gap auditor](tools/audit_libretro_source_review_gaps.py)
checks all **117,145 source DAT records across 75 Libretro collections**
against the original MAME-target review queue. The
[75-platform coverage report](reports/libretro-source-review-acquisition-gaps-v1.json)
separates **18,729 media-only, 4,243 title-only, 127 dual-evidence,
and 94,046 currently unlinked** original Libretro records; 25 source
collections have no current review lead. It also records per-scope source
revision, original Git blob SHA and license.
Its [automated workflow](.github/workflows/audit-libretro-review-gaps-v1.yml)
rebuilds the report from independently pinned originals. A record without a
lead is a **provider-acquisition priority**, never an assertion that a game
is absent or that source identities have been adjudicated.

The IDs identify **original-source review tasks**, not canonical games.
The optional [local SQLite source reader](tools/build_mame_catalog_sqlite.py)
also supports `--query-review`, indexing all 21,712 task IDs and their
original competing Libretro targets for fast exact-ID, source-class,
ambiguity, title and evidence-family searches. Run:

```sh
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query-review --evidence-type title --ambiguous-only --limit 3
python tools/build_mame_catalog_sqlite.py --db /tmp/ludographium-mame.sqlite --query --list psx --without-review-leads --limit 5
```

The SQLite file is ephemeral; its review-unit table is reconstructed from
the original CC0 MAME and CC-BY-SA Libretro evidence. Nothing is automatically
accepted as the identity of a game, platform, edition or release.

## Additional platform source accession

A separate pinned Wikidata CC0 accession now covers **Atari 7800,
PlayStation Portable, and PlayStation Vita** (2,254 game-item/platform
observations from 3,888 original source rows). This is an additive source
capture and does not modify the original 16-platform Wikidata baseline.

```sh
cargo run --locked -- --wikidata-expanded --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v2 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v3 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v4 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v5 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v6 --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v6 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v7 --platform all --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v7 --platform all --limit 5
# Per-console source-title review counts: reports/wikidata-expanded-platform-v{3,4,5}-title-review-v1.json
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v2 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --platform atari7800 --qid Q1014915
cargo run --locked -- --wikidata-expanded --platform sonyplaystationvita --title "King Oddball"
```

The sixth expansion cohort adds **six independently hash-pinned Wikidata
platform queries** (Game Gear, New Nintendo 3DS, Nintendo DSi, Nintendo 64DD,
Tiger Game.com and Fairchild Channel F). It preserves **662 raw source rows,
309 item/platform observations, 642 literal publication-date bindings and two
nonliteral publication bindings**. Tiger Game.com's zero-row query is retained
and verified as scoped noncoverage, not inferred evidence about its game library.
The Rust reader and conservative title-candidate CLI accept
`--expansion-source v6` while keeping prior snapshots immutable.

The seventh independently pinned Wikidata cohort covers **Arcadia 2001,
Super Cassette Vision, GamePark GP32, Interton VC 4000, RCA Studio II and
Sega Beena**. These six P400 queries preserve **20 raw source rows and 14
item/platform observations**. Two zero-row scopes (GP32 and Interton VC 4000)
are explicitly retained as query-specific noncoverage, not claims that those
consoles had no games. Read-only Rust source queries and candidate review are
available via `--expansion-source v7`.

The original source responses and hashes live under
[data/wikidata/platform-expansion-v1/](data/wikidata/platform-expansion-v1/).

## Expanded multilingual game-title source captures

Two additional independently preserved Wikidata localized-name cohorts cover
**37 more platform scopes** (19 in `expanded-v1` and 18 in `expanded-v2`).
They retain original language-tagged labels and aliases, source queries,
full response bytes, per-platform manifests and SHA-256 checksums. The Rust
reader independently verifies both cohorts, including zero-row query scopes,
without converting source names into canonical games or regional releases.

```sh
cargo run --locked -- --wikidata-localized-titles --metadata-cohort expanded-v1 --platform all --language es --limit 5
cargo run --locked -- --wikidata-localized-titles --metadata-cohort expanded-v2 --platform gg --language ja --limit 5
cargo run --locked -- --wikidata-localized-titles --metadata-cohort expanded-v2 --platform gameparkgp32 --limit 5
```

A third, independent [v8 localized source cohort](data/wikidata/expanded-localized-v3/)
adds **247 original language-tagged label and alias observations** across 12
new provisional query scopes, including six preserved zero-row source queries.
No title or alias is promoted to a canonical or verified regional release identity.

Across the original 16 platform scopes and the three added cohorts, a
**combined 65-scope offline query** now exposes **154,198 original localized
name/alias observations** while preserving every record's source partition,
ordinal, language, original binding and verified source hashes:

```sh
cargo run --locked -- --wikidata-localized-titles --metadata-cohort combined --platform all --language es --limit 5
cargo run --locked -- --wikidata-localized-titles --metadata-cohort combined --platform gg --language ja --limit 5
cargo run --locked -- --wikidata-localized-titles --metadata-cohort expanded-v3 --platform mobilezeebo --language pt --limit 5
```

The original 16-platform mode remains the default. Zero-row queries indicate
only source-specific Wikidata noncoverage, not absence of games.

The exact-title correspondence reviewer also supports
`--wikidata-localized-candidates --metadata-cohort combined --platform all`
across all **65 platform source scopes**, including all original language-tagged
label/alias evidence. It preserves ambiguous source QIDs and distinguishes
matches already supported by independently pinned English game-label evidence
from genuinely additional localized-name candidate links. Exact title
correspondence is **review-only**, not a verified work, region or release join.

A [type-agnostic source probe](.github/workflows/wikidata-p400-untyped-probe-v1.yml)
bulk-queries all ten completely empty P400 scopes without requiring their
items to have the Wikidata video-game instance type. Its separate source
captures retain raw responses, query bytes, hashes, and optional P31 types.
Any returned QIDs are **unreviewed evidence**, not automatically games or
accepted release/platform mappings.

A [source-yield coverage matrix](reports/wikidata-source-coverage-matrix-v1.json)
cross-tabulates the 65 registered query scopes across original game facts,
localized names, developer/publisher/genre statements, and
relation/identifier statements. It also tracks the ten remaining unregistered
source collections. This is an **acquisition-priority diagnostic**, not a game
count or evidence of platform completeness. Rebuild with
`python tools/audit_wikidata_evidence_matrix.py --write`, or verify the
pinned report with `--check`.

A [deterministic 75-collection scope coverage audit](reports/wikidata-p400-platform-gaps-v2.json)
checks all current source registers offline and identifies ten remaining
unregistered Libretro source partitions: eight distribution-specific collections
requiring separate identity treatment, and two unresolved platform/accessory
research leads. The [earlier 22-gap report](reports/wikidata-p400-platform-gaps-v1.json)
remains retained as the source state that led to this accession.
These are **unregistered P400 scopes**, not evidence that those platforms have
no games. Regenerate/check with `python tools/audit_wikidata_platform_gaps.py --write`
or `--check`.

The [historical 14-scope platform-search discovery queue](sources/wikidata-platform-discovery-v1.json)
accessions independent, hash-pinned Wikidata entity-search responses through
[GitHub Actions](.github/workflows/wikidata-platform-discovery-v1.yml).
Search-result QIDs remain independently sourced discovery evidence, never
accepted canonical platform mappings. A separate [provisional v8 P400
source register](sources/wikidata-platform-expansion-v8.json) preserves
twelve independently captured direct-P400 query scopes. The [v8 source
captures](data/wikidata/platform-expansion-v8/) contain **53 original source
rows, 27 item/platform observations, 49 English-label bindings, and 50 literal
date bindings**, including six explicit zero-row scopes. These are attributed
Wikidata source claims, not accepted game identities, physical-platform mappings,
or complete coverage. The remaining Pocket Challenge V2 and LeapPad platform
mappings are unresolved. Verify the provider search evidence with
`python tools/discover_wikidata_platforms.py --check`.

The v8 reader can now validate and query these original text captures
offline without changing older cohorts:

The offline property and relation readers additionally support
`--metadata-cohort combined` for **65 source platform scopes**. Their
**58,460 original developer/publisher/genre statements** and **113,204
relation/identifier statements** remain separate source claims, not merged
game identities. Combined queries intentionally reject `--with-entity-labels`
until cross-cohort label provenance can be represented unambiguously.

```sh
cargo run --locked -- --wikidata-expanded --expansion-source v8 --platform all --limit 5
cargo run --locked -- --wikidata-expanded --expansion-source v8 --platform mobilezeebo --limit 5
cargo run --locked -- --wikidata-expanded-candidates --expansion-source v8 --platform all --limit 5
```



The next bulk-acquisition wave preserves **85 original P178 developer,
P123 publisher, P136 genre statements** and **123 nine-predicate relation
and identifier statements** for the twelve provisional v8 scopes. Their
original source rows, zero-result captures, query/response hashes and unmatched
QIDs remain separate from verified game identities. Read both offline using
`--wikidata-properties --metadata-cohort expanded-v3` and
`--wikidata-relations --metadata-cohort expanded-v3`. A separately pinned [v8 English entity-label
inventory](data/wikidata/expanded-labels-v2/) covers all **83 referenced
QIDs**, including **73 English labels** and **10 explicit unlabeled references**.
The offline CLI verifies the exact source-manifest inventory before exposing
`--with-entity-labels` for this cohort; no QID is promoted into an accepted
entity or game identity. See the
[credits accession](.github/workflows/wikidata-expanded-credits-v3.yml) and
[relations accession](.github/workflows/wikidata-expanded-relations-v3.yml)
for the reproducible source-query contracts.

## Expanded Wikidata developer, publisher and genre evidence

The independently pinned [19-platform credit corpus](data/wikidata/expanded-credits-v1/)
adds **10,269 original P178 developer, P123 publisher, and P136 genre
statements** across Atari, PlayStation, Sega, Nintendo, NEC, and other
console scopes outside the original sixteen-platform baseline. It covers
**3,150 game-item/platform observations**. Original SPARQL responses,
ordered JSONL bindings, source SHA-256 checksums, and unmatched values are
preserved; none of these claims establishes a canonical game identity.

```sh
cargo run --locked -- --wikidata-properties --expanded-credits --platform all --limit 5
cargo run --locked -- --wikidata-properties --expanded-credits --platform sonyplaystationportable --property P178 --limit 5
```

These are source claims, not independently provider-confirmed credits.

A second [18-platform credit batch](data/wikidata/expanded-credits-v2/)
adds **962 more P178/P123/P136 statements** concerning **312
item/platform observations**, including four preserved zero-result query
scopes. Together, the 37 added console partitions contribute **11,231
additional credited-source statements**.

A separate [37-platform game-relationship accession](data/wikidata/expanded-relations-v1/)
and its [second cohort](data/wikidata/expanded-relations-v2/) capture
**20,460 additional relation, language, format, series, distributor, title,
and Steam/GOG identifier statements**, retaining original RDF bindings and
source hashes. Read these completely offline:

```sh
cargo run --locked -- --wikidata-properties --metadata-cohort expanded-v2 --platform all --limit 5
cargo run --locked -- --wikidata-relations --metadata-cohort expanded-v1 --platform all --limit 5
cargo run --locked -- --wikidata-relations --metadata-cohort expanded-v2 --platform all --property P1733 --limit 5
```

All values remain attributed claims, not provider-verified external IDs,
accepted game identities, editions, or release facts.

A separate [expanded English-label source](data/wikidata/expanded-labels-v1/)
adds **2,255 QID observations with 2,079 English labels**, independently
captured in 23 source batches. The remaining 176 QIDs retain their original
identifiers without invented names. Use source-attributed name evidence:

```sh
cargo run --locked -- --wikidata-properties --metadata-cohort expanded-v2 --with-entity-labels --platform all --limit 5
cargo run --locked -- --wikidata-relations --metadata-cohort expanded-v1 --with-entity-labels --platform all --limit 5
```


## Collection

The original v1 JSON baseline covers ten console and handheld platforms (retained for compatibility). **The Git clone now contains the original text DAT metadata for all 75 platform collections and 117,145 source observations**, with [complete provenance and coverage details](docs/BULK-EXPANSION.md). The 65 added identification DATs and 279 bibliographic DATs are [tracked under `archive/libretro-bulk/metadat/`](archive/libretro-bulk/metadat), not stored exclusively in a generated database or fetched on demand.

| Platform | Source records |
| --- | ---: |
| Super Nintendo | 4,268 |
| Game Boy | 2,254 |
| Game Boy Color | 2,566 |
| Game Boy Advance | 3,692 |
| Nintendo Entertainment System | 14,132 |
| Nintendo DS | 7,701 |
| Nintendo 64 | 1,435 |
| Sega Mega Drive / Genesis | 3,365 |
| Sega Master System | 1,163 |
| Sega Game Gear | 915 |
| **Total** | **41,491** |

These are original source observations, **not a count of distinct games**. Every record has an upstream title and fingerprint information, with additional fields depending on what the source provides.

The original 88 pinned Libretro DATs supply **129,008 bibliographic claims** across developer, publisher, release-year, release-month, genre, franchise, serial, age-rating, player-count, and rumble fields. Strict CRC32-and-title comparison attaches **98,856 claims** to base observations; conflicting or unmatched source statements remain visible rather than being silently assigned to games.

[75-platform bulk expansion](docs/BULK-EXPANSION.md) · [Source coverage](reports/source-coverage-v1.json) · [Enrichment coverage](reports/enrichment-coverage-v1.json) · [Reconciliation review queue](reports/reconciliation-queue-v1.json) · [Cross-provider company and year evidence report](reports/wikidata-cross-provider-review-v1.json) · [Steam/GOG identifier ambiguity report](reports/wikidata-external-identifier-review-v1.json) · [Source registers](sources/README.md)

## Rust offline source search

The existing Rust CLI can search all **75 cloned identification DAT collections** directly. No Python, SQLite build or network connection is necessary:

```sh
cargo run --locked -- --source-dat --platform all --title "Adventure" --limit 5
cargo run --locked -- --source-dat --platform atari2600 --title "Asteroids"
cargo run --locked -- --source-dat --enriched --platform atari2600 --title "Asteroids"
cargo run --locked -- --source-dat --enriched --claims --platform sonyplaystationportable --title "007 - From Russia with Love"
cargo run --locked -- --wikidata-text --platform atari2600 --qid Q379915
cargo run --locked -- --wikidata-text --platform all --title "Adventure" --limit 5
cargo run --locked -- --wikidata-candidates --platform all --limit 5
cargo run --locked -- --wikidata-candidates --compare-years --platform all --limit 5
cargo run --locked -- --wikidata-candidates --compare-credits --platform all --limit 5
cargo run --locked -- --wikidata-properties --platform all --limit 5
cargo run --locked -- --wikidata-properties --platform atari2600 --qid Q379915 --property P178
cargo run --locked -- --wikidata-properties --with-entity-labels --platform all --limit 5
cargo run --locked -- --wikidata-items --platform all --title "Adventure" --limit 5
cargo run --locked -- --wikidata-items --platform atari2600 --qid Q379915
cargo run --locked -- --wikidata-relations --platform all --property P1476 --limit 5
cargo run --locked -- --wikidata-relations --platform all --property P1733 --limit 5
cargo run --locked -- --wikidata-relations --with-entity-labels --platform atari2600 --qid Q100701966
cargo run --locked -- --wikidata-relations --platform all --external-id 15750 --property P1733
cargo run --locked -- --wikidata-authority-ids --platform all --property P4769 --limit 5
cargo run --locked -- --wikidata-authority-ids --platform all --property P11688 --external-id 39536
cargo run --locked -- --wikidata-gamefaqs-qualifiers --platform all --external-id 579332 --limit 5
cargo run --locked -- --wikidata-localized-titles --platform all --language es --limit 5
cargo run --locked -- --wikidata-localized-candidates --platform all --limit 5
```

The opt-in `--source-dat` mode reads the original, hash-verified DAT text. It retains original record ordinals, source paths and Git blob hashes. Title results are source observations, not canonical game identities; fingerprint matches are based on literal source SHA-1 or CRC32 plus size. The preexisting generated-JSON/ten-system Rust consumer path remains available unchanged. Add `--enriched` in source-DAT mode to read all **367 pinned bibliographic DATs** (88 original and 279 additional) directly from Git text, hash-verify them, and conservatively attach source claims by unique CRC32 and exact original title. The full corpus retains **167,640 original field observations**, including **112,948 conservatively attached claims**; unresolved claims retain their reasons and provenance instead of being treated as game identities. For original field records that cannot be joined to identification observations (including PSP serial-only records with no CRC32), `--claims` searches or lists the preserved bibliographic observations independently, without inventing a game match. This needs no Python or SQLite. [Details](docs/BULK-EXPANSION.md). The independent [CC0 Wikidata text accession](docs/WIKIDATA.md) is now available through `--wikidata-text`, with verified JSONL source hashes, direct QID lookup, attributed publication-date claims and English-label discovery. This mode does not assert a game/media identity. The separate opt-in `--wikidata-candidates` mode performs an evidence-only, same-platform conservative title correspondence, preserving QID ambiguity and both source digests without assigning canonical identities.

## Repository structure

| Location | Description |
| --- | --- |
| [`archive/`](archive/) | Unmodified original DATs, including all 344 pinned additional console/handheld sources |
| [`sources/`](sources/) | Pinned source revisions, attribution, and reuse information |
| [`generated/`](generated/) | Reproducible identification and bibliographic claim indexes |
| [`data/wikidata/v1/`](data/wikidata/v1/) | Small, attributed, human-readable Wikidata JSONL source files |
| [`curated/`](curated/v1/identities.json) | Evidence-backed work, release and build identities (15 works, 17 releases, 28 exact builds) |
| [`platforms/`](platforms/platforms.json) | Platform identifiers |
| [`tools/`](tools/) | Import, lookup, auditing, and verification scripts |
| [`crates/ludographium/`](crates/ludographium/) | Rust metadata reader and CLI |

The [distribution manifest](generated/v1/distribution.json) publishes byte lengths and SHA-256 digests for 25 consumer artifacts, including curated identities, both source registers, and a standalone metadata-attribution notice. A deterministic, metadata-only runtime archive can be built from the manifest; successful main-branch GitHub Actions runs also attach this portable bundle for downstream use. The [latest pinned dataset, **data-v1.6.0**](https://github.com/sguzman/ludographium/releases/tag/data-v1.6.0) includes the 75-platform expanded SQLite, a separately attributed Wikidata-enriched database and source snapshot, the ten-platform SQLite, and the integrity-checked JSON runtime. Earlier releases remain intact and individually addressable; consult the [release history](docs/DATA-RELEASES.md) for version-specific coverage. Consumers can consult the [dataset release history](docs/DATA-RELEASES.md) and [versioned publication policy](docs/RELEASING.md).

## Expanded 75-platform dataset

The [released bulk SQLite corpus](https://github.com/sguzman/ludographium/releases/download/data-v1.5.0/ludographium-expanded-data-v1.5.0.sqlite) contains **117,145 source records and media fingerprints** plus **167,640 bibliographic source claims** spanning 75 dedicated console/handheld collections. Of these, **112,948 field claims** are conservatively matched; **19,763 source records** have some attached field metadata. The 65 new identification DATs and 279 additional bibliographic DATs are pinned by source revision and original Git blob hash. All original source files are preserved inside the expanded SQLite artifact, including metadata with missing or ambiguous checksums.

The existing ten-platform release remains an independently reproducible, compatible baseline. Source observations are not asserted to be distinct game identities.

## Independent Wikidata observations

A [separate CC0 Wikidata accession](docs/WIKIDATA.md) adds **15,868 platform-linked item observations** and **29,333 independently attributed publication-date claims** across 16 console mappings. The reproducible bulk matcher generated **8,971 title-based review candidates**, identifying 8,908 existing source observations with possible Wikidata counterparts; **126 links are explicitly ambiguous**. They are **not** accepted work or release identities. The raw query results and SHA-256 values are pinned in the [source accession register](sources/wikidata-accession-v1.json) and published as [the immutable `data-v1.6.0` Wikidata source snapshot](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-source-data-v1.6.0.json). A [Wikidata-enriched, fully offline SQLite download](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-data-v1.6.0.sqlite) is released separately from the 75-system base corpus.

## Complete metadata corpus

**All 41,491 source observations and all 129,008 bibliographic claims can now be queried from one offline SQLite database.** The [full-corpus export](docs/CORPUS.md) automatically combines source records, exact media checksums, and individually attributed field claims across all ten platforms. It retains all unresolved statements, so only the 98,856 safely matched claims are attached to their corresponding source observations. In the current snapshot, **16,937** source records have one or more matched bibliographic claims.

The SQLite export is a complete source-level collection, **not** a hand-selected list of curated game identities. Original source records are kept separate, and no source-title similarity is used to fabricate canonical game identities. Each main-branch validation run generates a downloadable, SHA-256-checked `ludographium-complete-corpus-sqlite` artifact. That database is permanently published as the [`data-v1.4.0` SQLite download](https://github.com/sguzman/ludographium/releases/download/data-v1.4.0/ludographium-corpus-data-v1.4.0.sqlite), with a [separate SHA-256 checksum](https://github.com/sguzman/ludographium/releases/download/data-v1.4.0/ludographium-corpus-data-v1.4.0.sqlite.sha256).

**Corpus coverage, source acquisition and batch transformation are the priorities.** The 15 optional manually reviewed identity examples are not the ingestion method and do not limit the searchable catalog.

## Use the data

The Rust reader validates the source indexes before returning matches. Consumers may supply a known fingerprint or stream exact local media bytes without storing the file in Ludographium. Explicit NES, SNES, and N64 [byte-domain conversions](docs/BYTE-DOMAINS.md) are available for headered or byte-swapped local files and compatible ZIP members without changing the default exact-byte lookup:

```sh
cargo run --locked -p ludographium -- --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

A downloaded dataset may be checked end-to-end using the Rust command `--verify-runtime --root /path/to/extracted/runtime`, which validates all declared files and source catalog references against the included manifest. Verify the archive checksum from the release first; see the [consumer guide](docs/CONSUMERS.md).

Source-title discovery is also available when no fingerprint is known. Results remain original source records, not merged game identities:

```sh
cargo run --locked -p ludographium -- --platform nes --title "Mario" --limit 5
```

Use `--platform all` to identify media or search titles across **every registered system** when the platform is not known. The Rust library offers the equivalent `CatalogCollection` and `EnrichedCatalogCollection` APIs:

```sh
cargo run --locked -p ludographium -- --platform all --sha1 6B47BB75D16514B6A476AA0C73A683A2A4C18765 --curated
```

For an exact local file, use `--file /path/to/game` instead of a hash. Input is streamed and never added to the catalog. Compressed libraries can use `--zip` to inspect individual ZIP members without extracting them to disk:

```sh
cargo run --locked -p ludographium -- --platform all --zip /path/to/game.zip --enriched
```

Archive entries remain distinct source candidates, with bounds on the number of entries and decoded bytes. The file's representation must exactly match the source checksum; headers, archives, and byte-swapped formats are not silently normalized.

Add `--enriched` to fingerprint, file, or title queries to include matched and unresolved bibliographic claims separately:

```sh
cargo run --locked -p ludographium -- --enriched --platform gba --sha1 FC6163F99B71B05C10686A0D29010B31274E1DC4
```

Python lookup tools offer equivalent access. A match associates a fingerprint with an upstream record; it does not automatically establish a unique game, release, or build identity. Fifteen curated work identities now demonstrate explicitly reviewed revision and regional relationships (17 releases, 28 exact builds), including Nintendo DS, Nintendo 64 and Sega Genesis revisions. Most source records remain uncurated.

## Documentation

- [Scope](docs/SCOPE.md), [data model](docs/MODEL.md), and [media byte domains](docs/BYTE-DOMAINS.md)
- [Curated identity framework](docs/IDENTITIES.md), [revision candidate review](docs/IDENTITY-REVIEW.md), [cross-source field review](docs/CROSS-SOURCE-REVIEW.md), and [dataset release history](docs/DATA-RELEASES.md)
- [Licensing and third-party attribution](docs/LICENSING.md)
- [Provenance and licensing](docs/PROVENANCE.md)
- [75-platform bulk data accession](docs/BULK-EXPANSION.md), [full-corpus SQLite export](docs/CORPUS.md), [offline consumer interface](docs/CONSUMERS.md), and [version compatibility](docs/COMPATIBILITY.md)
- [Importing and validating](docs/IMPORTING.md)
- [Source acquisition strategy](docs/SOURCE-STRATEGY.md)
- [Quality reports](reports/README.md) and [roadmap](docs/ROADMAP.md)
