# Media byte-domain contracts

**Exact-source matching is the default.** The file lookup API and CLI normally SHA-1 hash every byte the caller supplies. A changed header, extra trainer, byte swap, or patch can change the digest. Ludographium never changes files, extracts game binaries into its repository, or infers a game identity from title alone.

For selected, well-defined representations, the Rust `media::fingerprint_normalized` helper and `--media-format` CLI option compute a second, **explicitly requested** representation. The returned `normalized_sha1` and `normalized_size` refer only to those converted bytes. The exact original file is left untouched. Source matches still require *both* full SHA-1 equality and media byte length equality; a match is a source-fingerprint association, not proof of legitimate provenance or canonical game identity.

## Supported explicit formats

| Selected platform | `--media-format` | Conversion and guardrails |
| --- | --- | --- |
| `nes` | `nes-ines` | Check 16-byte `NES\\x1A` legacy iNES header, nonzero PRG ROM count, no trainer, no NES 2.0 or VS/PlayChoice flags, and exactly the declared PRG+CHR payload size; hash precisely the payload after the 16-byte header |
| `snes` | `snes-copier512` | Check exact input size is 512 plus a positive multiple of 32 KiB; skip only the first 512 bytes; hash remaining bytes |
| `n64` | `n64-v64` | Require initial bytes `37 80 40 12`, length divisible by 4; swap each adjacent byte pair to big-endian N64 ROM order |
| `n64` | `n64-n64` | Require initial bytes `40 12 37 80`, length divisible by 4; reverse every four-byte word to big-endian N64 ROM order |

Conversions are **opt-in and tied to a single platform**. The CLI rejects `--media-format` without `--file`, on `--platform all`, or for the wrong platform. Neither `--zip` nor generic fingerprint searches implicitly normalize bytes. Compressed ZIP members retain exact-byte identification. The conversion helper works on a `Read + Seek` stream with fixed-size hashing buffers; the caller's file is not mutated or preserved.

Examples, from a local checkout with an existing file (substitute your own path):

```sh
cargo run --locked -p ludographium -- --platform nes --file /path/to/title.nes --media-format nes-ines
cargo run --locked -p ludographium -- --platform snes --file /path/to/title.smc --media-format snes-copier512 --enriched
cargo run --locked -p ludographium -- --platform n64 --file /path/to/title.v64 --media-format n64-v64 --curated
```

The response marks `input_kind: "explicit-normalized-local-file-bytes"` and includes `media_format`, `normalized_sha1`, `normalized_size`, `matches`, and `match_count`.

## What this does **not** claim

- The SNES prefix is **not authenticated** as a copier header: it has no universal magic. The size guard and explicit request are necessary precautions, not independent proof. A wrong-format choice may yield no match.
- iNES with a 512-byte trainer, NES 2.0 extended sizes, uncommon appended metadata, or extra console-specific sections are **rejected**, not silently discarded.
- For N64, only two specified dump orders are converted. Already-big-endian `.z64` images require no conversion; use the regular exact-byte `--file` lookup. Extensions alone are not treated as proof.
- Other systems and interleaved, overdumped, truncated, padded, decrypted, patched, or format-specific images remain out of scope. A missing match does not prove that a title does not exist.
- A successful converted media match is not an automatic work/release/build correspondence. Source provenance and curated identity rules still apply.

These are **consumer conversion contracts**, not modifications to immutable source DATs or to committed normalized catalog records. If future formats require additional conventions, they must be versioned, documented, and regression-tested instead of guessed.

### Format references

- [NESdev iNES header layout](https://www.nesdev.org/wiki/INES) and [NES 2.0 distinctions](https://www.nesdev.org/wiki/NES_2.0)
- [SNESdev ROM file formats and copier-header conventions](https://snes.nesdev.org/wiki/ROM_file_formats)
- [Debian file magic for Nintendo 64 dump byte orders](https://sources.debian.org/src/file/1%3A5.35-4%2Bdeb10u2/magic/Magdir/console)
