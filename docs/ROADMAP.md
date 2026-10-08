# Roadmap

This is a roadmap, not a changelog or a list of implied completed features.

## Phase A: reliable source accession

- [x] Define repository boundaries, layered identity and evidence rules.
- [x] Pin the initial Libretro No-Intro source revision and file blobs.
- [x] Import and retain intact source snapshots for SNES, GB, GBC and GBA.
- [x] Build validated, deterministic per-platform source observation bundles.
- [x] Add input parser tests, checksum/record validation and a repeatable rebuild command.
- [ ] Inspect source licensing for each planned dataset, especially third-party overrides.

## Phase B: defensible identities

- [ ] Build conservative candidate matches across independent providers and localized aliases.
- [ ] Store disputed fields and alternative assertions with source locators.
- [ ] Curate canonical work, release and build identities without overwriting sources.
- [ ] Add stable ID mapping to Cheatarium's platform/game/revision terms.
- [ ] Add NES and DS, then broaden to other console and handheld libraries.

## Phase C: distribution

- [ ] SHA-256 verified, reproducible, versioned offline release manifests.
- [ ] Read-only Rust consumer and CLI for exact fingerprint lookup.
- [ ] Document platform-specific normalization and exact byte domains.
- [ ] Publish migration/compatibility rules for future contract versions.

## Phase D: enrichment

- [ ] Additional release metadata with licensed/permitted sources: publisher, developer, dates, languages, serials.
- [ ] Art reference registry with separate rights review; do not redistribute protected images by default.
- [ ] Source corrections, conflict reports and incremental refresh automation.

Keep the README a clear introduction. Detailed progress and implementation logs live here and in commit history.
