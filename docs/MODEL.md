# Data model

Ludographium separates **what a source says** from **how the catalog interprets it**. The first implemented layer is an immutable-snapshot-based source index; curated work, release, and build identities are planned.

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

## Curated identity model (planned)

- **Work:** a stable identity for an underlying game.
- **Release:** a platform, region, edition, and publication identity associated with a work.
- **Build/media variant:** a concrete content revision or media manifest associated with a release.
- **Assertion:** a sourced field value, its evidence locator, and its resolution or verification state.
- **Asset reference:** optional metadata pointing to media with separately reviewed rights.

Curated records will retain source assertions and their disagreements. A reconciliation decision will include supporting evidence and its confidence or verification status; it will not rewrite the imported snapshot.

The distinction between `imported`, `corroborated`, `manually-verified`, `disputed`, and `unknown` is reserved for future curated assertions. **No such verification status is currently claimed by the source indexes.**

## Versioning

`schema_version: 1` describes the current source-index structure. Fields may be added compatibly; breaking changes will require a new major schema and migration guidance. Source data can change when a newer upstream snapshot is accessioned, independent of the schema version.
