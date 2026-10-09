# Data model

Ludographium separates **what a source says** from **how the catalog interprets it**. Identification and bibliographic source indexes are implemented; curated work, release, and build identities have a validated ledger with fifteen source-grounded works, seventeen releases, and twenty-eight exact media builds.

## Source observations: v1

The current per-platform exports are `generated/v1/<platform>.json`. Each is a JSON object with the following fields:

| Field | Description |
| --- | --- |
| `schema_version` | Integer `1` |
| `kind` | `source-observations` |
| `platform` | Platform identifier, such as `gb` |
| `source_id`, `source_revision` | Source identity and pinned repository commit |
| `source_path`, `source_blob_sha` | Upstream DAT path and Git blob SHA |
| `source_license` | License declared in the source register |
| `dat_version` | DAT header version, when present |
| `record_count`, `rom_count` | Counts of imported source records and media entries |
| `records` | Ordered source observations |

Each element of `records` contains a one-based `source_ordinal`, the source's `name`, and a `roms` array. Available scalar attributes such as `region`, `serial`, `description`, `releaseyear`, `releasemonth`, and `releaseday` are retained as provided by the upstream DAT. A ROM entry preserves its source filename, integer `size`, and available `crc32`, `md5`, `sha1`, or `serial`.

The importer preserves source values rather than interpreting them as facts about all territories or editions. For example, a `region` value of `USA` on a multi-territory title is one upstream field, not an exhaustive map of release regions. Optional values may be absent; the importer does not synthesize missing dates or identifiers.

Records are neither merged nor deduplicated by name, checksum, or serial. The importer rejects unsupported syntax, and the archived DAT remains the original evidence.

## Source occurrence identity

The tuple

```text
(source_id, source_revision, source_path, source_ordinal)
```

locates an occurrence within one source snapshot. It is **not** a permanent identifier for a game. An upstream update may reorder records; canonical game identifiers must survive such changes.

The per-platform [catalog manifest](../generated/v1/catalog.json) records the source revision, counts, input archive paths and Git blob SHAs, and generated artifact paths and Git blob SHAs.

## Bibliographic claim model: enrichment-v1

The `generated/enrichment-v1/<platform>.json` files preserve developer, publisher, release-year, release-month, genre, franchise, serial, ESRB rating, player count, and rumble-support claims from the pinned Libretro bibliographic DATs. Each claim carries its field name and value, original CRC32, source-title comment, file path, blob SHA, ordinal, all original parsed `source_fields`, and resolution status. The enclosing enrichment bundle records the source ID and revision, both exposed by read-only consumers.

Quoted and unquoted single-token source values remain source strings; counts and hardware flags are not silently interpreted as verified game properties. The Rust consumer can compute raw SHA-1 from an in-memory byte slice or streamed local file. Exact-byte matching remains the default; a separate, explicitly requested [byte-domain conversion](BYTE-DOMAINS.md) supports limited NES, SNES, and N64 representations without source-record editing.

A claim is attached to a base observation only when a CRC32 has exactly one candidate and the metadata comment exactly matches that source record's title. Other observations remain unresolved with an explicit reason: `comment_mismatch`, `unmatched_crc`, `missing_comment`, `missing_value`, or `ambiguous_crc`. This is a match between source records, not verification of bibliographic facts.

See the [enrichment coverage report](../reports/enrichment-coverage-v1.json) and the [offline consumer guide](CONSUMERS.md).

## Curated identity model

- **Work:** a stable identity for an underlying game.
- **Release:** a platform, region, edition, and publication identity associated with a work.
- **Build/media variant:** a concrete content revision or media manifest associated with a release.
- **Assertion:** a sourced field value, its evidence locator, and its resolution or verification state.
- **Asset reference:** optional metadata pointing to media with separately reviewed rights.

Curated records will retain source assertions and their disagreements. A reconciliation decision will include supporting evidence and its confidence or verification status; it will not rewrite the imported snapshot.

The [identity ledger](../curated/v1/identities.json) currently contains fifteen reviewed works, seventeen release labels, and twenty-eight exact media builds. The expansion documents same-platform revision relationships while preserving distinct regional releases when the source territory labels differ. Most source observations remain uncurated. Its [identity rules](IDENTITIES.md) validate opaque UUIDv4 IDs, supporting source occurrences, and release/build parent relationships.

## Versioning

`schema_version: 1` describes the current source-index structure. Fields may be added compatibly; breaking changes will require a new major schema and migration guidance. Source data can change when a newer upstream snapshot is accessioned, independent of the schema version.
