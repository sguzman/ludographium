//! Manifest-driven, read-only searches across every accessioned platform.
//!
//! Source matches remain individual platform/source occurrences. This module
//! never merges game works based on titles or checksum coincidences.

use crate::enrichment::{EnrichedMediaMatch, EnrichedPlatformCatalog};
use crate::{CatalogError, MediaMatch, PlatformCatalog};
use serde::Deserialize;
use sha1::{Digest, Sha1};
use std::collections::HashSet;
use std::fs;
use std::io::Read;
use std::path::Path;

#[derive(Deserialize)]
struct Registry {
    schema_version: u32,
    kind: String,
    platforms: Vec<RegistryPlatform>,
}

#[derive(Deserialize)]
struct RegistryPlatform {
    platform: String,
    artifact_path: String,
}

/// Enumerate the exact platform IDs advertised by a pinned catalog manifest.
/// Each platform bundle is subsequently checked against the distribution manifest.
pub fn registered_platforms(root: impl AsRef<Path>) -> Result<Vec<String>, CatalogError> {
    let raw = fs::read(root.as_ref().join("generated/v1/catalog.json"))?;
    let registry: Registry = serde_json::from_slice(&raw)?;
    if registry.schema_version != 1 || registry.kind != "source-catalog"
        || registry.platforms.is_empty()
    {
        return Err(CatalogError::Invalid("unsupported or empty source catalog".into()));
    }
    let mut result = Vec::with_capacity(registry.platforms.len());
    let mut seen = HashSet::new();
    for item in registry.platforms {
        let id = item.platform;
        if id.is_empty()
            || !id.bytes().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit())
            || item.artifact_path != format!("generated/v1/{id}.json")
            || !seen.insert(id.clone())
        {
            return Err(CatalogError::Invalid("unsafe or repeated platform registration".into()));
        }
        result.push(id);
    }
    Ok(result)
}

/// Read one exact media representation once, with bounded working memory.
/// No archive transformation, copier-header stripping, or byte swap is attempted.
fn fingerprint_reader<R: Read>(mut input: R) -> Result<(String, u64), CatalogError> {
    let mut digest = Sha1::new();
    let mut count = 0u64;
    let mut buffer = [0u8; 65536];
    loop {
        let length = input.read(&mut buffer)?;
        if length == 0 {
            break;
        }
        count = count.checked_add(length as u64)
            .ok_or_else(|| CatalogError::Invalid("media input length overflow".into()))?;
        digest.update(&buffer[..length]);
    }
    Ok((format!("{:X}", digest.finalize()), count))
}

/// Title matches are limited by source records, not by number of media entries.
pub struct CollectionTitleSearch<'a> {
    pub total_source_records: usize,
    pub matches: Vec<MediaMatch<'a>>,
}

/// Equivalent title discovery with attributed bibliographic source claims.
pub struct EnrichedCollectionTitleSearch<'a> {
    pub total_source_records: usize,
    pub matches: Vec<EnrichedMediaMatch<'a>>,
}

/// Preloaded, independently integrity-checked source indexes for all platforms.
pub struct CatalogCollection {
    indexes: Vec<PlatformCatalog>,
}

impl CatalogCollection {
    pub fn open(root: impl AsRef<Path>) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let indexes = registered_platforms(root)?.iter()
            .map(|p| PlatformCatalog::open(root, p))
            .collect::<Result<Vec<_>, _>>()?;
        Ok(Self { indexes })
    }

    pub fn platform_ids(&self) -> impl Iterator<Item = &str> {
        self.indexes.iter().map(|index| index.platform())
    }

    pub fn lookup_sha1(&self, value: &str) -> Result<Vec<MediaMatch<'_>>, CatalogError> {
        let mut matches = Vec::new();
        for index in &self.indexes {
            matches.extend(index.lookup_sha1(value)?);
        }
        Ok(matches)
    }

    pub fn lookup_crc32(&self, value: &str, size: u64) -> Result<Vec<MediaMatch<'_>>, CatalogError> {
        let mut matches = Vec::new();
        for index in &self.indexes {
            matches.extend(index.lookup_crc32(value, size)?);
        }
        Ok(matches)
    }

    pub fn lookup_bytes(&self, data: &[u8]) -> Result<Vec<MediaMatch<'_>>, CatalogError> {
        self.lookup_reader(data)
    }

    /// Hash the input once, then compare exact SHA-1 and byte length across platforms.
    pub fn lookup_reader<R: Read>(&self, input: R) -> Result<Vec<MediaMatch<'_>>, CatalogError> {
        let (hash, size) = fingerprint_reader(input)?;
        Ok(self.lookup_sha1(&hash)?.into_iter()
            .filter(|hit| hit.media.size == size).collect())
    }

    pub fn search_titles(&self, query: &str, limit: usize)
        -> Result<CollectionTitleSearch<'_>, CatalogError>
    {
        if limit == 0 || limit > 200 {
            return Err(CatalogError::Invalid("title search limit must be in 1..=200".into()));
        }
        let mut matches = Vec::new();
        let mut total_source_records = 0usize;
        for index in &self.indexes {
            let remaining = limit.saturating_sub(total_source_records.min(limit));
            // Query every platform to retain the global total, even after filling the limit.
            let found = index.search_titles(query, remaining.max(1))?;
            total_source_records += found.total;
            if remaining != 0 {
                for record in found.records {
                    for media in &record.roms {
                        matches.push(MediaMatch {
                            platform: index.platform(), record, media, source: index.source(),
                        });
                    }
                }
            }
        }
        Ok(CollectionTitleSearch { total_source_records, matches })
    }
}

/// Versioned bibliographic source-claim indexes for all registered platforms.
pub struct EnrichedCatalogCollection {
    indexes: Vec<EnrichedPlatformCatalog>,
}

impl EnrichedCatalogCollection {
    pub fn open(root: impl AsRef<Path>) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let indexes = registered_platforms(root)?.iter()
            .map(|p| EnrichedPlatformCatalog::open(root, p))
            .collect::<Result<Vec<_>, _>>()?;
        Ok(Self { indexes })
    }

    pub fn platform_ids(&self) -> impl Iterator<Item = &str> {
        self.indexes.iter().map(|index| index.base().platform())
    }

    pub fn lookup_sha1(&self, value: &str) -> Result<Vec<EnrichedMediaMatch<'_>>, CatalogError> {
        let mut matches = Vec::new();
        for index in &self.indexes {
            matches.extend(index.lookup_sha1(value)?);
        }
        Ok(matches)
    }

    pub fn lookup_crc32(&self, value: &str, size: u64)
        -> Result<Vec<EnrichedMediaMatch<'_>>, CatalogError>
    {
        let mut matches = Vec::new();
        for index in &self.indexes {
            matches.extend(index.lookup_crc32(value, size)?);
        }
        Ok(matches)
    }

    pub fn lookup_bytes(&self, data: &[u8])
        -> Result<Vec<EnrichedMediaMatch<'_>>, CatalogError>
    {
        self.lookup_reader(data)
    }

    pub fn lookup_reader<R: Read>(&self, input: R)
        -> Result<Vec<EnrichedMediaMatch<'_>>, CatalogError>
    {
        let (hash, size) = fingerprint_reader(input)?;
        Ok(self.lookup_sha1(&hash)?.into_iter()
            .filter(|hit| hit.base.media.size == size).collect())
    }

    pub fn search_titles(&self, query: &str, limit: usize)
        -> Result<EnrichedCollectionTitleSearch<'_>, CatalogError>
    {
        if limit == 0 || limit > 200 {
            return Err(CatalogError::Invalid("title search limit must be in 1..=200".into()));
        }
        let mut matches = Vec::new();
        let mut total_source_records = 0usize;
        for index in &self.indexes {
            let remaining = limit.saturating_sub(total_source_records.min(limit));
            let found = index.search_titles(query, remaining.max(1))?;
            total_source_records += found.total_records;
            if remaining != 0 {
                matches.extend(found.matches);
            }
        }
        Ok(EnrichedCollectionTitleSearch { total_source_records, matches })
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
    fn accession_registry_is_dynamic_and_integrity_checked() {
        let all = CatalogCollection::open(root()).unwrap();
        let ids = all.platform_ids().collect::<Vec<_>>();
        assert!(ids.contains(&"snes") && ids.contains(&"genesis"));
        assert!(ids.len() >= 10);
    }

    #[test]
    fn exact_media_and_titles_retain_individual_platform_matches() {
        let all = CatalogCollection::open(root()).unwrap();
        let hits = all.lookup_sha1("6B47BB75D16514B6A476AA0C73A683A2A4C18765").unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].platform, "snes");
        assert_eq!(hits[0].record.name, "Super Mario World (USA)");
        let titles = all.search_titles("mario", 3).unwrap();
        assert!(titles.total_source_records >= 3);
        assert!(!titles.matches.is_empty());
        assert!(titles.matches.iter().all(|m| m.record.name.to_lowercase().contains("mario")));
        assert!(all.search_titles(" ", 5).is_err());
        assert!(all.search_titles("mario", 0).is_err());
        assert!(all.search_titles("mario", 201).is_err());
        assert!(all.lookup_reader(&b"synthetic bytes"[..]).unwrap().is_empty());
    }

    #[test]
    fn enriched_matches_do_not_lose_source_claims() {
        let all = EnrichedCatalogCollection::open(root()).unwrap();
        let hits = all.lookup_sha1("6B47BB75D16514B6A476AA0C73A683A2A4C18765").unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].base.platform, "snes");
        assert!(hits[0].metadata_claims.iter().all(|c| c.resolution.status == "matched"));
        assert!(all.search_titles("metroid", 0).is_err());
        let result = all.search_titles("metroid", 2).unwrap();
        assert!(result.total_source_records >= 2);
        assert!(!result.matches.is_empty());
        assert!(all.lookup_reader(&b"synthetic bytes"[..]).unwrap().is_empty());
    }
}
