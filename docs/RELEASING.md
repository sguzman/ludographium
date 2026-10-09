# Publishing metadata releases

Ludographium's portable metadata archive can be distributed independently of the source repository or the Rust client. Releases are frozen snapshots of the distribution manifest and its validated data files. They are not replacements for the preserved source archive.

## Release identity

Dataset releases use Git tags such as `data-v1.0.0`. These versions identify the released **dataset snapshot**, separately from the Rust crate version and the JSON schema version. The major component changes when consumer compatibility requires a breaking transition; minor versions can add supported metadata and compatible records; patch versions can repair or revise data without changing its published shape. The tag identifies the precise Git revision from which the assets were built.

A new release must use a new tag; do not move or reuse a published data tag. Historical releases remain independently retrievable through [GitHub Releases](https://github.com/sguzman/ludographium/releases). A GitHub release is durable relative to expiring CI artifacts, but repository administrators can still delete or replace assets and tags. Hashes detect accidental or malicious byte changes when compared with a trusted reference; they are not signatures.

## Publishing

The [versioned release workflow](../.github/workflows/release.yml) supports two explicit publication routes:

1. **Release request on main.** Change `.github/data-release.json` to contain a new dataset tag (for example `{"schema_version":1,"tag":"data-v1.0.0"}`). Only a change to that exact file on `main` starts the request-based publisher. The requested tag is validated, all metadata and software checks rerun, and the workflow publishes a GitHub Release while creating an unmoved tag at the exact verified commit. A tag or release that already exists cannot be overwritten.
2. **Existing tag.** Push a new `data-vMAJOR.MINOR.PATCH` tag pointing to a commit on `main` history. The same validation and packaging checks run; publication requires that the tag exists rather than creating one.

Both routes validate Python, Rust, source provenance, manifests, curated identities, and documentation before uploading a versioned runtime archive, SHA-256 checksum file, and source-revision/rights notes. New releases also retain the verified Wikidata source snapshot as readable JSON, **not** the large generated SQLite indexes. Text/JSONL in Git is the primary collected dataset; SQLite is reproducible locally when a consumer needs it. Only the publish job gets `contents: write` permission. The workflow is **not** invoked on ordinary `main` commits: a release request file change or a new data tag is required.

Review licensing and successful `main` CI before initiating a release. If publication fails, investigate and rerun the *same immutable revision* rather than moving an existing tag or replacing release assets. New dataset versions get new tags. Neither route publishes prereleases.

The generated-database boundary is documented in [source data and formats](DATA-FORMATS.md). Existing SQLite attachments in releases through `data-v1.6.0` remain intact rather than breaking old consumer URLs.

The release assets can also be staged entirely offline from a checkout at that commit:

```sh
python3 tools/prepare_release.py --tag data-v1.0.0 --output /tmp/ludographium-release
cd /tmp/ludographium-release
sha256sum -c ludographium-runtime-data-v1.0.0.tar.gz.sha256
```

The version here illustrates syntax; staging locally does **not** create a GitHub Release. Use the exact desired tag in both commands. The underlying packager checks the per-artifact SHA-256 distribution manifest and builds a deterministic tarball. No ROMs, firmware, original DAT archives, or third-party artwork are included. Source attribution and licensing notices travel with every runtime archive.

## Consumer guarantees

Consumers should pin a specific data tag rather than following a mutable `main` branch or an expiring Actions artifact. The [release history](DATA-RELEASES.md) distinguishes already published dataset versions. Check the companion `.sha256` checksum against the downloaded tarball and retain the exact tag/commit identity in downstream provenance. The extracted `generated/v1/distribution.json` provides SHA-256 hashes for individual metadata files. Source claims and curated identities are not interchangeable; consult the [consumer guide](CONSUMERS.md) and [compatibility/migration guide](COMPATIBILITY.md) for those contracts.
