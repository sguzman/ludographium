# Data model: first collection

## Source observations (implemented first)

Each import is one pinned **source snapshot**, grouped by platform. The current `source-observations-v1` envelope contains:

- `schema_version` = 1, `kind` = `source-observations`.
- `platform`, `source_id`, `source_revision`, `source_path`, `source_blob_sha`.
- `dat_version`: descriptive upstream metadata, not a substitute for the pinned Git revision.
- `records`: an ordered list of source game blocks, preserving their title and source ordinal.
- Each record: `source_ordinal`, `name`, optional `description` / `region` / `serial` and `roms` array.
- Each ROM: original name, size, CRC32, MD5, SHA-1, optional serial; all are **assertions in the source**.

Records are *not* deduplicated by title, hash or serial. Unrecognized fields must be recorded or rejected explicitly by the importer, not silently discarded. The source snapshot can be retrieved by exact upstream revision and path. For auditability, we also keep the untouched input in `archive/` when source terms permit.

**No invented data:** absent values are omitted/null, never inferred as a release date, region, locale or truth of compatibility. In particular a `region` field of `USA` in a multi-region title is not a reliable list of all release territories.

## Planned curated entities

These are **not** implied by the first import:

1. **Work:** an intentionally resolved underlying game, with stable Ludographium ID.
2. **Release:** a platform/territory/language/publication identity, distinct from other regional or edition releases.
3. **Build:** a particular revision/variant, disc or media manifest, with multiple possible hashes/identifiers.
4. **Assertion:** a value plus source, locator, license, collection date, verification type and any conflicting assertions.
5. **Assets:** optional references to identified, correctly licensed artwork or other media.

A bridge can connect source-observation records to a curated release or build only with cited evidence and explicit resolution state. Do not create canonical IDs merely by stripping parenthetical qualifiers from filenames.

## Source conflict treatment

Conflicting assertions coexist as claims. A curated record may choose a value if evidence supports it and it records *why*; it never alters archived inputs. We distinguish `imported`, `corroborated`, `manually-verified`, `disputed` and `unknown` states as future evidence quality values. Importing a checksum is not the same as personally re-dumping or executing a game.

## Stable IDs

`source_id + source_revision + source_path + source_ordinal` identifies an occurrence in **one snapshot**, not a durable game. Future stable work/release/build IDs live in curated records and survive upstream reordering. Never use a name or a content hash alone as a canonical work ID.
