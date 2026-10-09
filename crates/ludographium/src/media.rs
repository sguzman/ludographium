//! Explicit, bounded-memory fingerprints of well-defined ROM file representations.
//!
//! Every conversion is opt-in. The input is never written to or retained.
//! A converted fingerprint is evidence for a source match, not proof of game identity.
use crate::CatalogError;
use sha1::{Digest, Sha1};
use std::io::{Read, Seek, SeekFrom};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MediaFormat {
    NesInes,
    SnesCopier512,
    N64V64,
    N64N64,
}

impl MediaFormat {
    pub fn parse(value: &str) -> Result<Self, CatalogError> {
        match value {
            "nes-ines" => Ok(Self::NesInes),
            "snes-copier512" => Ok(Self::SnesCopier512),
            "n64-v64" => Ok(Self::N64V64),
            "n64-n64" => Ok(Self::N64N64),
            _ => Err(CatalogError::Invalid(format!(
                "unsupported media format: {value}; expected nes-ines, snes-copier512, n64-v64 or n64-n64"
            ))),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Self::NesInes => "nes-ines",
            Self::SnesCopier512 => "snes-copier512",
            Self::N64V64 => "n64-v64",
            Self::N64N64 => "n64-n64",
        }
    }

    pub fn platform(self) -> &'static str {
        match self {
            Self::NesInes => "nes",
            Self::SnesCopier512 => "snes",
            Self::N64V64 | Self::N64N64 => "n64",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NormalizedFingerprint {
    /// SHA-1 of the explicitly converted byte representation.
    pub sha1: String,
    /// Number of bytes in that converted representation.
    pub size: u64,
    /// Name of the explicitly selected conversion contract.
    pub media_format: &'static str,
}

fn invalid(message: &str) -> CatalogError {
    CatalogError::Invalid(format!("invalid normalized media: {message}"))
}

/// Compute a *converted* SHA-1 without modifying the original stream.
///
/// Only these explicit transformations are supported:
/// * iNES 1.0 without trainer, extras or NES 2.0: exact PRG + CHR payload
/// * SNES copier prefix: drop exactly 512 bytes when remainder is in 32-KiB banks
/// * N64 V64: swap adjacent byte pairs
/// * N64 N64: reverse each four-byte word
///
/// An arbitrary copy of bytes cannot establish platform identity. Callers must
/// require the declared platform and compare the full transformed SHA-1+size to
/// a source record; never merge game identities based on conversion alone.
pub fn fingerprint_normalized<R: Read + Seek>(
    mut input: R,
    format: MediaFormat,
) -> Result<NormalizedFingerprint, CatalogError> {
    let file_len = input.seek(SeekFrom::End(0))?;
    input.seek(SeekFrom::Start(0))?;
    fingerprint_normalized_stream(input, file_len, format)
}

/// Convert a non-seekable input (including a decoded ZIP entry) without
/// extracting to disk. The file_len parameter is the declared decoded byte
/// length, not the compressed ZIP size. Enforce exact consumption.
pub fn fingerprint_normalized_stream<R: Read>(
    mut input: R,
    file_len: u64,
    format: MediaFormat,
) -> Result<NormalizedFingerprint, CatalogError> {
    let mut digest = Sha1::new();
    let size = match format {
        MediaFormat::NesInes => {
            if file_len < 16 {
                return Err(invalid("iNES header is truncated"));
            }
            let mut header = [0u8; 16];
            input.read_exact(&mut header)?;
            if &header[..4] != b"NES\x1a" {
                return Err(invalid("expected iNES NES\\x1A magic"));
            }
            if (header[7] & 0x0c) != 0 || (header[7] & 0x03) != 0 {
                return Err(invalid(
                    "NES 2.0, VS/PlayChoice or reserved header flags are unsupported",
                ));
            }
            if (header[6] & 0x04) != 0 {
                return Err(invalid(
                    "iNES trainer requires a separate byte-domain contract",
                ));
            }
            if header[4] == 0 {
                return Err(invalid("iNES header has no PRG ROM"));
            }
            let prg = u64::from(header[4]) * 16_384;
            let chr = u64::from(header[5]) * 8_192;
            let expected = 16 + prg + chr;
            if file_len != expected {
                return Err(invalid("iNES PRG+CHR sizes do not match the file length"));
            }
            prg + chr
        }
        MediaFormat::SnesCopier512 => {
            if file_len <= 512 || (file_len - 512) % 32_768 != 0 {
                return Err(invalid(
                    "expected a 512-byte copier prefix and whole 32-KiB ROM banks",
                ));
            }
            let mut header = [0u8; 512];
            input.read_exact(&mut header)?;
            file_len - 512
        }
        MediaFormat::N64V64 | MediaFormat::N64N64 => {
            if file_len < 4 || file_len % 4 != 0 {
                return Err(invalid("Nintendo 64 ROM length must be divisible by four"));
            }
            let mut magic = [0u8; 4];
            input.read_exact(&mut magic)?;
            let expected: [u8; 4] = match format {
                MediaFormat::N64V64 => [0x37, 0x80, 0x40, 0x12],
                MediaFormat::N64N64 => [0x40, 0x12, 0x37, 0x80],
                _ => unreachable!(),
            };
            if magic != expected {
                return Err(invalid(
                    "Nintendo 64 byte-order signature does not match selected format",
                ));
            }
            digest.update([0x80, 0x37, 0x12, 0x40]);
            file_len
        }
    };

    let mut remaining = if matches!(format, MediaFormat::N64V64 | MediaFormat::N64N64) {
        size - 4
    } else {
        size
    };
    let mut buffer = [0u8; 65_536];
    while remaining > 0 {
        let length = remaining.min(buffer.len() as u64) as usize;
        input.read_exact(&mut buffer[..length])?;
        let bytes = &mut buffer[..length];
        match format {
            MediaFormat::N64V64 => {
                for pair in bytes.chunks_exact_mut(2) {
                    pair.swap(0, 1);
                }
            }
            MediaFormat::N64N64 => {
                for word in bytes.chunks_exact_mut(4) {
                    word.reverse();
                }
            }
            MediaFormat::NesInes | MediaFormat::SnesCopier512 => {}
        }
        digest.update(bytes);
        remaining -= length as u64;
    }

    // Reject streams longer than their declared size. This matters for ZIP
    // entries with inconsistent metadata or custom Read implementations.
    let mut extra = [0u8; 1];
    if input.read(&mut extra)? != 0 {
        return Err(invalid("decoded input exceeds its declared size"));
    }
    Ok(NormalizedFingerprint {
        sha1: format!("{:X}", digest.finalize()),
        size,
        media_format: format.name(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn hash(bytes: &[u8]) -> String {
        format!("{:X}", Sha1::digest(bytes))
    }

    #[test]
    fn explicit_platform_and_format_contracts() {
        assert_eq!(MediaFormat::parse("nes-ines").unwrap().platform(), "nes");
        assert_eq!(
            MediaFormat::parse("snes-copier512").unwrap().platform(),
            "snes"
        );
        assert_eq!(MediaFormat::parse("n64-v64").unwrap().platform(), "n64");
        assert_eq!(MediaFormat::parse("n64-n64").unwrap().platform(), "n64");
        assert!(MediaFormat::parse("raw").is_err());
        assert!(MediaFormat::parse("snes-copier512/../secret").is_err());
    }

    #[test]
    fn legacy_ines_hashes_only_declared_prg_chr() {
        let mut rom = vec![0u8; 16 + 16_384 + 8_192];
        rom[..4].copy_from_slice(b"NES\x1a");
        rom[4] = 1;
        rom[5] = 1;
        rom[16..].fill(0x3a);
        let pristine = rom.clone();
        let actual = fingerprint_normalized(Cursor::new(&rom), MediaFormat::NesInes).unwrap();
        assert_eq!(actual.sha1, hash(&rom[16..]));
        assert_eq!(actual.size, 24_576);
        assert_eq!(rom, pristine);
        rom[7] = 0x08;
        assert!(fingerprint_normalized(Cursor::new(&rom), MediaFormat::NesInes).is_err());
        rom[7] = 0;
        rom[6] = 0x04;
        assert!(fingerprint_normalized(Cursor::new(&rom), MediaFormat::NesInes).is_err());
        rom[6] = 0;
        rom.push(0);
        assert!(fingerprint_normalized(Cursor::new(&rom), MediaFormat::NesInes).is_err());
        rom.pop();
        rom.truncate(30);
        assert!(fingerprint_normalized(Cursor::new(&rom), MediaFormat::NesInes).is_err());
    }

    #[test]
    fn copier512_has_explicit_full_bank_requirement() {
        let mut data = vec![0xfe; 512];
        data.extend(vec![0x42; 32_768]);
        let result =
            fingerprint_normalized(Cursor::new(&data), MediaFormat::SnesCopier512).unwrap();
        assert_eq!(result.sha1, hash(&data[512..]));
        assert_eq!(result.size, 32_768);
        assert!(
            fingerprint_normalized(Cursor::new(&data[512..]), MediaFormat::SnesCopier512).is_err()
        );
        data.push(0);
        assert!(fingerprint_normalized(Cursor::new(&data), MediaFormat::SnesCopier512).is_err());
    }

    #[test]
    fn n64_endian_conversions_restore_identical_big_endian_bytes() {
        let canonical = [0x80, 0x37, 0x12, 0x40, 0xab, 0xcd, 0xef, 0x11];
        let v64 = [0x37, 0x80, 0x40, 0x12, 0xcd, 0xab, 0x11, 0xef];
        let n64 = [0x40, 0x12, 0x37, 0x80, 0x11, 0xef, 0xcd, 0xab];
        for (bytes, format) in [
            (&v64[..], MediaFormat::N64V64),
            (&n64[..], MediaFormat::N64N64),
        ] {
            let result = fingerprint_normalized(Cursor::new(bytes), format).unwrap();
            assert_eq!(result.size, canonical.len() as u64);
            assert_eq!(result.sha1, hash(&canonical));
        }
        assert!(fingerprint_normalized(Cursor::new(&v64), MediaFormat::N64N64).is_err());
        assert!(fingerprint_normalized(Cursor::new(&v64[..7]), MediaFormat::N64V64).is_err());
    }

    #[test]
    fn large_stream_crosses_chunk_boundaries() {
        let mut canonical = vec![0u8; 65_540];
        canonical[..4].copy_from_slice(&[0x80, 0x37, 0x12, 0x40]);
        for (i, byte) in canonical[4..].iter_mut().enumerate() {
            *byte = (i % 251) as u8;
        }
        let mut little = canonical.clone();
        for word in little.chunks_exact_mut(4) {
            word.reverse();
        }
        let result = fingerprint_normalized(Cursor::new(&little), MediaFormat::N64N64).unwrap();
        assert_eq!(result.sha1, hash(&canonical));
    }
}
