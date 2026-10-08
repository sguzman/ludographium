//! Read-only access to versioned Ludographium source-observation indexes.
//!
//! A fingerprint match associates media bytes with an upstream source record.
//! It does not establish a canonical work, release, or build identity.

use serde::Deserialize;
use sha1::{Digest, Sha1};
use sha2::Sha256;
use std::collections::HashMap;
use std::error::Error;
use std::fmt;
use std::fs;
use std::path::{Component, Path};

#[derive(Debug)]
pub enum CatalogError {
    Io(std::io::Error),
    Json(serde_json::Error),
    Invalid(String),
}

impl fmt::Display for CatalogError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(err) => write!(f, "I/O error: {err}"),
            Self::Json(err) => write!(f, "invalid JSON: {err}"),
            Self::Invalid(msg) => write!(f, "invalid catalog: {msg}"),
        }
    }
}

impl Error for CatalogError {}

impl From<std::io::Error> for CatalogError {
    fn from(error: std::io::Error) -> Self {
        Self::Io(error)
    }
}

impl From<serde_json::Error> for CatalogError {
    fn from(error: serde_json::Error) -> Self {
        Self::Json(error)
    }
}

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    kind: String,
    source_id: String,
    source_revision: String,
    platforms: Vec<ManifestPlatform>,
}

#[derive(Debug, Deserialize)]
struct ManifestPlatform {
    platform: String,
    artifact_path: String,
    artifact_git_blob_sha: String,
    source_records: usize,
    rom_fingerprints: usize,
}

#[derive(Debug, Deserialize)]
struct DistributionManifest {
    schema_version: u32,
    kind: String,
    source_id: String,
    source_revision: String,
    artifacts: Vec<DistributionArtifact>,
}

#[derive(Debug, Deserialize)]
struct DistributionArtifact {
    path: String,
    bytes: usize,
    sha256: String,
}

#[derive(Debug, Deserialize)]
struct Bundle {
    schema_version: u32,
    kind: String,
    platform: String,
    source_id: String,
    source_revision: String,
    source_path: String,
    source_blob_sha: String,
    record_count: usize,
    rom_count: usize,
    records: Vec<SourceRecord>,
}

/// One untouched source record as represented in the normalized index.
#[derive(Debug, Deserialize)]
pub struct SourceRecord {
    pub source_ordinal: usize,
    pub name: String,
    pub region: Option<String>,
    pub serial: Option<String>,
    pub description: Option<String>,
    pub releaseyear: Option<String>,
    pub releasemonth: Option<String>,
    pub releaseday: Option<String>,
    pub roms: Vec<MediaFile>,
}

/// A source's assertion about one exact media byte representation.
#[derive(Debug, Deserialize)]
pub struct MediaFile {
    pub name: String,
    pub size: u64,
    pub crc32: Option<String>,
    pub md5: Option<String>,
    pub sha1: Option<String>,
    pub serial: Option<String>,
}

#[derive(Debug)]
pub struct SourceIdentity {
    pub source_id: String,
    pub revision: String,
    pub path: String,
    pub git_blob_sha: String,
}

/// A match retains its original source ordinal and snapshot identity.
#[derive(Debug)]
pub struct MediaMatch<'a> {
    pub platform: &'a str,
    pub record: &'a SourceRecord,
    pub media: &'a MediaFile,
    pub source: &'a SourceIdentity,
}

/// In-memory index for one platform, built once and reused across lookups.
pub struct PlatformCatalog {
    platform: String,
    source: SourceIdentity,
    records: Vec<SourceRecord>,
    by_sha1: HashMap<String, Vec<(usize, usize)>>,
    by_crc32_size: HashMap<(String, u64), Vec<(usize, usize)>>,
}

fn git_blob_sha(bytes: &[u8]) -> String {
    let mut hash = Sha1::new();
    hash.update(format!("blob {}\0", bytes.len()).as_bytes());
    hash.update(bytes);
    format!("{:x}", hash.finalize())
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hash = Sha256::new();
    hash.update(bytes);
    format!("{:x}", hash.finalize())
}

fn verify_distribution_artifact(
    distribution: &DistributionManifest,
    path: &str,
    bytes: &[u8],
) -> Result<(), CatalogError> {
    let matches: Vec<_> = distribution
        .artifacts
        .iter()
        .filter(|entry| entry.path == path)
        .collect();
    if matches.len() != 1 {
        return Err(CatalogError::Invalid(format!(
            "missing or duplicate distribution entry for {path}"
        )));
    }
    let artifact = matches[0];
    if artifact.bytes != bytes.len() || artifact.sha256 != sha256_hex(bytes) {
        return Err(CatalogError::Invalid(format!(
            "SHA-256 or byte-length mismatch for {path}"
        )));
    }
    Ok(())
}

fn validate_hex(input: &str, width: usize) -> Result<String, CatalogError> {
    if input.len() != width || !input.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(CatalogError::Invalid(format!(
            "expected a {width}-character hexadecimal fingerprint"
        )));
    }
    Ok(input.to_ascii_uppercase())
}

fn relative_path(path: &str) -> Result<&Path, CatalogError> {
    let path = Path::new(path);
    if path.components().next().is_none()
        || !path.components().all(|p| matches!(p, Component::Normal(_)))
    {
        return Err(CatalogError::Invalid("unsafe artifact path".into()));
    }
    Ok(path)
}

impl PlatformCatalog {
    /// Open and validate a platform bundle relative to the repository/data root.
    /// Only the manifest and one indexed JSON file are needed at runtime.
    pub fn open(root: impl AsRef<Path>, platform: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let manifest_bytes = fs::read(root.join("generated/v1/catalog.json"))?;
        let manifest: Manifest = serde_json::from_slice(&manifest_bytes)?;
        if manifest.schema_version != 1 || manifest.kind != "source-catalog" {
            return Err(CatalogError::Invalid("unsupported catalog manifest".into()));
        }
        let distribution_bytes = fs::read(root.join("generated/v1/distribution.json"))?;
        let distribution: DistributionManifest = serde_json::from_slice(&distribution_bytes)?;
        if distribution.schema_version != 1
            || distribution.kind != "ludographium-distribution"
            || distribution.source_id != manifest.source_id
            || distribution.source_revision != manifest.source_revision
        {
            return Err(CatalogError::Invalid("distribution/source catalog mismatch".into()));
        }
        verify_distribution_artifact(
            &distribution,
            "generated/v1/catalog.json",
            &manifest_bytes,
        )?;

        let entry = manifest
            .platforms
            .iter()
            .find(|p| p.platform == platform)
            .ok_or_else(|| CatalogError::Invalid(format!("unknown platform: {platform}")))?;

        // Don't let untrusted manifest paths select arbitrary files.
        let path = relative_path(&entry.artifact_path)?;
        if path != Path::new(&format!("generated/v1/{platform}.json")) {
            return Err(CatalogError::Invalid("unexpected artifact path".into()));
        }
        let bytes = fs::read(root.join(path))?;
        if git_blob_sha(&bytes) != entry.artifact_git_blob_sha {
            return Err(CatalogError::Invalid(format!(
                "Git blob digest mismatch for {}",
                entry.artifact_path
            )));
        }
        verify_distribution_artifact(&distribution, &entry.artifact_path, &bytes)?;
        let bundle: Bundle = serde_json::from_slice(&bytes)?;
        if bundle.schema_version != 1
            || bundle.kind != "source-observations"
            || bundle.platform != platform
            || bundle.source_id != manifest.source_id
            || bundle.source_revision != manifest.source_revision
            || bundle.record_count != entry.source_records
            || bundle.rom_count != entry.rom_fingerprints
            || bundle.records.len() != bundle.record_count
        {
            return Err(CatalogError::Invalid("manifest/bundle metadata mismatch".into()));
        }
        let roms = bundle.records.iter().map(|r| r.roms.len()).sum::<usize>();
        if roms != bundle.rom_count {
            return Err(CatalogError::Invalid("media entry count mismatch".into()));
        }
        Self::from_bundle(bundle)
    }

    fn from_bundle(bundle: Bundle) -> Result<Self, CatalogError> {
        let mut by_sha1: HashMap<String, Vec<(usize, usize)>> = HashMap::new();
        let mut by_crc32_size: HashMap<(String, u64), Vec<(usize, usize)>> = HashMap::new();
        for (record_index, record) in bundle.records.iter().enumerate() {
            if record.source_ordinal != record_index + 1 || record.name.is_empty() {
                return Err(CatalogError::Invalid("invalid source record ordinal/title".into()));
            }
            for (rom_index, media) in record.roms.iter().enumerate() {
                if let Some(ref hash) = media.sha1 {
                    let hash = validate_hex(hash, 40)?;
                    by_sha1.entry(hash).or_default().push((record_index, rom_index));
                }
                if let Some(ref hash) = media.crc32 {
                    let hash = validate_hex(hash, 8)?;
                    by_crc32_size
                        .entry((hash, media.size))
                        .or_default()
                        .push((record_index, rom_index));
                }
            }
        }
        Ok(Self {
            platform: bundle.platform,
            source: SourceIdentity {
                source_id: bundle.source_id,
                revision: bundle.source_revision,
                path: bundle.source_path,
                git_blob_sha: bundle.source_blob_sha,
            },
            records: bundle.records,
            by_sha1,
            by_crc32_size,
        })
    }

    pub fn platform(&self) -> &str {
        &self.platform
    }

    pub fn source(&self) -> &SourceIdentity {
        &self.source
    }

    pub fn len(&self) -> usize {
        self.records.len()
    }

    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }

    fn collect_matches(&self, keys: Option<&Vec<(usize, usize)>>) -> Vec<MediaMatch<'_>> {
        keys.into_iter()
            .flat_map(|indices| indices.iter())
            .map(|&(record_index, rom_index)| MediaMatch {
                platform: &self.platform,
                record: &self.records[record_index],
                media: &self.records[record_index].roms[rom_index],
                source: &self.source,
            })
            .collect()
    }

    /// Exact SHA-1 match; returns every matching source occurrence, including duplicates.
    pub fn lookup_sha1(&self, sha1: &str) -> Result<Vec<MediaMatch<'_>>, CatalogError> {
        let key = validate_hex(sha1, 40)?;
        Ok(self.collect_matches(self.by_sha1.get(&key)))
    }

    /// Weaker CRC32+length match, preserving possible collisions as multiple results.
    pub fn lookup_crc32(
        &self,
        crc32: &str,
        byte_len: u64,
    ) -> Result<Vec<MediaMatch<'_>>, CatalogError> {
        let key = validate_hex(crc32, 8)?;
        Ok(self.collect_matches(self.by_crc32_size.get(&(key, byte_len))))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
    }

    #[test]
    fn loads_all_accessioned_platforms() {
        for (platform, count) in [("snes", 4268), ("gb", 2254), ("gbc", 2566), ("gba", 3692)] {
            let index = PlatformCatalog::open(root(), platform).unwrap();
            assert_eq!(index.len(), count);
            assert_eq!(index.platform(), platform);
        }
    }

    #[test]
    fn matches_known_game_boy_fingerprint_and_retains_evidence() {
        let index = PlatformCatalog::open(root(), "gb").unwrap();
        let hits = index
            .lookup_sha1("952d154dd2c6189ef4b786ae37bd7887c8ca9037")
            .unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].record.name, "10-Pin Bowling (USA) (Proto)");
        assert_eq!(hits[0].record.source_ordinal, 1);
        assert_eq!(hits[0].media.size, 131072);
        assert_eq!(hits[0].source.source_id, "libretro-no-intro");
        assert_eq!(hits[0].source.git_blob_sha, "0ead6bff1f819075793605985a9ee2dcb3c0c3ab");
    }

    #[test]
    fn checksum_validation_and_unmatched_are_distinct() {
        let index = PlatformCatalog::open(root(), "gb").unwrap();
        assert!(index.lookup_sha1("invalid").is_err());
        assert!(index.lookup_crc32("not-hex!", 100).is_err());
        assert!(index.lookup_sha1(&"0".repeat(40)).unwrap().is_empty());
        let hit = index.lookup_crc32("9a024415", 131072).unwrap();
        assert_eq!(hit[0].record.name, "10-Pin Bowling (USA) (Proto)");
        assert!(index.lookup_crc32("9a024415", 131073).unwrap().is_empty());
    }

    #[test]
    fn collision_does_not_hide_entries() {
        let fake = Bundle {
            schema_version: 1,
            kind: "source-observations".into(),
            platform: "gb".into(),
            source_id: "example".into(),
            source_revision: "rev".into(),
            source_path: "source.dat".into(),
            source_blob_sha: "blob".into(),
            record_count: 2,
            rom_count: 2,
            records: (1..=2)
                .map(|n| SourceRecord {
                    source_ordinal: n,
                    name: format!("Game {n}"),
                    region: None,
                    serial: None,
                    description: None,
                    releaseyear: None,
                    releasemonth: None,
                    releaseday: None,
                    roms: vec![MediaFile {
                        name: format!("game-{n}.gb"),
                        size: 1024,
                        crc32: Some("AAAAAAAA".into()),
                        sha1: None,
                        md5: None,
                        serial: None,
                    }],
                })
                .collect(),
        };
        let index = PlatformCatalog::from_bundle(fake).unwrap();
        let hits = index.lookup_crc32("aaaaaaaa", 1024).unwrap();
        assert_eq!(hits.len(), 2);
        assert_eq!(hits[0].record.name, "Game 1");
        assert_eq!(hits[1].record.name, "Game 2");
    }

    #[test]
    fn rejects_unsafe_paths() {
        for bad in ["/tmp/outside", "../../outside", "foo/../bar", ""] {
            assert!(relative_path(bad).is_err(), "{bad}");
        }
        assert!(relative_path("generated/v1/gb.json").is_ok());
    }

    #[test]
    fn git_blob_hash_matches_committed_source() {
        let data = fs::read(root().join("archive/libretro-no-intro/gb.dat")).unwrap();
        assert_eq!(git_blob_sha(&data), "0ead6bff1f819075793605985a9ee2dcb3c0c3ab");
    }
    #[test]
    fn distribution_rejects_modified_bytes() {
        let raw = fs::read(root().join("generated/v1/distribution.json")).unwrap();
        let distribution: DistributionManifest = serde_json::from_slice(&raw).unwrap();
        let original = fs::read(root().join("generated/v1/gb.json")).unwrap();
        assert!(verify_distribution_artifact(
            &distribution,
            "generated/v1/gb.json",
            &original,
        ).is_ok());
        let mut corrupted = original;
        corrupted.push(b'x');
        assert!(verify_distribution_artifact(
            &distribution,
            "generated/v1/gb.json",
            &corrupted,
        ).is_err());
        assert!(verify_distribution_artifact(
            &distribution,
            "generated/v1/unknown.json",
            b"sample",
        ).is_err());
    }

    #[test]
    fn sha256_known_vector() {
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

}
