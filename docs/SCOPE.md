# Scope and mission

Ludographium is a public, emulator-independent metadata archive for **console and handheld video games**. Its job is to collect evidence, preserve attribution, normalize useful factual records conservatively, and distribute reproducible read-only data.

## In scope

- Platform identifiers and known aliases.
- Source record titles, localized titles, regions, languages, serial/product codes and release/revision labels.
- Publishers, developers, release dates, ratings and other bibliographic facts **when sourced**.
- Non-executable file-identification metadata: filename hints, file sizes, CRC32, MD5, SHA-1, SHA-256, disc IDs, header IDs, and normalization rules.
- Optional references to cover art, manuals and screenshots (asset hosting requires rights review).
- Exact, traceable source snapshots; curated corrections and conflict resolution **separate** from raw evidence.
- Versioned offline consumer indexes usable by emulators, library managers and frontends.

## Out of scope

- ROMs, disc images, ISOs, BIOS/firmware, copyrighted game assets without appropriate rights.
- Cheats, passwords, unlockables, patches and executable modifications (Cheatarium).
- Emulation cores or program-specific UI/launcher logic (Starbyte and future emulators).
- Game mechanics ontology, semantic relations such as narrative worlds, or ambitious genre taxonomies (possible future Gameaerium).

## Identity is layered

A game *work*, a product/release, and a particular digital image/build are different things. The source-import layer deliberately does **not** assert a canonical work identity. It records what a source says about an item. Future curated IDs can link several source claims to one identified release/work while keeping the original source claims intact.

Names are evidence, not unique keys. Platform + CRC32 is useful but collision-prone. SHA-1/MD5/CRC32 are fingerprints of content variants, **not** proofs of a unique artistic game or of a legitimate copy. Use SHA-256 when independently available; never invent it from other hashes.

## Relationships

- Ludographium describes games; Cheatarium describes cheats for candidate games and revisions. Link by stable platform IDs and eventually verified revision identifiers, **never by optimistic title-slug joins**.
- Starbyte may read a published Ludographium index; Ludographium never edits Starbyte's code.
- Sourcearium is for textual corpora; Observatorium is for time/event observations. Ludographium keeps the domain-specific game catalog and provenance, without importing either project's unrelated datasets.
