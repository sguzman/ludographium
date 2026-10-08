# Consumer guide

Ludographium publishes source-indexed metadata for read-only, offline use by emulator frontends, game-library tools, and related software.

## Available artifacts

The [v1 catalog manifest](../generated/v1/catalog.json) lists the available platform bundles and their input and output Git blob SHAs:

| Platform | Export |
| --- | --- |
| SNES | [`generated/v1/snes.json`](../generated/v1/snes.json) |
| Game Boy | [`generated/v1/gb.json`](../generated/v1/gb.json) |
| Game Boy Color | [`generated/v1/gbc.json`](../generated/v1/gbc.json) |
| Game Boy Advance | [`generated/v1/gba.json`](../generated/v1/gba.json) |
| Nintendo Entertainment System | [`generated/v1/nes.json`](../generated/v1/nes.json) |
| Nintendo DS | [`generated/v1/nds.json`](../generated/v1/nds.json) |
| Nintendo 64 | [`generated/v1/n64.json`](../generated/v1/n64.json) |
| Sega Mega Drive / Genesis | [`generated/v1/genesis.json`](../generated/v1/genesis.json) |
| Sega Master System | [`generated/v1/sms.json`](../generated/v1/sms.json) |
| Sega Game Gear | [`generated/v1/gg.json`](../generated/v1/gg.json) |

Each base bundle contains source observations and fingerprints. Matching [enrichment bundles](../generated/enrichment-v1/) contain attributed bibliographic and technical claims (including publishers, developers, genre, franchise, serial, age rating, player counts, and rumble support), together with unresolved source evidence. Neither is a canonical work/release/build registry. A separate [curated identity index](../generated/curated-v1/identities.json) publishes the deliberately selected work, release, and media-build identifiers.

## Matching a local image

1. Select the matching platform bundle.
2. Compute a fingerprint of the local file's **exact bytes**.
3. Find source entries with the corresponding `roms[].sha1`, or use CRC32 with the file size and inspect all matching entries.
4. Display the source title and available metadata, retaining the exact source locator: `source_id`, `source_revision`, `source_path`, and `source_ordinal`.

A matching digest associates a file with a source record. It does not independently verify provenance, legitimacy, game identity, or emulator compatibility. CRC32 collisions are possible; the lookup CLI deliberately returns every match.

Headers, trimming, byte-swapping, patches, and other transformations can change fingerprints. The current exports have **no platform-specific normalization contract**. Applications should compare known byte representations rather than assuming a particular header-stripping strategy.

## Command-line example

Run from the repository root:

```sh
python3 tools/verify_catalog.py
python3 tools/lookup.py --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

The example resolves to one source observation for `10-Pin Bowling (USA) (Proto)` in the Game Boy DAT. The tool reads committed JSON indexes, not game files. It also supports `--crc32` with the mandatory `--size` byte count.

## Cross-platform identification

If a consumer does not know the console in advance, it can use `--platform all` to search the source manifests in their registered order. The result contains `platforms_searched`, `platform_scope: all-registered`, and each match's actual platform and complete source locator. Ambiguous matches are retained as separate source occurrences, never merged.

```sh
cargo run --locked -p ludographium -- --platform all --sha1 6B47BB75D16514B6A476AA0C73A683A2A4C18765 --curated
cargo run --locked -p ludographium -- --platform all --title "Mario" --limit 5 --enriched
cargo run --locked -p ludographium -- --platform all --file /path/to/a-game
```

The Rust library exposes `CatalogCollection::open(root)` and `EnrichedCatalogCollection::open(root)` with matching `lookup_sha1`, `lookup_crc32`, `lookup_bytes`, `lookup_reader`, and `search_titles` methods. Each collection enumerates the pinned manifest dynamically and verifies the relevant indexes on opening. Raw bytes are fingerprinted **once** for all systems; they are not copied or modified.

Title-search limits apply globally to source records (1–200), not individual media entries. `total_source_records` counts all original title matches across systems before limiting the output. These searches identify source observations, not canonical works. Identity resolution remains an explicit evidence-based step.

## Matching exact local media bytes

Emulator and library consumers can supply an in-memory byte slice through `PlatformCatalog::lookup_bytes`, or a streaming Rust `Read` source through `PlatformCatalog::lookup_reader`. The corresponding methods on `EnrichedPlatformCatalog` preserve the source-attributed bibliographic claims.

For a standalone file on disk, the Rust CLI offers:

```sh
cargo run --locked -p ludographium -- --platform gba --file /path/to/a-game.gba
cargo run --locked -p ludographium -- --enriched --platform gba --file /path/to/a-game.gba
```

This hashes **exactly the supplied bytes** with SHA-1, checks the original file length, and returns all matching source observations. Input is read with bounded memory and is never copied into Ludographium. An unmatched result does not establish that a game is unknown; differing archive compression, copier headers, byte ordering, patches, or other representations can change fingerprints.

This is not a container extractor or a platform-specific byte-normalization layer. Consumers must explicitly choose the byte representation they want to identify. Full ZIP/archive support and verified per-platform normalization rules remain future work.

## Read-only ZIP identification

Use `--zip` to inspect individual members of a ZIP archive without extracting files to disk:

```sh
cargo run --locked -p ludographium -- --platform all --zip /path/to/collection.zip --enriched
cargo run --locked -p ludographium -- --platform gbc --zip /path/to/single-game.zip
```

Each member returns its original archive entry name, SHA-1, byte length, and source matches. Members without matches remain visible. Both `CatalogCollection` and `EnrichedCatalogCollection` expose `lookup_zip` for use in Rust applications.

The reader handles stored and Deflate-compressed ZIP entries. It does not extract, save, patch, strip headers from, or change member bytes. Resource limits are **256 entries**, **1 GiB decoded per member**, and **2 GiB decoded in total**. Unsupported or unreadable entries return an error. ZIP identification does not establish canonical game identity, and the collection never stores game binaries.

Use `--file` for one uncompressed media representation and `--zip` for ZIP members. Other archive formats are not yet supported.

## Discovering source titles

Source-title search is intentionally separate from fingerprint identification. It searches original source title strings, preserving individual edition and revision records and their source provenance.

```sh
cargo run --locked -p ludographium -- --platform nes --title "Mario" --limit 5
cargo run --locked -p ludographium -- --enriched --platform nes --title "Mario" --limit 5
```

Both Rust and Python support bounded, case-insensitive substring title queries (default limit: 50; permitted range: 1–200 records). The response includes `query_kind: source-title-substring`, `total_source_records` before limiting, and the returned `matches`. A record can have multiple media entries, so `match_count` counts displayed media occurrences, while `total_source_records` counts matching source records.

Spelling, accents, and edition annotations remain source-provided. Search is a discovery mechanism, not evidence that titles are synonymous or that records describe the same creative work.

## Bibliographic claims

The Rust `EnrichedPlatformCatalog::open(root, platform)` API verifies the source index and enrichment bundle, then supports `lookup_sha1` and `lookup_crc32`. The CLI uses `--enriched` to return matched `metadata_claims` separately from `unresolved_source_claims`:

```sh
cargo run --locked -p ludographium -- --enriched --platform gba --sha1 FC6163F99B71B05C10686A0D29010B31274E1DC4
```

The Python `tools/lookup_enrichment.py` provides a corresponding offline interface. Both return the enrichment source ID and revision, while individual claims retain their original parsed `source_fields`, source path, Git blob SHA, and source ordinal. Unquoted numeric upstream fields remain strings; consumers may interpret those values separately. Neither interface needs game binaries or original DAT files during lookup.

## Portable runtime distribution

Consumers do not need the repository's original DAT archives or development files. The standard-library packager builds a **deterministic** gzip-compressed tar archive containing only the distribution manifest and its 22 indexed artifacts, including the curated identity export.

```sh
python3 tools/package_runtime.py --build /tmp/ludographium-runtime-v1.tar.gz
python3 tools/package_runtime.py --verify /tmp/ludographium-runtime-v1.tar.gz
mkdir -p /tmp/ludographium-data
tar -xzf /tmp/ludographium-runtime-v1.tar.gz -C /tmp/ludographium-data
cargo run --locked -p ludographium -- --root /tmp/ludographium-data --platform nes --title "Mario" --limit 5
```

Archive entries use their standard `generated/...` paths; the extracted directory is a valid runtime root. Every input file is SHA-256 checked before packaging. File order and archive timestamps are normalized, so the compressed output is byte-for-byte reproducible from a pinned distribution.

Successful [main-branch CI runs](https://github.com/sguzman/ludographium/actions/workflows/validate.yml) attach the archive as `ludographium-runtime-v1` for a limited retention period. CI build artifacts are **not** permanent, versioned releases or cryptographically signed attestations.

## Integrity and compatibility

The [distribution manifest](../generated/v1/distribution.json) contains a byte length and SHA-256 digest for the catalog manifest, ten base JSON bundles, ten enrichment bundles, and a curated identity export. `python3 tools/build_distribution.py --check` checks those records against the committed bytes. `python3 tools/verify_catalog.py` separately re-imports the original archived DATs and checks Git blob identities, generated bytes, and counts.

The Rust crate `crates/ludographium` reads the catalog manifest, the SHA-256 distribution manifest and the requested platform index (plus optional enrichment and curated indexes); it validates both that index's Git blob identity and the declared SHA-256 digest before returning matches. It exposes `PlatformCatalog::open(root, platform)`, `lookup_sha1`, and `lookup_crc32` for offline use and includes a matching CLI:

```sh
cargo run -p ludographium -- --platform gb --sha1 952D154DD2C6189EF4B786AE37BD7887C8CA9037
```

The distribution manifest is not signed; consumers should obtain it from a trusted, pinned Git revision or release. A future independent release packaging process may add signed attestations and publishing guarantees.

Platform identifiers such as `snes`, `gb`, `gbc`, `gba`, `nes`, `nds`, `n64`, `genesis`, `sms`, and `gg` follow the project's registry and are compatible by convention with related datasets. Cross-project game/revision joins should use the curated correspondence and source evidence, not inferred title slugs.

The source-observation v1 format is an early interface. Breaking semantics will be introduced through versioned contracts; unknown or unmatched games remain legitimate lookup results.
