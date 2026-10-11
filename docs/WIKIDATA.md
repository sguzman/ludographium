# Independent Wikidata game-metadata source

Wikidata is a separate, CC0-licensed source of structured game metadata. Its source statements are **not treated as authoritative identity proof** and are not assumed to have originated independently of every other upstream contributor. Unlike the Libretro identification and field-DAT imports, it provides globally resolvable item identifiers, platform associations and publication-date observations.

The [official Wikidata licensing policy](https://www.wikidata.org/wiki/Wikidata:Licensing) places structured item and property data under CC0. No Wikipedia article prose, artwork, game files, cover images, or third-party descriptions are copied.

## Verified first accession

The first completed source capture on **2026-10-09** includes **16 platform mappings, 15,868 original Wikidata item/platform observations, 29,333 literal publication-date statements, 8,971 source-title candidate links, and 8,908 console source observations with a candidate**. Among the candidate links, **126** were explicitly marked ambiguous rather than resolved.

[Snapshot lock and source checksums](../sources/wikidata-accession-v1.json) · [Successful capture, verification and reconciliation](https://github.com/sguzman/ludographium/actions/runs/37968964983) · [Published `data-v1.6.0` release](https://github.com/sguzman/ludographium/releases/tag/data-v1.6.0)

The [published Wikidata-enriched SQLite database](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-data-v1.6.0.sqlite) retained all **117,145** Libretro source observations and **167,640** attributed field claims unchanged. It adds independent Wikidata entities, dates, exact query-response evidence and noncanonical title candidates.

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

## Unified read-only Wikidata game-item observations

The Rust `--wikidata-items` mode constructs an exact-QID, per-platform,
**noncanonical source projection** from all three independent captures:
original English game labels and date statements; original developer,
publisher and genre claims; and separately captured company/genre entity
English labels. Source provenance and capture boundaries remain visible.

```sh
cargo run --locked -- --wikidata-items --platform all --limit 10
cargo run --locked -- --wikidata-items --platform atari2600 --qid Q379915
cargo run --locked -- --wikidata-items --platform snes --title "Mario" --limit 10
```

The union preserves and counts records found only in the original title/date
capture, only in the later property capture, or in both independently
captured source snapshots. No Libretro work/media identity or source
correction is inferred. The reader requires no SQLite, Python, or network.

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

## Accuracy and source-rights boundaries

Wikidata's CC0 statements can support independently *attributed* comparisons. They are not automatically independent factual corroboration: Wikidata contributors may have consulted the same upstream references as Libretro contributors. Label correspondence alone has no power to authenticate media hashes, identify a regional edition, or establish that two products are the same canonical work.

The Libretro/No-Intro-derived metadata and their CC BY-SA attribution remain governed by their original notices; Wikidata's CC0 grant does not relicense third-party source data. The offline database includes neither game files nor copyrighted cover art.
