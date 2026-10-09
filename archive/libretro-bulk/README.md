# Pinned bulk Libretro metadata source archive

This directory preserves **original source DAT metadata as text**, exactly as supplied by the pinned upstream repository at revision `fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90`.

- `metadat/no-intro/`: 65 additional console and handheld identification DATs.
- `metadat/{developer,publisher,genre,franchise,serial,releaseyear,releasemonth,maxusers,esrb,rumble}/`: 279 additional bibliographic field DATs.
- Source register: [identification files](../../sources/bulk-expansion-v1.json) and [bibliographic files](../../sources/bulk-fields-v1.json).
- Official upstream: [libretro/libretro-database](https://github.com/libretro/libretro-database) at the immutable commit above.
- Upstream repository declares **CC BY-SA 4.0**, including attribution/share-alike requirements as applicable. No-Intro and other underlying third-party rights remain separate and are **not** overridden by the repository declaration.

Files are organized by their *original upstream relative paths*, with no conversions, dropped records, or inferred game identities. Every DAT must match both the SHA-1 Git blob identity and exact byte count in the source manifests; discrepancies abort accession.

These files contain **game metadata, not ROMs, firmware, artwork or game executables**. Git can clone the original DAT corpus directly. No SQLite or other generated binary is checked in.

The previous ten-system DAT archive at `archive/libretro-no-intro/` and `archive/libretro-enrichment/` is preserved separately, unchanged.
