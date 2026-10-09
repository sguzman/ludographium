# Complete offline console metadata corpus

The bulk corpus builder can generate **a queryable local SQLite index for the pinned collection**, rather than requiring individual game curation. It is derived automatically from the existing immutable text-based identification and bibliographic source indexes. **SQLite is a generated consumer index, not canonical source data or an asset for future releases.** See the [text-first data policy](DATA-FORMATS.md).

The **original ten-platform v1 baseline** contains:

- **41,491 identification source observations** across ten Nintendo and Sega systems;
- **129,008 separately attributed bibliographic field claims**, of which **98,856** resolve conservatively to original source observations;
- all source-record media entries, exact hashes, titles, regions, serials and other upstream record fields;
- all unresolved and conflicting claim observations with their original status, value and source citations.

The Git checkout now includes [the 344 extra original text DAT files](../archive/libretro-bulk/metadat), alongside the prior ten platform archives and the checked-in Wikidata JSONL corpus. A historical, optional [bulk-expanded SQLite build](BULK-EXPANSION.md) from `data-v1.5.0` includes **75 platform collections, 117,145 identification observations and 167,640 bibliographic claims** (112,948 conservatively matched). The v1 ten-platform SQLite and JSON packages remain available for consumers pinned to that original contract.

Those 41,491 baseline observations are **not asserted to be 41,491 distinct games**. The database preserves separate original source occurrences and does not manufacture work or release identities by normalizing titles or inventing relationships.

## Consumer interface

GitHub Actions builds `ludographium-corpus.sqlite` for every main-branch validation run, alongside a SHA-256 checksum. The [`data-v1.4.0` release](https://github.com/sguzman/ludographium/releases/tag/data-v1.4.0) publishes the versioned **SQLite companion** with its own checksum, independent of the portable JSON runtime archive. The GitHub Actions artifact is short-lived; [versioned SQLite Release assets](https://github.com/sguzman/ludographium/releases/download/data-v1.4.0/ludographium-corpus-data-v1.4.0.sqlite) persist.

The SQLite file needs no server, local media files or Rust installation. Any SQLite reader can query it offline. Its main relations:

| Relation | Coverage |
| --- | --- |
| `platforms` | Original source snapshot and license for each platform |
| `games` | **Every** original source record; `(platform, source_ordinal)` is an observation locator, not a canonical game ID |
| `media` | Every original media entry, including exact SHA-1, MD5, CRC32, size and unmodified source media fields |
| `claims` | **Every** bibliographic field observation, its source locator, original field values, CRC32, and matched/unmatched resolution status |
| `matched_metadata` | Read-only SQL view of only those field claims conservatively resolved to the original record, never by title similarity or CRC32 alone |
| `provenance` | Machine-readable pinned source registers, original catalog manifest, and the full metadata attribution notice |

For a local repository checkout, rebuilding the entire catalog is one operation:

```sh
python3 tools/build_corpus.py --build --db /tmp/ludographium-corpus.sqlite
python3 tools/build_corpus.py --verify --db /tmp/ludographium-corpus.sqlite
```

The following examples are documentation for consumers; they are **not prerequisites that the principal must perform** for project development:

```sh
python3 tools/build_corpus.py --db /tmp/ludographium-corpus.sqlite --summary
python3 tools/build_corpus.py --db /tmp/ludographium-corpus.sqlite --title "Super Mario" --limit 10
python3 tools/build_corpus.py --db /tmp/ludographium-corpus.sqlite --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037 --platform gb
```

Any SQLite application may also query it directly:

```sql
SELECT g.platform, g.title, c.field, c.value,
       c.source_path, c.source_ordinal
FROM games AS g
JOIN claims AS c ON c.platform=g.platform
                AND c.base_source_ordinal=g.source_ordinal
WHERE c.resolution_status='matched'
  AND g.title LIKE '%Mario%'
ORDER BY g.platform,g.title,c.field
LIMIT 100;
```

Querying the `claims` table without the matched filter exposes all disagreements and incomplete source statements. The `games.source_fields_json` and `media.source_fields_json` columns retain all imported upstream fields, so normalization never discards information.

## Reproducibility, integrity, and limitations

The exporter verifies the pinned distribution manifest and SHA-256 digests of **all** input indexes before building; refuses mismatched source revisions and invalid claim-to-record associations; stores all resolution categories without coercing them into accepted joins; uses stable platform/observation ordering; and writes to a temporary file before atomically replacing the target.

The `--verify` command runs SQLite integrity and foreign-key checks and compares aggregate record/media/claim totals against the immutable catalog and field-coverage report. GitHub Actions also exercises a real title lookup and publishes checksums. Unit tests prove deterministic rebuilds, exact field attribution, unresolved-claim preservation, and failure on tampered input.

The title query is literal substring search across source-record names. Exact SHA-1 lookup returns source observations matching the source media representation. Neither establishes a unique underlying work or independently authenticates publishers, dates or genres. The separate [curated identity model](IDENTITIES.md) is optional editorial analysis, not a gate for access to the corpus.

Source licenses and metadata rights **do not become MIT-licensed** merely because the importer code is MIT. Consult the embedded `rights_notice`, source registry metadata and [licensing documentation](LICENSING.md). The database contains no game ROMs, firmware, cheat data or image assets.

## Scaling principle

Bulk source ingestion, bibliographic attribution and indexed consumer delivery operate on **every record**. Manually selected game examples are regression fixtures only. The work/release/build identity-resolution research remains a separate unresolved layer; it must not delay publication or access to metadata already available for the full corpus.

Improving the collection means expanding independently sourced, rights-reviewed metadata and bulk reconciliations with quantified coverage and discrepancy rates - **not** manually processing one game at a time.
