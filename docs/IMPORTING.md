# Importing and validating sources

The initial accession uses the files registered in [`sources/libretro-no-intro.json`](../sources/libretro-no-intro.json). Their raw DAT bytes are preserved under `archive/libretro-no-intro/` and can be re-imported without fetching anything from the network.

## Rebuild a platform

From the repository root:

```sh
python3 tools/import_dat.py \
  --source sources/libretro-no-intro.json \
  --platform gb \
  --dat archive/libretro-no-intro/gb.dat \
  --output generated/v1/gb.json
```

Substitute `snes`, `gbc`, `gba`, `nes`, or `nds` for `gb` to rebuild the other current exports.

The importer checks the raw DAT against the expected Git blob SHA before producing JSON. The Git blob identity is computed as SHA-1 over the bytes `blob <byte-count>\0<original-file-bytes>`; it is different from SHA-1 of the DAT file alone.

## Validate the collection

```sh
python3 -m unittest discover -s tests -v
python3 tools/verify_catalog.py
python3 tools/build_distribution.py --check
python3 tools/audit_catalog.py --check
python3 tools/import_enrichment.py --check
python3 tools/audit_enrichment.py --check
python3 tools/validate_curated.py
```

The verification command reimports all six archived identification DATs, compares the generated JSON bytes with the committed artifacts, and checks each input/output Git blob SHA and manifest count. The tests cover parser and lookup behavior, including checksum validation and ambiguous CRC32 matches. The distribution check validates SHA-256 digests, while the source audit checks metadata field counts and repeated identifiers against the committed report.

The entire identification catalog can be reconstructed with `python3 tools/rebuild_catalog.py --write`. The `tools/fetch_pinned_sources.py` helper retrieves missing, revision-pinned original metadata files and checks their Git blob identities. Existing source files are never silently replaced.

## Identifying a locally held game image

The read-only Rust CLI accepts `--file /path/to/image` as an alternative to `--sha1` or `--crc32 --size`. Local file content is streamed for SHA-1 comparison; it is not archived, uploaded, or otherwise stored. A raw file representation that differs from the pinned source DAT (for example, a byte-swapped Nintendo 64 image, copier header, or ZIP container) will not necessarily match. The catalog does not silently transform inputs.

## Distributing runtime metadata

The [packager](../tools/package_runtime.py) verifies every file against the SHA-256 distribution manifest before creating a normalized runtime tarball. The archive contains only the portable `generated/` metadata and has deterministic file ordering, permissions, timestamps, and gzip header.

```sh
python3 tools/package_runtime.py --build /tmp/ludographium-runtime-v1.tar.gz
python3 tools/package_runtime.py --verify /tmp/ludographium-runtime-v1.tar.gz
```

Consumers can extract this tarball and set the extracted directory as their catalog root.

## Adding or updating a source

1. Evaluate authorship, coverage, distribution method, and reuse conditions; see [source evaluation](SOURCE-STRATEGY.md).
2. Register the immutable revision, source paths, blob hashes, declared version and collection date in `sources/`.
3. Preserve the original metadata files where redistribution is permitted. Record any omissions or transformations.
4. Import records with loss detection, stable source locators and deterministic output formatting.
5. Update the catalog manifest and run the tests and integrity verifier.
6. Review changes to public contracts and documentation before committing.

The base importer handles the No-Intro-derived DATs. The separately registered [Libretro bibliographic sources](../sources/libretro-enrichment.json) are processed by `tools/import_enrichment.py` from the original files under `archive/libretro-enrichment/`.

To update the bibliographic collection, rebuild its indexes with `python3 tools/import_enrichment.py --write`, then regenerate the quality report with `python3 tools/audit_enrichment.py --write` and the distribution manifest with `python3 tools/build_distribution.py --write`. Commit the related source registers, raw files, generated indexes, reports, and manifest as one coherent accession.

Other source formats require independently audited parsers and source-specific mappings.

## What import results mean

Successful import establishes fidelity to the pinned DAT input, not independent verification of its claims. The exports preserve upstream names, dates, serials and media fingerprints as observations. Curated game identities will be an additional layer.
