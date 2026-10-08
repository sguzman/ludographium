# Importing and validating sources

The initial accession uses the files registered in [\`sources/libretro-no-intro.json\`](../sources/libretro-no-intro.json). Their raw DAT bytes are preserved under \`archive/libretro-no-intro/\` and can be re-imported without fetching anything from the network.

## Rebuild a platform

From the repository root:

\`\`\`sh
python3 tools/import_dat.py \
  --source sources/libretro-no-intro.json \
  --platform gb \
  --dat archive/libretro-no-intro/gb.dat \
  --output generated/v1/gb.json
\`\`\`

Substitute \`snes\`, \`gbc\`, or \`gba\` for \`gb\` to rebuild the other current exports.

The importer checks the raw DAT against the expected Git blob SHA before producing JSON. The Git blob identity is computed as SHA-1 over the bytes \`blob <byte-count>\0<original-file-bytes>\`; it is different from SHA-1 of the DAT file alone.

## Validate the collection

\`\`\`sh
python3 -m unittest discover -s tests -v
python3 tools/verify_catalog.py
\`\`\`

The verification command reimports all four archived DATs, compares the generated JSON bytes with the committed artifacts, and checks each input/output Git blob SHA and manifest count. The tests cover parser and lookup behavior, including checksum validation and ambiguous CRC32 matches.

## Adding or updating a source

1. Evaluate authorship, coverage, distribution method, and reuse conditions; see [source evaluation](SOURCE-STRATEGY.md).
2. Register the immutable revision, source paths, blob hashes, declared version and collection date in \`sources/\`.
3. Preserve the original metadata files where redistribution is permitted. Record any omissions or transformations.
4. Import records with loss detection, stable source locators and deterministic output formatting.
5. Update the catalog manifest and run the tests and integrity verifier.
6. Review changes to public contracts and documentation before committing.

The present importer accepts the clrmamepro-style DAT syntax used by the pinned No-Intro-derived files. Other source formats require their own audited parser and source-specific mapping.

## What import results mean

Successful import establishes fidelity to the pinned DAT input, not independent verification of its claims. The exports preserve upstream names, dates, serials and media fingerprints as observations. Curated game identities will be an additional layer.
