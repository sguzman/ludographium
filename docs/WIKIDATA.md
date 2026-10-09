# Independent Wikidata game-metadata source

Wikidata is a separate, CC0-licensed source of structured game metadata. Its source statements are **not treated as authoritative identity proof** and are not assumed to have originated independently of every other upstream contributor. Unlike the Libretro identification and field-DAT imports, it provides globally resolvable item identifiers, platform associations and publication-date observations.

The [official Wikidata licensing policy](https://www.wikidata.org/wiki/Wikidata:Licensing) places structured item and property data under CC0. No Wikipedia article prose, artwork, game files, cover images, or third-party descriptions are copied.

## Verified first accession

The first completed source capture on **2026-10-09** includes **16 platform mappings, 15,868 original Wikidata item/platform observations, 29,333 literal publication-date statements, 8,971 source-title candidate links, and 8,908 console source observations with a candidate**. Among the candidate links, **126** were explicitly marked ambiguous rather than resolved.

[Snapshot lock and source checksums](../sources/wikidata-accession-v1.json) · [Successful capture, verification and reconciliation](https://github.com/sguzman/ludographium/actions/runs/37968964983)

The resulting separate SQLite database retained all **117,145** Libretro source observations and **167,640** attributed field claims unchanged. It adds independent Wikidata entities, dates, exact query-response evidence and noncanonical title candidates.

## Bulk accession

The [source register](../sources/wikidata-v1.json) declares 16 Wikidata platform IDs across the existing 75-platform console corpus. It includes original ten-system families and selected additional Atari, Nintendo, Xbox and PlayStation collections.

The [independent-source acquisition tool](../tools/wikidata_source.py) issues one *whole-platform* query per declared hardware ID. It does not issue a request for each game, and it does not do regex/fuzzy scraping of titles.

Each query selects Wikidata entities asserted to be video games (`P31:Q7889`) on the declared platform (`P400:Q...`), requesting English item labels and publication dates (`P577`). The raw JSON responses, exact SPARQL query text, SHA-256 digests, timestamp, row count, and originating platform QID are all retained. Entity labels and publication-date facts are source claims; dates without territory qualifiers are **not** silently converted into region-specific release dates.

The [Wikidata Query Service documentation](https://www.wikidata.org/wiki/Wikidata:Data_access) advises against using broad regex-based search or large, expensive queries; the [query service manual](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual) describes timeouts and rate limits. This importer partitions by platform, sends a meaningful User-Agent, accesses sequentially with delay, retries retryable responses, limits response bytes, and **rejects** result sets that reach the configured row ceiling. A failed or truncated snapshot is not considered a completed accession.

A live Wikidata query endpoint is not an immutable upstream revision. Reproducibility begins when the **complete raw query results** have been captured, checksummed, and stored as a snapshot. The resulting SQLite database can be regenerated from exactly that snapshot and the immutable expanded `data-v1.5.0` source corpus. Re-running the live query later may yield different source content.

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
