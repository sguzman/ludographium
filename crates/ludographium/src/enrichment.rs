//! Source-attributed publisher/developer/date/genre claims attached to exact media records.
//!
//! Unlike canonical game identities, a claim's target is a particular source occurrence.
//! Disagreements and unresolved claims are returned separately.

use crate::{CatalogError, MediaMatch, PlatformCatalog};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Debug, Deserialize)]
struct EnrichmentBundle {
    schema_version: u32,
    kind: String,
    platform: String,
    source_id: String,
    source_revision: String,
    base_source_id: String,
    base_source_revision: String,
    claim_count: usize,
    resolution_counts: HashMap<String, usize>,
    claims: Vec<MetadataClaim>,
}

#[derive(Debug, Deserialize)]
struct Distribution {
    schema_version: u32,
    kind: String,
    source_revision: String,
    artifacts: Vec<Artifact>,
}

#[derive(Debug, Deserialize)]
struct Artifact {
    path: String,
    bytes: usize,
    sha256: String,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct ClaimResolution {
    pub status: String,
    pub base_source_ordinal: Option<usize>,
}

#[derive(Debug, Deserialize, Serialize)]
pub struct MetadataClaim {
    pub field: String,
    pub value: Option<String>,
    pub crc32: String,
    pub source_ordinal: usize,
    pub source_comment: Option<String>,
    pub source_path: String,
    pub source_blob_sha: String,
    pub resolution: ClaimResolution,
}

#[derive(Debug)]
pub struct EnrichedMediaMatch<'a> {
    pub base: MediaMatch<'a>,
    pub metadata_claims: Vec<&'a MetadataClaim>,
    pub unresolved_source_claims: Vec<&'a MetadataClaim>,
}

/// Loads the base index and all per-platform enriched claims from a verified distribution.
/// This index never silently promotes an unmatched claim into an asserted game fact.
pub struct EnrichedPlatformCatalog {
    base: PlatformCatalog,
    source_id: String,
    claims: Vec<MetadataClaim>,
    attached: HashMap<(usize, String), Vec<usize>>,
    unresolved: HashMap<String, Vec<usize>>,
}

fn valid_hash(s: &str, width: usize) -> bool {
    s.len() == width && s.bytes().all(|b| b.is_ascii_hexdigit())
}

fn checked_enrichment_file(root: &Path, platform: &str) -> Result<Vec<u8>, CatalogError> {
    let distribution: Distribution =
        serde_json::from_slice(&fs::read(root.join("generated/v1/distribution.json"))?)?;
    if distribution.schema_version != 1 || distribution.kind != "ludographium-distribution" {
        return Err(CatalogError::Invalid(
            "invalid distribution manifest".into(),
        ));
    }
    let path = format!("generated/enrichment-v1/{platform}.json");
    let matching: Vec<_> = distribution
        .artifacts
        .iter()
        .filter(|a| a.path == path)
        .collect();
    if matching.len() != 1 {
        return Err(CatalogError::Invalid(format!(
            "missing or duplicate enrichment artifact: {platform}"
        )));
    }
    let bytes = fs::read(root.join(&path))?;
    let artifact = matching[0];
    let mut digest = Sha256::new();
    digest.update(&bytes);
    let actual = format!("{:x}", digest.finalize());
    if bytes.len() != artifact.bytes || artifact.sha256 != actual {
        return Err(CatalogError::Invalid(format!(
            "enrichment SHA-256 mismatch: {platform}"
        )));
    }
    let base: serde_json::Value =
        serde_json::from_slice(&fs::read(root.join("generated/v1/catalog.json"))?)?;
    if base["source_revision"] != distribution.source_revision {
        return Err(CatalogError::Invalid(
            "distribution/base revision mismatch".into(),
        ));
    }
    Ok(bytes)
}

impl EnrichedPlatformCatalog {
    pub fn open(root: impl AsRef<Path>, platform: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        // Includes Git blob and SHA-256 checks on the base bundle.
        let base = PlatformCatalog::open(root, platform)?;
        let bytes = checked_enrichment_file(root, platform)?;
        let bundle: EnrichmentBundle = serde_json::from_slice(&bytes)?;
        if bundle.schema_version != 1
            || bundle.kind != "source-enrichment-claims"
            || bundle.platform != platform
            || bundle.source_id.is_empty()
            || bundle.source_revision != base.source().revision
            || bundle.base_source_id != base.source().source_id
            || bundle.base_source_revision != base.source().revision
            || bundle.claim_count != bundle.claims.len()
        {
            return Err(CatalogError::Invalid(
                "enrichment/base metadata mismatch".into(),
            ));
        }

        let mut attached: HashMap<(usize, String), Vec<usize>> = HashMap::new();
        let mut unresolved: HashMap<String, Vec<usize>> = HashMap::new();
        let mut counted: HashMap<String, usize> = HashMap::new();
        for (index, claim) in bundle.claims.iter().enumerate() {
            if !valid_hash(&claim.crc32, 8)
                || !valid_hash(&claim.source_blob_sha, 40)
                || claim.source_ordinal == 0
                || claim.field.is_empty()
                || claim.source_path.is_empty()
            {
                return Err(CatalogError::Invalid(
                    "malformed provenance-bearing claim".into(),
                ));
            }
            *counted.entry(claim.resolution.status.clone()).or_insert(0) += 1;
            if claim.resolution.status == "matched" {
                let ordinal = claim.resolution.base_source_ordinal.ok_or_else(|| {
                    CatalogError::Invalid("matched claim has no source target".into())
                })?;
                let record = base.source_record(ordinal).ok_or_else(|| {
                    CatalogError::Invalid("matched claim has invalid source target".into())
                })?;
                let comment_matches = claim.source_comment.as_deref() == Some(record.name.as_str());
                let media_matches = record
                    .roms
                    .iter()
                    .any(|m| m.crc32.as_deref() == Some(&claim.crc32));
                if claim.value.is_none() || !comment_matches || !media_matches {
                    return Err(CatalogError::Invalid(
                        "matched claim contradicts base evidence".into(),
                    ));
                }
                attached
                    .entry((ordinal, claim.crc32.clone()))
                    .or_default()
                    .push(index);
            } else if matches!(
                claim.resolution.status.as_str(),
                "unmatched_crc"
                    | "ambiguous_crc"
                    | "missing_comment"
                    | "comment_mismatch"
                    | "missing_value"
            ) {
                if claim.resolution.base_source_ordinal.is_some() {
                    return Err(CatalogError::Invalid(
                        "unresolved claim has a target".into(),
                    ));
                }
                unresolved
                    .entry(claim.crc32.clone())
                    .or_default()
                    .push(index);
            } else {
                return Err(CatalogError::Invalid(
                    "unrecognized enrichment resolution".into(),
                ));
            }
        }
        if counted != bundle.resolution_counts {
            return Err(CatalogError::Invalid(
                "enrichment resolution counts mismatch".into(),
            ));
        }
        Ok(Self {
            base,
            source_id: bundle.source_id,
            claims: bundle.claims,
            attached,
            unresolved,
        })
    }

    pub fn source_id(&self) -> &str {
        &self.source_id
    }

    pub fn base(&self) -> &PlatformCatalog {
        &self.base
    }

    pub fn claim_count(&self) -> usize {
        self.claims.len()
    }

    fn attach<'a>(&'a self, matches: Vec<MediaMatch<'a>>) -> Vec<EnrichedMediaMatch<'a>> {
        matches
            .into_iter()
            .map(|base| {
                let ordinal = base.record.source_ordinal;
                let crc = base.media.crc32.as_deref().unwrap_or("");
                let refs = self.attached.get(&(ordinal, crc.to_owned()));
                let metadata_claims = refs
                    .into_iter()
                    .flat_map(|v| v.iter())
                    .map(|index| &self.claims[*index])
                    .collect();
                let unresolved_source_claims = self
                    .unresolved
                    .get(crc)
                    .into_iter()
                    .flat_map(|v| v.iter())
                    .map(|index| &self.claims[*index])
                    .collect();
                EnrichedMediaMatch {
                    base,
                    metadata_claims,
                    unresolved_source_claims,
                }
            })
            .collect()
    }

    pub fn lookup_sha1(&self, hash: &str) -> Result<Vec<EnrichedMediaMatch<'_>>, CatalogError> {
        Ok(self.attach(self.base.lookup_sha1(hash)?))
    }

    pub fn lookup_crc32(
        &self,
        hash: &str,
        size: u64,
    ) -> Result<Vec<EnrichedMediaMatch<'_>>, CatalogError> {
        Ok(self.attach(self.base.lookup_crc32(hash, size)?))
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
    fn all_platform_enrichments_are_integrity_checked() {
        for platform in ["snes", "gb", "gbc", "gba"] {
            let catalog = EnrichedPlatformCatalog::open(root(), platform).unwrap();
            assert!(catalog.claim_count() > 1000);
            assert_eq!(catalog.source_id(), "libretro-metadata");
        }
    }

    #[test]
    fn known_game_has_attributed_metadata() {
        let catalog = EnrichedPlatformCatalog::open(root(), "gba").unwrap();
        let matches = catalog
            .lookup_sha1("FC6163F99B71B05C10686A0D29010B31274E1DC4")
            .unwrap();
        assert_eq!(matches.len(), 1);
        assert!(matches[0]
            .metadata_claims
            .iter()
            .any(|claim| claim.field == "developer"
                && claim.value.as_deref() == Some("Griptonite Games")));
        assert!(matches[0]
            .metadata_claims
            .iter()
            .all(|claim| claim.resolution.status == "matched"));
    }

    #[test]
    fn invalid_hash_and_unknown_games() {
        let catalog = EnrichedPlatformCatalog::open(root(), "gb").unwrap();
        assert!(catalog.lookup_sha1("bogus").is_err());
        assert!(catalog.lookup_sha1(&"0".repeat(40)).unwrap().is_empty());
    }

    #[test]
    fn checksums_match_expected_sha256_vector() {
        let mut hash = Sha256::new();
        hash.update(b"abc");
        assert_eq!(
            format!("{:x}", hash.finalize()),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }
}
