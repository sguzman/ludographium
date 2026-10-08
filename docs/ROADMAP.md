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
- [x] Provide bounded source-title discovery in both Rust and Python, including attributed enrichment.
- [x] Publish reproducible per-platform field-coverage and repeated-fingerprint audits.
- [ ] Complete source-specific redistribution review for future providers.

## Identity and curation

- [x] Establish evidence-validated UUID identifiers for work, release, and build records.
- [x] Curate initial source-grounded work/release/build identity examples with exact media evidence.
- [ ] Expand curated identities and evidence-backed correspondences across editions and providers.
- [ ] Reconcile localized titles, regional editions, revisions, and independent provider identifiers.
- [ ] Preserve conflicting assertions and editorial resolution evidence.
- [ ] Establish evidence-based correspondences with external game metadata collections.
- [x] Expand the catalog to ten systems, including NES, DS, N64, Genesis, Master System, and Game Gear.
- [ ] Expand to additional consoles and handhelds with audited source snapshots.

## Distribution and consumers

- [x] Publish deterministic per-artifact SHA-256 digests and byte lengths in a distribution manifest.
- [x] Provide a v0.1 Rust read-only client and CLI with integrity-checked exact-fingerprint lookup.
- [x] Build and CI-verify a metadata-only, reproducible runtime archive.
- [x] Include validated curated identities in the portable integrity manifest and runtime archive.
- [ ] Publish permanent versioned data releases, independent of short-lived CI artifacts.
- [ ] Specify and test platform-specific byte-domain and header normalization rules.
- [ ] Publish compatibility and migration guidance for future consumer contracts.

## Bibliographic enrichment

- [x] Accession 88 pinned Libretro field-metadata DATs spanning developer, publisher, date, genre, franchise, serial, age rating, player count, and rumble.
- [x] Implement conservative claim resolution, coverage reports, and integrity-checked Rust/Python access.
- [x] Publish deterministic discrepancy groups for targeted source reconciliation.
- [ ] Expand to localized titles, richer dates, and independently sourced company credits as reuse permits.
- [ ] Curate source corrections without modifying original archives.
- [ ] Introduce an attributed art-reference catalog with rights metadata.
- [ ] Support incremental source refreshes and reproducible index releases.

Current data counts and usage examples are maintained in the [README](../README.md). Implementation history lives in Git commits.
