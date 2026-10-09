# Data compatibility and migration

Ludographium publishes offline-readable, source-attributed video game metadata. The [first public dataset release](https://github.com/sguzman/ludographium/releases/tag/data-v1.0.0) freezes a particular collection of records independently of its Rust reader and of future changes to this repository. Consumers should **pin a dataset tag and verify the downloaded bytes** rather than assume that the current default branch is a stable dataset revision.

## Four independent identities

| Identifier | What it versions | What it does not imply |
| --- | --- | --- |
| Dataset release (e.g. `data-v1.0.0`) | One published collection of generated metadata and attribution files | A Rust crate version, a ROM compatibility guarantee, or a unique count of games |
| JSON `schema_version` | The serialized contract of an individual catalog or distribution manifest | That records or upstream assertions have stayed unchanged |
| Rust crate version (currently `0.1.0`) | API and CLI software implementation | The provenance revision or release of the metadata on disk |
| `source_id`, `source_revision`, source-blob SHA | The original upstream snapshot and each source occurrence | A permanent work/release/build identity |

New data may be published against the same JSON schema without changing the Rust client version. Conversely, compatible Rust reader changes need not change the data. Consumer implementations must check each dimension separately.

## Getting an exact dataset

On Linux, download both assets from a specific [GitHub Release](https://github.com/sguzman/ludographium/releases), then check the archive's SHA-256 before extraction. Here is the first release:

```sh
tag=data-v1.0.0
base="https://github.com/sguzman/ludographium/releases/download/$tag"
curl -fL --retry 3 -o "ludographium-runtime-$tag.tar.gz" "$base/ludographium-runtime-$tag.tar.gz"
curl -fL --retry 3 -o "ludographium-runtime-$tag.tar.gz.sha256" "$base/ludographium-runtime-$tag.tar.gz.sha256"
sha256sum -c "ludographium-runtime-$tag.tar.gz.sha256"
mkdir -p "$HOME/.local/share/ludographium/$tag"
tar -xzf "ludographium-runtime-$tag.tar.gz" -C "$HOME/.local/share/ludographium/$tag"
```

The checksum must come from a release reference the consumer already trusts; a matching checksum downloaded alongside a compromised archive is not an independent authenticity guarantee. Checksums are **not signed attestations**. Retain the release tag, Git commit, source revision, and archive SHA-256 in the consuming application's lockfile or audit log. Never select an unversioned release URL for a reproducible pipeline.

After extraction, the directory is a valid Ludographium runtime root for the Rust reader (using `--root`). The Rust CLI can audit every declared file in the extracted distribution without the original DATs:

```sh
cargo run --locked -p ludographium -- --verify-runtime --root "$HOME/.local/share/ludographium/$tag"
```

This command verifies the complete artifact inventory, SHA-256 digests, declared sizes, platform references, and source revision; it rejects missing, modified, or symlinked artifacts. It validates the runtime **against the included manifest**, not the authenticity of that manifest. Always verify the release archive checksum from a trusted reference first.

The runtime contains `generated/v1/distribution.json`, which declares sizes and SHA-256 digests for each included artifact, plus `METADATA-NOTICE.md` and the source registers. The archive contains no ROMs, firmware, binaries, or original source DAT archives.

## Consumer rules for the v1 contract

- **Preserve provenance.** Source occurrence identity uses `source_id`, `source_revision`, `source_path`, and `source_ordinal`, with the source blob SHA as an integrity anchor. Title strings, serials, and source ordinals do not by themselves define a stable canonical game identity.
- **Treat enrichment as claims.** Developers, publishers, dates, genres, and other fields are source assertions with resolution evidence. Unresolved or divergent claims must not silently become canonical values.
- **Keep media bytes explicit.** Exact SHA-1 and byte length associate a source record with the input representation. CRC32 plus byte length is weaker and can return multiple candidates. Explicit [byte-domain conversion](BYTE-DOMAINS.md) is available for selected formats; do not infer conversions from filename extensions or modify stored media.
- **Expect incompleteness.** A missing fingerprint or metadata field does not prove the game does not exist. Most source observations have no curated work/release/build identity yet.
- **Verify every loaded artifact.** Use `generated/v1/distribution.json` and the reader's integrity checks before displaying data. Reject unsupported major schemas rather than interpreting unknown structures as the v1 contract. Preserve unrecognized optional source claims when passing data through other tools.

The v1 archive paths include ten platform observation bundles under `generated/v1/`, ten bibliographic claim bundles under `generated/enrichment-v1/`, a curated identity projection, two source registers, and a self-contained attribution notice. Platform identifiers are defined by the committed catalog manifest and should be enumerated from there rather than inferred from hardcoded names.

## Upgrading to a later release

1. Download the new **specific tag** and verify its checksum and internal distribution manifest.
2. Compare the declared schema versions, source identities, source revisions, platform list, and per-artifact digests. Changed digests mean changed bytes, even if the schema version is identical.
3. Load the new data in an isolated runtime root and rerun known fingerprint/title/enrichment checks. Do not automatically merge new source occurrences into old curated IDs on the strength of matching names or CRC32.
4. Migrate the consuming application's pin only after its compatibility checks pass. Preserve the old runtime root to allow rollback without replacing or modifying source records.

Dataset versioning follows the policy in [release documentation](RELEASING.md): major for breaking consumer semantics, minor for compatible expansion, patch for compatible data correction. A patch or minor release **may change metadata values or source identities**; stable binary format does not imply stable facts. Each published tag and its assets are intended to remain immutable. Public tags must never be repointed to a newer commit.

## Migrating from a checkout or CI artifact

Applications currently opening the repository working tree can instead extract a pinned runtime release and pass its extraction directory as `--root`. Applications using short-lived GitHub Actions artifacts should switch to the tagged GitHub Release assets. The Rust reader requires the generated manifest and its referenced data files, not the original DAT archive, build scripts, or development tests.

The release archive is metadata-only. Runtime lookup, title discovery, enriched claims, and explicitly requested byte conversions retain their existing source-evidence semantics. Consumers must still use the correct file or decoded ZIP-member byte representation for fingerprint matching.
