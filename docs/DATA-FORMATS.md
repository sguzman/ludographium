# Source data and generated database policy

Ludographium is a source-data repository. **Versioned, attributed, human-reviewable text is canonical; SQLite is an optional derived local index.** This boundary applies to Git history and to new public dataset publications.

- Original source evidence and stable claims belong in `.json`, `.jsonl`, CSV/TSV, or native documented text formats, split by collection when appropriate.
- Do **not** commit `.sqlite`, `.sqlite3`, `.db`, generated binary indexes, or multi-hundred-megabyte dumps to Git.
- Large SQLite materializations may be built in temporary CI directories to check query behavior or regenerated locally by downstream clients, but **must not be uploaded as new GitHub Release assets or CI artifacts** by default.
- New release assets should be text-first and provenance-preserving. Versioned source snapshots must have SHA-256 checksums. Avoid unnecessary duplicated formats and keep download sizes justified by actual consumption.
- Existing tagged releases, including historical SQLite companions through `data-v1.6.0`, remain intact so published consumer links are not broken. This is a policy for future publications, not retroactive alteration of immutable releases.

## Wikidata source corpus

The first pinned independent Wikidata source is now stored as **16 small, plain-text JSONL files** under [`data/wikidata/v1/`](../data/wikidata/v1/), plus a text [manifest](../data/wikidata/v1/manifest.json). The 15,868 item/platform observations, English labels, and all captured date statements are readable and diffable in Git. The entire committed text projection is approximately 4.2 MB, compared with the 189.8 MB historical SQLite companion.

The manifest retains the origin snapshot SHA-256, query-response digests, original platform QIDs and acquisition timestamps. The [source snapshot from `data-v1.6.0`](https://github.com/sguzman/ludographium/releases/download/data-v1.6.0/ludographium-wikidata-source-data-v1.6.0.json) is independently readable JSON, not a binary database, and remains available to reproduce the text projection.

`tools/export_wikidata_text.py` regenerates or verifies those 16 JSONL files from that immutable snapshot, and CI checks that the source projection fits under 5 MB and contains no binary files. The source data are independent claims, not confirmed correspondences or canonical game identities.

The importer and SQLite tools remain usable for **optional local, transient indexing**. They are not the primary collected data format and do not justify storing a 190 MB database in the source repository or distributing one unrequested.
