# Publishing metadata releases

Ludographium's portable metadata archive can be distributed independently of the source repository or the Rust client. Releases are frozen snapshots of the distribution manifest and its validated data files. They are not replacements for the preserved source archive.

## Release identity

Dataset releases use Git tags such as `data-v1.0.0`. These versions identify the released **dataset snapshot**, separately from the Rust crate version and the JSON schema version. The major component changes when consumer compatibility requires a breaking transition; minor versions can add supported metadata and compatible records; patch versions can repair or revise data without changing its published shape. The tag identifies the precise Git revision from which the assets were built.

A new release must use a new tag; do not move or reuse a published data tag. Historical releases remain independently retrievable through [GitHub Releases](https://github.com/sguzman/ludographium/releases). A GitHub release is durable relative to expiring CI artifacts, but repository administrators can still delete or replace assets and tags. Hashes detect accidental or malicious byte changes when compared with a trusted reference; they are not signatures.

## Publishing

The [versioned release workflow](../.github/workflows/release.yml) responds only to a newly pushed `data-vMAJOR.MINOR.PATCH` tag pointing to a commit on `main` history. It reruns Python, Rust, source-provenance, manifest, curated-identity, and documentation checks. Only after all checks pass does it publish a GitHub Release with a versioned runtime archive, its SHA-256 checksum file, and source-revision/rights notes. The publishing job has the only `contents: write` permission.

Maintainers should inspect the current `main` CI results and data/source rights before creating a tag. The workflow is deliberately not automatic on every `main` push. A failed publication should be diagnosed and rerun at the *same verified commit*; it must not be fixed by silently repointing a public tag. The workflow rejects malformed tags and tags outside `main` history. It does not publish prereleases.

The release assets can also be staged entirely offline from a checkout at that commit:

```sh
python3 tools/prepare_release.py --tag data-v1.0.0 --output /tmp/ludographium-release
cd /tmp/ludographium-release
sha256sum -c ludographium-runtime-data-v1.0.0.tar.gz.sha256
```

The version here illustrates syntax; staging locally does **not** create a GitHub Release. Use the exact desired tag in both commands. The underlying packager checks the per-artifact SHA-256 distribution manifest and builds a deterministic tarball. No ROMs, firmware, original DAT archives, or third-party artwork are included. Source attribution and licensing notices travel with every runtime archive.

## Consumer guarantees

Consumers should pin a specific data tag rather than following a mutable `main` branch or an expiring Actions artifact. Check the companion `.sha256` checksum against the downloaded tarball and retain the exact tag/commit identity in downstream provenance. The extracted `generated/v1/distribution.json` provides SHA-256 hashes for individual metadata files. Source claims and curated identities are not interchangeable; consult the [consumer guide](CONSUMERS.md) for those contracts.
