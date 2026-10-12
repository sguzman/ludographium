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
- [x] Read all 367 pinned original bibliographic DATs in Rust from Git text with verified source hashes, conservative CRC/title associations and retained unmatched evidence.
- [x] Read and search all 16 committed CC0 Wikidata JSONL source partitions in Rust, verifying source hashes and retaining QIDs and dates without inferred source identities.
- [x] Reconcile Libretro and Wikidata original text sources in Rust using platform-scoped conservative title candidates, original provenance and explicit ambiguous-QID status.
- [x] Compare source-grounded Libretro releaseyear and Wikidata publication-year evidence across title candidates, preserving regional ambiguity and raw contradictory/missing assertions.
- [x] Integrate and permanently publish a SHA-256-locked CC0 Wikidata source snapshot in `data-v1.6.0`, across 16 whole-platform queries, with 15,868 item/platform observations and 29,333 literal date claims.
- [x] Bulk-generate 8,971 noncanonical title correspondence candidates and identify 126 ambiguous links without merging game identities.
- [x] Acquire all 16 Wikidata platform partitions of original CC0 P178 developer, P123 publisher and P136 genre claims (47,144 new source bindings, 14,759 game-item/platform observations), with immutable source text and SHA-256 provenance.
- [x] Accession 2,768 independently referenced Wikidata company/genre entity QIDs and 2,614 English labels in 28 source-pinned batches, preserving 154 unlabeled references without invented names.
- [x] Compare independent Wikidata developer and publisher QID/English-label claims with attributed Libretro company fields across all 8,971 noncanonical title candidates, preserving agreement, missing evidence and disagreement statuses.
- [x] Expose an exact-QID, per-platform Wikidata game observation projection across title/date and developer/publisher/genre captures, retaining separately captured claims, entity labels and source-only observations.
- [x] Add all 92,621 original series, title, language, distribution and external-ID source bindings to the exact-QID game observation union without erasing independent source-only rows.
- [x] Independently capture and hash-verify 1,837 game-relation QID label observations (1,639 English, 198 unlabeled), displaying them only as source-attributed evidence.
- [x] Accession 124,690 original language-tagged Wikidata label and alternate-title statements spanning 25 observed language tags and 16 platforms, with full SHA-256 source retention and bounded offline Rust lookup.
- [x] Preserve 92,621 additional original Wikidata statements across 16 console groups for series, play modes, languages, countries, distribution, published titles and 3,282 Steam/GOG external identifier claims, with exact query/response source hashes.
- [x] Audit all 3,282 source Steam/GOG ID claims, 1,972 provider-qualified ID strings, cross-platform repetition and 10 multi-QID identifier conflicts as noncanonical source review leads.
- [x] Acquire 65,182 original source claims for MobyGames numeric/legacy IDs, GameFAQs, HowLongToBeat, OpenCritic, MAME, AtariAge, PlayStation and Metacritic with hash-pinned responses and exact property-qualified offline reverse lookup.
- [x] Include original authority identifier claims in the exact-QID, per-platform offline game-observation union while keeping the fifth source accession independent and preserving source-only QID observations.
- [x] Accession and verify all 23,623 original P4769 statement-level observations with explicit/missing P400 qualifiers, distinguishing 9,042 same-partition qualifiers from 14,084 other-platform qualifiers and 497 unqualified rows.
- [x] Add three previously uncovered Wikidata P400 platform partitions (Atari 7800, PSP, Vita), preserving 3,888 original response rows, 2,254 game item/platform observations, and five nonliteral Vita P577 bindings without interpreting them as dates.
- [x] Add independently pinned Atari Jaguar, Atari Lynx, WonderSwan and WonderSwan Color source partitions (305 observations, 206 QIDs), with separate Rust v2 source lookup and conservative title-review candidates.
- [x] Add six more independently hash-pinned Wikidata P400 console partitions (1,148 original rows, 655 item/platform QIDs), with Rust v3 lookup and conservative title review.
- [x] Add six more verified Atari, Coleco, Vectrex, Intellivision, Odyssey and Pokémon Mini source partitions (482 original rows, 356 item/platform QIDs), with read-only Rust v4 lookup.
- [x] Preserve six specialized console query scopes (35 source rows, 22 game QIDs) including an explicitly hash-verified zero-result Casio Loopy capture, with Rust v5 lookup and conservative title review.
- [x] Integrate six additional v6 platform queries into hash-verified offline Rust lookup and noncanonical title review, retaining all 662 raw rows, 309 item/platform observations, two nonliteral publication bindings, and the zero-result Tiger Game.com partition.
- [x] Accession and integrate six additional seventh-cohort Wikidata console scopes (20 original source rows, 14 item/platform observations, two explicit zero-row partitions) with immutable query/response evidence and offline source/title-review lookup.
- [x] Bulk-acquire, preserve and offline-verify 11,231 additional independent Wikidata P178/P123/P136 statements across all 37 added platform scopes (19 plus 18), without canonical work/company associations.
- [x] Bulk-acquire, preserve and offline-verify 20,460 additional Wikidata series, language, distribution, title and external-ID statements across the same 37 added platform scopes, leaving ambiguous provider identifiers unresolved.
- [x] Capture 2,255 independent English-label QID observations (2,079 labeled, 176 unresolved) in 23 batches and verify them against all 74 pinned expanded metadata source manifests and referenced entity QIDs.
- [x] Quantify exact noncanonical title candidates for three independently captured console cohorts: v3 290 links (4 ambiguous), v4 238 links (0 ambiguous), v5 10 links (0 ambiguous), retaining empty source and no-match cases.
- [ ] Expand independently *provider-verified* identifier evidence beyond Wikidata assertions; quantify false-positive risk using adjudicated ground truth.
- [x] Publish a durable, versioned SQLite companion for downstream offline consumers (`data-v1.4.0`).

- [x] Build and integrity-check a disposable 69-list CC0 MAME plus 75-scope CC-BY-SA Libretro SQLite companion, with 33,119 original MAME observations, 117,145 DAT records, 19,152 source-media evidence pairs, 6,833 title-review leads, 21,845 source-review tasks and stable cohort attribution.
- [x] Provide bounded, filtered paging across original MAME, Libretro, source-media, title-review and stable review-unit readers; verify independent original source ordinals and preserve historic baseline evidence.
- [x] Publish an additive 69-list, 75-collection Libretro gap matrix while preserving the original 65-list report: 93,911 DAT source records remain without current cross-provider review evidence, spanning 21 collections with no review leads.
- [ ] Expand independent source coverage for unmatched digital/optical and later-generation platforms with provider-specific licensing and provenance review; treat no-match as an evidence gap, not proof of a missing game.

## Identity and curation

- [x] Establish evidence-validated UUID identifiers for work, release, and build records.
- [x] Curate source-grounded work/release/build identities, including independently hashed regional and revision records across Game Boy, Color, Advance, Nintendo DS, Master System and Game Gear.
- [ ] Develop a corpus-wide evidence-based candidate-identity pipeline with explicit uncertainty, stable identifiers and exception-only review. The selected curated examples remain validation fixtures; serial game-by-game curation is not the production workflow.
- [x] Provide conservative, provenance-preserving revision candidate discovery without generating canonical relationships.
- [x] Reject conflicting work/release ownership of a source occurrence during curation validation.
- [x] Verify the same parent-evidence and ownership invariants in the Rust offline reader.
- [x] Audit curated media against separately attributed field-DAT claims and prioritize revision leads by field-claim availability without auto-curation.
- [x] Preserve prior exact-revision curation as test fixtures without making manually reviewed entries a prerequisite to metadata ingestion.
- [x] Independently index the 124,690 language-tagged title/alias assertions into exact same-platform Libretro title review candidates with grouped original provenance, ambiguity and comparisons against the original 8,971 English-label links.
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
