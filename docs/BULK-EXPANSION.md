# Bulk console and handheld metadata accession

Ludographium now has a reproducible **75-platform**, **117,145-source-observation** console metadata database. It is not a hand-curated subset: one importer processes every original DAT source record, its media fingerprints, and every corresponding available bibliographic field DAT claim.

## Coverage of the expanded pinned source snapshot

| Measure | Baseline v1 (ten systems) | Expanded (75 collections) |
| --- | ---: | ---: |
| Console/handheld source collections | 10 | **75** |
| Identification source observations | 41,491 | **117,145** |
| Exact media entries | 41,491 | **117,145** |
| Bibliographic field observations retained | 129,008 | **167,640** |
| Conservatively matched field observations | 98,856 | **112,948** |
| Source records with at least one matched field | 16,937 | **19,763** |

The additional sources contribute **75,654** identification observations and **38,632** field observations, of which **14,092** conservatively attach to original source occurrences. Unmatched records are never omitted. These numbers are source observations, not a count of distinct game works or validated publication records.

### Included source families

The 65 newly accessioned platform collections include Atari 2600, 5200, 7800, Jaguar and Lynx; PC Engine/TurboGrafx-16 and SuperGrafx; WonderSwan and WonderSwan Color; Neo Geo Pocket and Color; Nintendo 3DS, DSi, Virtual Boy, Pokémon Mini, Famicom Disk System, Satellaview, Wii/Wii U digital collections; Sega 32X, SG-1000 and Pico; Microsoft Xbox 360; PlayStation Portable, Vita and PS3 digital collections; and additional dedicated home consoles and handhelds.

Collection is at the **DAT-file level** using a deterministic, documented source manifest. This is not a claim of all commercially published games, all platforms, or all region-specific releases. Original ten-system JSON consumer contracts remain separately available for compatibility.

## Exact source provenance

- [65 identification DATs](../sources/bulk-expansion-v1.json), each pinned to its upstream path, Git blob SHA and byte length;
- [279 bibliographic DATs](../sources/bulk-fields-v1.json), pinned independently by path, field, SHA and length;
- same immutable upstream repository revision: `fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90`;
- declared upstream repository license **CC BY-SA 4.0**, with underlying No-Intro and third-party rights still separately applicable.

The expanded SQLite database embeds the **original byte-for-byte DAT inputs** in `source_archives` and `field_archives`, and also includes their source registers in `provenance`. It contains no game ROMs, firmware, executable programs, game images or cheat codes.

## Conservative field association

The `claims` table contains all matched, unmatched and incomplete bibliographic claims. When a source provides CRC32, a field is attached to a base observation only if:

1. exactly one media entry in that platform has the original CRC32;
2. the original metadata comment matches that source record's title exactly; and
3. the field value is present.

Otherwise the claim is retained with the reason, including `unmatched_crc`, `ambiguous_crc`, `comment_mismatch`, `missing_comment`, or `missing_value`.

Some PlayStation and other optical-media metadata files give serials but omit CRC32. These are retained with a **NULL CRC32** and `missing_crc` status rather than discarded or joined by a guessed checksum. Original `rom_serial` and other record fields remain in `source_fields_json`. A future, explicitly documented unique-serial reconciliation procedure may address these sources without relaxing this evidentiary boundary.

Matching field claims are *source associations*, not independent factual verification and not canonical game/release identities.

## Build and verify

The [dedicated bulk CI workflow](../.github/workflows/expand-corpus.yml) performs the entire process without a manual game-by-game queue:

```sh
python3 tools/build_expanded_corpus.py --build --db /tmp/expanded-base.sqlite
python3 tools/enrich_expanded_corpus.py --build \
  --from-db /tmp/expanded-base.sqlite \
  --db /tmp/ludographium-expanded.sqlite
python3 tools/enrich_expanded_corpus.py --verify --db /tmp/ludographium-expanded.sqlite
```

The two build steps fetch only the manifest-selected, **revision- and Git-blob-pinned** source files. They fail closed on missing source files, checksum drift, unsupported input syntax, duplicate or malformed platform registries, source-claim mismatches, and database integrity errors. The pipeline verifies source and media counts against the previous ten-platform baseline and exercises synthetic regression cases for mismatched titles, serial-only claims, and tampered source input.

Use a regular SQLite client or:

```sh
python3 tools/enrich_expanded_corpus.py --db /tmp/ludographium-expanded.sqlite --summary
python3 tools/enrich_expanded_corpus.py --db /tmp/ludographium-expanded.sqlite --title Mario --limit 10
python3 tools/enrich_expanded_corpus.py --db /tmp/ludographium-expanded.sqlite --platform atari2600 --title Asteroids
```

The source IDs in the expanded SQLite are deterministic, lowercased alphanumeric forms of the upstream collection names, not claims of canonical hardware taxonomies. Original source names and revision evidence remain in the source register and the source paths.

The original ten-system JSON runtime is **not rewritten** by this expansion. The [published `data-v1.5.0` expanded SQLite companion](https://github.com/sguzman/ludographium/releases/download/data-v1.5.0/ludographium-expanded-data-v1.5.0.sqlite) is a separate durable dataset asset, with its [SHA-256 checksum](https://github.com/sguzman/ludographium/releases/download/data-v1.5.0/ludographium-expanded-data-v1.5.0.sqlite.sha256).

## What remains

Bulk source coverage has expanded, but most individual platform collections still lack complete independent bibliographic histories. Missing CRC32s and divergent comments limit automatic joins. Work/release/build entity reconciliation remains separate from ingestion and is not required for access to the entire metadata corpus.

The next genuine corpus improvements are source-wide independent bibliographic provider accession, conservative identifier reconciliation with quantified join/ambiguity rates, and wider platform coverage wherever source rights permit. Manual per-game identity drafting is not an ingestion strategy.
