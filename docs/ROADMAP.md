# Roadmap

Ludographium is growing from a source-faithful identification index into a catalog of distinct works, releases, and media variants with documented evidence. The roadmap separates completed infrastructure from planned expansion.

## Source foundation

- [x] Define the catalog's scope and layered identity model.
- [x] Register an immutable Libretro / No-Intro-derived source snapshot.
- [x] Preserve original source DATs for ten Nintendo and Sega platforms.
- [x] Generate deterministic source-observation JSON for all ten platforms.
- [x] Validate imports, source identities, generated outputs, and counts.
- [x] Provide a basic offline SHA-1 and CRC32 lookup utility.
- [x] Provide exact raw-byte SHA-1 streaming lookup for local files and in-memory emulator data.
- [x] Identify stored and Deflate-compressed ZIP members with bounded, read-only streaming.
- [x] Provide bounded source-title discovery in both Rust and Python, including attributed enrichment.
- [x] Support dynamic cross-platform fingerprint, stream, and title lookup through the Rust CLI and library.
- [x] Publish reproducible per-platform field-coverage and repeated-fingerprint audits.
- [ ] Complete source-specific redistribution review for future providers.

## Bulk metadata coverage

- [x] Assemble a ten-platform source-observation catalog and preserve original metadata and media fingerprints.
- [x] Materialize a complete, queryable SQLite export of every source record, media entry and bibliographic field claim, including all unresolved associations.
- [x] Validate aggregate coverage, full input-source integrity, exact claim attachments and deterministic source-to-SQLite transformation.
- [x] Deliver the complete SQLite corpus as a CI artifact, independently of optional manually curated identity examples.
- [x] Expand the source universe from ten to 75 console/handheld collections by pinned file-level bulk import, preserving every original DAT inside offline SQLite.
- [x] Accession 279 additional pinned Libretro bibliographic DAT sources in one batch, explicitly retaining checksums, source values and unresolved claims.
- [x] Integrate and permanently publish a SHA-256-locked CC0 Wikidata source snapshot in `data-v1.6.0`, across 16 whole-platform queries, with 15,868 item/platform observations and 29,333 literal date claims.
- [x] Bulk-generate 8,971 noncanonical title correspondence candidates and identify 126 ambiguous links without merging game identities.
- [ ] Add more external metadata properties/providers and evidence-backed cross-provider reconciliation beyond label correspondences; quantify false-positive risk.
- [x] Publish a durable, versioned SQLite companion for downstream offline consumers (`data-v1.4.0`).

## Identity and curation

- [x] Establish evidence-validated UUID identifiers for work, release, and build records.
- [x] Curate source-grounded work/release/build identities, including independently hashed regional and revision records across Game Boy, Color, Advance, Nintendo DS, Master System and Game Gear.
- [ ] Develop a corpus-wide evidence-based candidate-identity pipeline with explicit uncertainty, stable identifiers and exception-only review. The selected curated examples remain validation fixtures; serial game-by-game curation is not the production workflow.
- [x] Provide conservative, provenance-preserving revision candidate discovery without generating canonical relationships.
- [x] Reject conflicting work/release ownership of a source occurrence during curation validation.
- [x] Verify the same parent-evidence and ownership invariants in the Rust offline reader.
- [x] Audit curated media against separately attributed field-DAT claims and prioritize revision leads by field-claim availability without auto-curation.
- [x] Preserve prior exact-revision curation as test fixtures without making manually reviewed entries a prerequisite to metadata ingestion.
- [ ] Reconcile localized titles, regional editions, revisions, and independent provider identifiers.
- [ ] Preserve conflicting assertions and editorial resolution evidence.
- [ ] Establish evidence-based correspondences with external game metadata collections.
- [x] Expand the catalog to ten systems, including NES, DS, N64, Genesis, Master System, and Game Gear.
- [x] Bulk expand to 75 source collections from the same pinned upstream revision, with verifiable source snapshot hashes.
- [ ] Accession additional independently sourced systems after rights/source review.

## Distribution and consumers

- [x] Publish deterministic per-artifact SHA-256 digests and byte lengths in a distribution manifest.
- [x] Provide a v0.1 Rust read-only client and CLI with integrity-checked exact-fingerprint lookup.
- [x] Build and CI-verify a metadata-only, reproducible runtime archive.
- [x] Include validated curated identities in the portable integrity manifest and runtime archive.
- [x] Implement a tag-gated, fully validated release workflow with checksum-verified, versioned runtime assets.
- [x] Publish the first versioned GitHub data release (`data-v1.0.0`), independent of short-lived CI artifacts.
- [x] Specify and test opt-in NES iNES, SNES copier-header, and N64 byte-order conversions without mutating source data.
- [x] Support explicit normalized ZIP member lookup with decoded-size limits and source-aware Rust APIs.
- [ ] Expand byte-domain contracts to additional vetted format variants and trainer handling where justified.
- [x] Publish data-version compatibility and migration guidance for consumers.
- [x] Provide an offline, whole-runtime integrity audit that detects missing, modified, or symlinked artifacts.

## Bibliographic enrichment

- [x] Accession 88 pinned Libretro field-metadata DATs spanning developer, publisher, date, genre, franchise, serial, age rating, player count, and rumble.
- [x] Implement conservative claim resolution, coverage reports, and integrity-checked Rust/Python access.
- [x] Publish deterministic discrepancy groups for targeted source reconciliation.
- [ ] Expand to localized titles, richer dates, and independently sourced company credits as reuse permits.
- [ ] Curate source corrections without modifying original archives.
- [ ] Introduce an attributed art-reference catalog with rights metadata.
- [ ] Support incremental source refreshes and reproducible index releases.

Current data counts and usage examples are maintained in the [README](../README.md). Implementation history lives in Git commits.
