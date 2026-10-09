//! Evidence-validated, read-only work/release/build identities for exact media matches.
//!
//! Identity mappings are opt-in and never inferred by title or a CRC32 alone.
//! They require the original source occurrence and byte fingerprint to agree.
use crate::{CatalogError, MediaMatch, PlatformCatalog};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::Path;

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct EvidenceLocator {
    pub source_id: String,
    pub source_revision: String,
    pub source_path: String,
    pub source_blob_sha: String,
    pub source_ordinal: usize,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CuratedWork {
    pub id: String,
    pub preferred_title: String,
    pub rationale: String,
    pub evidence: Vec<EvidenceLocator>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CuratedRelease {
    pub id: String,
    pub work_id: String,
    pub platform: String,
    pub release_label: String,
    pub rationale: String,
    pub evidence: Vec<EvidenceLocator>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ExactMedia {
    pub sha1: String,
    pub size: u64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct CuratedBuild {
    pub id: String,
    pub release_id: String,
    pub build_label: String,
    pub rationale: String,
    pub media: ExactMedia,
    pub evidence: Vec<EvidenceLocator>,
}

#[derive(Debug, Deserialize)]
struct Export {
    schema_version: u32,
    kind: String,
    works: Vec<CuratedWork>,
    releases: Vec<CuratedRelease>,
    builds: Vec<CuratedBuild>,
}

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    kind: String,
    artifacts: Vec<Artifact>,
}

#[derive(Debug, Deserialize)]
struct Artifact {
    path: String,
    bytes: usize,
    sha256: String,
}

/// Borrowed matches return IDs and original rationales without copying catalog data.
#[derive(Debug)]
pub struct CuratedMediaMatch<'a> {
    pub work: &'a CuratedWork,
    pub release: &'a CuratedRelease,
    pub build: &'a CuratedBuild,
}

/// An integrity-checked curated identity graph indexed by exact source media.
pub struct CuratedCatalog {
    works: Vec<CuratedWork>,
    releases: Vec<CuratedRelease>,
    builds: Vec<CuratedBuild>,
    work_by_id: HashMap<String, usize>,
    release_by_id: HashMap<String, usize>,
    by_fingerprint: HashMap<(String, String, u64), Vec<usize>>,
}

fn locator_matches(found: &MediaMatch<'_>, ref_: &EvidenceLocator) -> bool {
    ref_.source_id == found.source.source_id
        && ref_.source_revision == found.source.revision
        && ref_.source_path == found.source.path
        && ref_.source_blob_sha == found.source.git_blob_sha
        && ref_.source_ordinal == found.record.source_ordinal
}

fn integrity_checked_bytes(root: &Path) -> Result<Vec<u8>, CatalogError> {
    let raw = fs::read(root.join("generated/v1/distribution.json"))?;
    let manifest: Manifest = serde_json::from_slice(&raw)?;
    if manifest.schema_version != 1 || manifest.kind != "ludographium-distribution" {
        return Err(CatalogError::Invalid(
            "invalid curated distribution manifest".into(),
        ));
    }
    let path = "generated/curated-v1/identities.json";
    let matching: Vec<_> = manifest
        .artifacts
        .iter()
        .filter(|a| a.path == path)
        .collect();
    if matching.len() != 1 {
        return Err(CatalogError::Invalid(
            "missing or duplicated curated artifact".into(),
        ));
    }
    let bytes = fs::read(root.join(path))?;
    let entry = matching[0];
    let mut digest = Sha256::new();
    digest.update(&bytes);
    if bytes.len() != entry.bytes || format!("{:x}", digest.finalize()) != entry.sha256 {
        return Err(CatalogError::Invalid(
            "curated artifact integrity mismatch".into(),
        ));
    }
    Ok(bytes)
}

impl CuratedCatalog {
    pub fn open(root: impl AsRef<Path>) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let bytes = integrity_checked_bytes(root)?;
        let export: Export = serde_json::from_slice(&bytes)?;
        if export.schema_version != 1 || export.kind != "curated-identity-ledger" {
            return Err(CatalogError::Invalid(
                "unsupported curated identity export".into(),
            ));
        }
        let mut seen = HashSet::new();
        let mut works = HashMap::new();
        for (index, item) in export.works.iter().enumerate() {
            if !seen.insert(&item.id) || item.evidence.is_empty() || item.preferred_title.is_empty()
            {
                return Err(CatalogError::Invalid(
                    "invalid or duplicated curated work".into(),
                ));
            }
            works.insert(item.id.clone(), index);
        }
        let mut releases = HashMap::new();
        for (index, item) in export.releases.iter().enumerate() {
            if !seen.insert(&item.id)
                || !works.contains_key(&item.work_id)
                || item.evidence.is_empty()
                || item.release_label.is_empty()
            {
                return Err(CatalogError::Invalid(
                    "invalid curated release relationship".into(),
                ));
            }
            releases.insert(item.id.clone(), index);
        }

        let mut by_fingerprint: HashMap<(String, String, u64), Vec<usize>> = HashMap::new();
        let mut platform_catalogs: HashMap<String, PlatformCatalog> = HashMap::new();
        for (index, item) in export.builds.iter().enumerate() {
            let release = releases
                .get(&item.release_id)
                .map(|i| &export.releases[*i])
                .ok_or_else(|| CatalogError::Invalid("orphan curated build".into()))?;
            if !seen.insert(&item.id)
                || item.evidence.is_empty()
                || item.media.size == 0
                || item.media.sha1.len() != 40
                || !item.media.sha1.bytes().all(|b| b.is_ascii_hexdigit())
            {
                return Err(CatalogError::Invalid(
                    "invalid curated build fingerprint or ID".into(),
                ));
            }
            if !platform_catalogs.contains_key(&release.platform) {
                platform_catalogs.insert(
                    release.platform.clone(),
                    PlatformCatalog::open(root, &release.platform)?,
                );
            }
            let source = &platform_catalogs[&release.platform];
            let found = source.lookup_sha1(&item.media.sha1)?;
            if !found.iter().any(|m| {
                m.media.size == item.media.size
                    && item.evidence.iter().any(|ref_| locator_matches(m, ref_))
            }) {
                return Err(CatalogError::Invalid(
                    "curated media is absent from its original evidence".into(),
                ));
            }
            let key = (
                release.platform.clone(),
                item.media.sha1.clone(),
                item.media.size,
            );
            by_fingerprint.entry(key).or_default().push(index);
        }

        Ok(Self {
            works: export.works,
            releases: export.releases,
            builds: export.builds,
            work_by_id: works,
            release_by_id: releases,
            by_fingerprint,
        })
    }

    pub fn counts(&self) -> (usize, usize, usize) {
        (self.works.len(), self.releases.len(), self.builds.len())
    }

    /// Resolve only builds whose exact original cited occurrence matches this media.
    /// The empty list means that source media is not curated, not that the game is unknown.
    pub fn for_media(&self, found: &MediaMatch<'_>) -> Vec<CuratedMediaMatch<'_>> {
        let Some(sha1) = found.media.sha1.as_deref() else {
            return Vec::new();
        };
        let key = (found.platform.to_owned(), sha1.to_owned(), found.media.size);
        self.by_fingerprint
            .get(&key)
            .into_iter()
            .flat_map(|v| v.iter())
            .filter_map(|i| {
                let build = &self.builds[*i];
                if !build
                    .evidence
                    .iter()
                    .any(|ref_| locator_matches(found, ref_))
                {
                    return None;
                }
                let release = &self.releases[*self.release_by_id.get(&build.release_id)?];
                let work = &self.works[*self.work_by_id.get(&release.work_id)?];
                Some(CuratedMediaMatch {
                    work,
                    release,
                    build,
                })
            })
            .collect()
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
    fn resolves_only_cited_exact_media_images() {
        let curated = CuratedCatalog::open(root()).unwrap();
        assert_eq!(curated.counts(), (8, 10, 12));
        let platform = PlatformCatalog::open(root(), "snes").unwrap();
        let hits = platform
            .lookup_sha1("6B47BB75D16514B6A476AA0C73A683A2A4C18765")
            .unwrap();
        assert_eq!(hits.len(), 1);
        let linked = curated.for_media(&hits[0]);
        assert_eq!(linked.len(), 1);
        assert_eq!(linked[0].work.preferred_title, "Super Mario World");
        assert_eq!(linked[0].release.platform, "snes");
        assert_eq!(linked[0].build.media.size, 524288);
        let unrelated = platform.lookup_sha1("0".repeat(40).as_str()).unwrap();
        assert!(unrelated.is_empty());
    }

    #[test]
    fn curated_revisions_have_distinct_sha1_and_exact_source_evidence() {
        let curated = CuratedCatalog::open(root()).unwrap();
        let gb = PlatformCatalog::open(root(), "gb").unwrap();
        let base = gb
            .lookup_sha1("3A4DDB39B234A67FFB361EE7ABC3D23E0A8B1C89")
            .unwrap();
        let rev1 = gb
            .lookup_sha1("418203621B887CAA090215D97E3F509B79AFFD3E")
            .unwrap();
        assert_eq!(base.len(), 1);
        assert_eq!(rev1.len(), 1);
        let a = curated.for_media(&base[0]);
        let b = curated.for_media(&rev1[0]);
        assert_eq!(a.len(), 1);
        assert_eq!(b.len(), 1);
        assert_eq!(a[0].work.id, b[0].work.id);
        assert_eq!(a[0].release.id, b[0].release.id);
        assert_ne!(a[0].build.id, b[0].build.id);
        assert_ne!(a[0].build.media.sha1, b[0].build.media.sha1);
        assert_eq!(a[0].work.preferred_title, "Super Mario Land");

        let gbc = PlatformCatalog::open(root(), "gbc").unwrap();
        let first = gbc
            .lookup_sha1("F4CD194BDEE0D04CA4EAC29E09B8E4E9D818C133")
            .unwrap();
        let revised = gbc
            .lookup_sha1("F2F52230B536214EF7C9924F483392993E226CFB")
            .unwrap();
        let x = curated.for_media(&first[0]);
        let y = curated.for_media(&revised[0]);
        assert_eq!(x.len(), 1);
        assert_eq!(y.len(), 1);
        assert_eq!(x[0].work.id, y[0].work.id);
        assert_ne!(x[0].release.id, y[0].release.id);
    }

    #[test]
    fn rejects_malformed_or_modified_curated_bytes() {
        let root = root();
        assert!(integrity_checked_bytes(&root).unwrap().len() > 100);
    }
}
