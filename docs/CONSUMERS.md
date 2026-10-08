# Emulator and library-manager consumer contract

Ludographium is **data-only**. Starbyte and other emulators can use it without repository-specific coupling or network access at runtime. No emulator is modified by this project.

## Phase 1: source observation data

The current `generated/v1/<platform>.json` files are auditable source indexes, not canonical game registries. Consumers can:

1. Select the appropriate platform bundle.
2. Compute the checksum of the **expected exact byte representation** of a local game image.
3. Match a record's `roms[].sha1` (and optionally MD5/CRC32 with collision checks). A match is a probable *image fingerprint association*, not authenticity verification.
4. Display the source's title and qualified metadata while retaining the `source_id`, `source_revision`, `source_path` and `source_ordinal`.

Headered, headerless, trimmed, patched, byte-swapped and interleaved dumps can hash differently. A consumer **must not** strip headers or transform media based only on Ludographium's current generic fields; platform-specific, documented rules must be added first.

Never search a ROM in this repository, auto-execute cheats, or claim that an unmatched file is illegitimate. No runtime network fetching, file modification or core selection is required.

## Planned versioned distribution

A future consolidated `catalog.json` manifest will reference deterministic, per-platform files with byte lengths, SHA-256 digests, source attribution and contract versions. Cached consumers should pin a Git commit or release and verify it before use. The v1 JSON source records are a **provisional import contract**, not a promise that future curated APIs will have the same shape.

## ID and compatibility requirements

- Respect stable `gb`, `gbc`, `gba`, `snes`, `nds` etc platform IDs shared by convention with Cheatarium; do not mutate Cheatarium to enforce this.
- For public artifact contracts, increment major schema version before breaking changes.
- Never merge different regional titles simply because names normalize to the same slug.
- Null/unverified/unmatched is a legitimate result.
- Future curated work/release/build IDs will support more precise links to Cheatarium, instead of relying on filename guesses.
