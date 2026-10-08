# Initial import protocol

Initial sources: `sources/libretro-no-intro.json`. The register pins the exact Git revision and per-file Git blob SHA.

To rebuild a platform snapshot locally:

1. Download the **exact raw DAT** from the pinned Libretro revision in the source register. Do not use a floating `master` URL or a filename-renamed ROM dump.
2. Verify its Git blob SHA against the register (Git's blob hash is SHA-1 over `blob <byte-count>\\0<bytes>`, not the plain-file SHA-1).
3. Run `python3 tools/import_dat.py --source sources/libretro-no-intro.json --platform gb --dat /path/to/Nintendo-Game-Boy.dat --output generated/v1/gb.json`. Repeat for `gbc`, `gba`, `snes`.
4. Validate `source_path`, record counts and `roms` checksums in the exported JSON. Preserve the original DAT unmodified in `archive/` only when redistribution terms allow.
5. Commit import outputs alongside source attribution, importer changes and validation outcomes. No ROM files are ever required to build or test this metadata.

Script is standard-library Python, usable through `uv run` or `python3`; a Rust read-only consumer is a separate later milestone. A successful import is **not** verification that a game image works or a claim that a title is canonical.
