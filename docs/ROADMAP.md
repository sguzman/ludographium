# Roadmap

Ludographium is growing from a source-faithful identification index into a catalog of distinct works, releases, and media variants with documented evidence. The roadmap separates completed infrastructure from planned expansion.

## Source foundation

- [x] Define the catalog's scope and layered identity model.
- [x] Register an immutable Libretro / No-Intro-derived source snapshot.
- [x] Preserve original SNES, GB, GBC, and GBA DAT files.
- [x] Generate deterministic source-observation JSON for all four platforms.
- [x] Validate imports, source identities, generated outputs, and counts.
- [x] Provide a basic offline SHA-1 and CRC32 lookup utility.
- [ ] Complete source-specific redistribution review for future providers.

## Identity and curation

- [ ] Design stable identifiers for game works, releases, and builds.
- [ ] Reconcile localized titles, regional editions, revisions, and independent provider identifiers.
- [ ] Preserve conflicting assertions and editorial resolution evidence.
- [ ] Establish evidence-based correspondences with external game metadata collections.
- [ ] Extend the collection to NES and Nintendo DS, followed by additional systems.

## Distribution and consumers

- [x] Publish deterministic per-artifact SHA-256 digests and byte lengths in a distribution manifest.
- [x] Provide a v0.1 Rust read-only client and CLI with integrity-checked exact-fingerprint lookup.
- [ ] Specify and test platform-specific byte-domain and header normalization rules.
- [ ] Publish compatibility and migration guidance for future consumer contracts.

## Bibliographic enrichment

- [ ] Accession sources for publishers, developers, publication dates and localized titles, as reuse permits.
- [ ] Curate source corrections without modifying original archives.
- [ ] Introduce an attributed art-reference catalog with rights metadata.
- [ ] Support incremental source refreshes and reproducible index releases.

Current data counts and usage examples are maintained in the [README](../README.md). Implementation history lives in Git commits.
