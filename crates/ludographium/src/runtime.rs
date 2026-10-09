//! Complete, read-only verification of an extracted metadata runtime.
//!
//! Unlike per-platform lookup, this checks every artifact in the published
//! distribution manifest. It never requires the preserved upstream DAT files.
use crate::CatalogError;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::{self, File};
use std::io::{BufReader, Read};
use std::path::{Component, Path, PathBuf};

#[derive(Debug)]
pub struct RuntimeVerification {
    pub artifact_count: usize,
    pub total_artifact_bytes: u64,
    pub source_id: String,
    pub source_revision: String,
}

#[derive(Deserialize)]
struct Distribution {
    schema_version: u32,
    kind: String,
    source_id: String,
    source_revision: String,
    artifacts: Vec<Artifact>,
}

#[derive(Deserialize)]
struct Artifact {
    path: String,
    bytes: u64,
    sha256: String,
}

#[derive(Deserialize)]
struct CatalogHeader {
    schema_version: u32,
    kind: String,
    source_id: String,
    source_revision: String,
    platforms: Vec<PlatformHeader>,
}

#[derive(Deserialize)]
struct PlatformHeader {
    platform: String,
    artifact_path: String,
}

fn invalid(message: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(message.into())
}

/// Allow only artifact shapes emitted by the v1 metadata-only packager.
fn allowed_artifact(path: &str) -> bool {
    if path == "METADATA-NOTICE.md"
        || path == "sources/libretro-no-intro.json"
        || path == "sources/libretro-enrichment.json"
    {
        return true;
    }
    let components: Vec<_> = Path::new(path).components().collect();
    if components.len() != 3 {
        return false;
    }
    if components[0] != Component::Normal("generated".as_ref()) {
        return false;
    }
    if !matches!(
        components[1],
        Component::Normal(dir)
            if dir == "v1" || dir == "enrichment-v1" || dir == "curated-v1"
    ) {
        return false;
    }
    let Component::Normal(file) = components[2] else {
        return false;
    };
    let Some(file) = file.to_str() else {
        return false;
    };
    file.ends_with(".json")
        && file.len() > ".json".len()
        && file.bytes().all(|ch| {
            ch.is_ascii_lowercase() || ch.is_ascii_digit() || matches!(ch, b'.' | b'_' | b'-')
        })
}

/// Reject symlinks and non-files, including symlinks in intermediate
/// directories. Do not follow an attacker-selected filesystem entry.
fn regular_file(root: &Path, relative: &str) -> Result<PathBuf, CatalogError> {
    let mut path = root.to_path_buf();
    for component in Path::new(relative).components() {
        let Component::Normal(part) = component else {
            return Err(invalid(format!("unsafe runtime path: {relative}")));
        };
        path.push(part);
        let meta = fs::symlink_metadata(&path)?;
        if meta.file_type().is_symlink() {
            return Err(invalid(format!("symlink in runtime path: {relative}")));
        }
    }
    if !fs::metadata(&path)?.is_file() {
        return Err(invalid(format!("not a regular runtime file: {relative}")));
    }
    Ok(path)
}

/// Verify all published artifacts, sizes and SHA-256 values using bounded
/// memory. The distribution manifest itself is authenticated only by the
/// release archive checksum, not by this self-contained audit.
pub fn verify_runtime_root(root: impl AsRef<Path>) -> Result<RuntimeVerification, CatalogError> {
    let root = root.as_ref();
    let raw = fs::read(regular_file(root, "generated/v1/distribution.json")?)?;
    let distribution: Distribution = serde_json::from_slice(&raw)?;
    if distribution.schema_version != 1
        || distribution.kind != "ludographium-distribution"
        || distribution.source_id.is_empty()
        || distribution.source_revision.is_empty()
        || distribution.artifacts.is_empty()
    {
        return Err(invalid(
            "invalid or unsupported runtime distribution manifest",
        ));
    }

    let mut seen = HashSet::new();
    let mut total_artifact_bytes = 0u64;
    for artifact in &distribution.artifacts {
        if !allowed_artifact(&artifact.path) || !seen.insert(artifact.path.as_str()) {
            return Err(invalid(format!(
                "unsafe or duplicate runtime artifact: {}",
                artifact.path
            )));
        }
        if artifact.sha256.len() != 64 || !artifact.sha256.bytes().all(|ch| ch.is_ascii_hexdigit())
        {
            return Err(invalid(format!(
                "invalid SHA-256 in distribution entry: {}",
                artifact.path
            )));
        }
        let path = regular_file(root, &artifact.path)?;
        if fs::metadata(&path)?.len() != artifact.bytes {
            return Err(invalid(format!("byte length mismatch: {}", artifact.path)));
        }
        let mut reader = BufReader::new(File::open(&path)?);
        let mut hasher = Sha256::new();
        let mut count = 0u64;
        let mut buffer = [0u8; 65_536];
        loop {
            let n = reader.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            count = count
                .checked_add(n as u64)
                .ok_or_else(|| invalid("runtime byte count overflow"))?;
            if count > artifact.bytes {
                return Err(invalid(format!(
                    "file expanded while hashing: {}",
                    artifact.path
                )));
            }
            hasher.update(&buffer[..n]);
        }
        if count != artifact.bytes || format!("{:x}", hasher.finalize()) != artifact.sha256 {
            return Err(invalid(format!("SHA-256 mismatch: {}", artifact.path)));
        }
        total_artifact_bytes = total_artifact_bytes
            .checked_add(count)
            .ok_or_else(|| invalid("distribution total byte count overflow"))?;
    }

    for path in [
        "generated/v1/catalog.json",
        "generated/curated-v1/identities.json",
        "sources/libretro-no-intro.json",
        "sources/libretro-enrichment.json",
        "METADATA-NOTICE.md",
    ] {
        if !seen.contains(path) {
            return Err(invalid(format!(
                "missing required runtime artifact: {path}"
            )));
        }
    }

    let catalog_bytes = fs::read(regular_file(root, "generated/v1/catalog.json")?)?;
    let catalog: CatalogHeader = serde_json::from_slice(&catalog_bytes)?;
    if catalog.schema_version != 1
        || catalog.kind != "source-catalog"
        || catalog.source_id != distribution.source_id
        || catalog.source_revision != distribution.source_revision
        || catalog.platforms.is_empty()
    {
        return Err(invalid(
            "runtime catalog and distribution identities disagree",
        ));
    }
    let mut platforms = HashSet::new();
    for platform in &catalog.platforms {
        if platform.platform.is_empty() || !platforms.insert(&platform.platform) {
            return Err(invalid("invalid or duplicate catalog platform"));
        }
        let path = format!("generated/v1/{}.json", platform.platform);
        if platform.artifact_path != path || !seen.contains(path.as_str()) {
            return Err(invalid(format!(
                "missing or mismatched platform bundle: {}",
                platform.platform
            )));
        }
    }

    Ok(RuntimeVerification {
        artifact_count: distribution.artifacts.len(),
        total_artifact_bytes,
        source_id: distribution.source_id,
        source_revision: distribution.source_revision,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn runtime_archive_paths_only() {
        assert!(allowed_artifact("generated/v1/gb.json"));
        assert!(allowed_artifact("generated/enrichment-v1/gb.json"));
        assert!(allowed_artifact("generated/curated-v1/identities.json"));
        assert!(allowed_artifact("METADATA-NOTICE.md"));
        for wrong in [
            "../outside",
            "/etc/passwd",
            "generated/v1/../secret.json",
            "generated/v1/gb.zip",
            "generated/v1/foo/bar.json",
            "sources/private.json",
            "generated/unpinned/a.json",
        ] {
            assert!(!allowed_artifact(wrong), "{wrong}");
        }
    }

    #[test]
    fn validates_current_extracted_runtime_contract() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        let result = verify_runtime_root(root).unwrap();
        assert_eq!(result.artifact_count, 25);
        assert_eq!(result.source_id, "libretro-no-intro");
        assert!(result.total_artifact_bytes > 0);
    }
}
