//! Integrity test for all locally cloned *original text* console metadata.
//! Does not need Python, SQLite, network access, or generated artifacts.
use serde_json::Value;
use sha1::{Digest, Sha1};
use std::collections::HashSet;
use std::fs;
use std::path::{Component, Path, PathBuf};

fn root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repository root")
}

fn blob_hash(data: &[u8]) -> String {
    let mut hasher = Sha1::new();
    hasher.update(format!("blob {}\0", data.len()).as_bytes());
    hasher.update(data);
    format!("{:x}", hasher.finalize())
}

fn assert_pinned_text_blob(root: &Path, entry: &Value, seen: &mut HashSet<String>) -> u64 {
    let relative = entry["source_path"].as_str().expect("original source path");
    let upstream = Path::new(relative);
    assert!(
        relative.starts_with("metadat/")
            && relative.ends_with(".dat")
            && upstream
                .components()
                .all(|component| matches!(component, Component::Normal(_))),
        "untrusted source path: {relative}"
    );
    assert!(
        seen.insert(relative.to_owned()),
        "duplicate source: {relative}"
    );
    let local = root.join("archive/libretro-bulk").join(relative);
    let raw = fs::read(&local)
        .unwrap_or_else(|err| panic!("missing offline-clone source {}: {err}", local.display()));
    let expected_size = entry["bytes"].as_u64().expect("source byte count");
    assert_eq!(raw.len() as u64, expected_size, "size drift: {relative}");
    let expected_sha = entry["git_blob_sha"].as_str().expect("Git blob SHA");
    assert_eq!(
        blob_hash(&raw),
        expected_sha,
        "source bytes drift: {relative}"
    );
    assert!(!raw.contains(&0), "NUL byte in source text: {relative}");
    std::str::from_utf8(&raw)
        .unwrap_or_else(|err| panic!("source is not UTF-8 text, {relative}: {err}"));
    expected_size
}

#[test]
fn every_expanded_console_and_bibliographic_dat_is_in_git_as_original_text() {
    let root = root();
    let platforms: Value = serde_json::from_slice(
        &fs::read(root.join("sources/bulk-expansion-v1.json")).expect("platform manifest"),
    )
    .expect("valid platform manifest");
    let fields: Value = serde_json::from_slice(
        &fs::read(root.join("sources/bulk-fields-v1.json")).expect("field manifest"),
    )
    .expect("valid field manifest");

    assert_eq!(platforms["schema_version"], 1);
    assert_eq!(fields["schema_version"], 1);
    assert_eq!(platforms["kind"], "pinned-bulk-platform-expansion");
    assert_eq!(fields["kind"], "pinned-bulk-bibliographic-expansion");
    assert_eq!(platforms["declared_repository_license"], "CC-BY-SA-4.0");
    assert_eq!(fields["declared_repository_license"], "CC-BY-SA-4.0");
    let revision = "fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90";
    assert_eq!(platforms["repository_revision"], revision);
    assert_eq!(fields["repository_revision"], revision);

    let ids = platforms["platforms"].as_array().expect("platform list");
    let claims = fields["files"].as_array().expect("field list");
    assert_eq!(ids.len(), 65, "source coverage unexpectedly changed");
    assert_eq!(
        claims.len(),
        279,
        "bibliographic coverage unexpectedly changed"
    );

    let mut seen = HashSet::new();
    let mut total_size = 0u64;
    for entry in ids.iter().chain(claims) {
        total_size += assert_pinned_text_blob(&root, entry, &mut seen);
    }
    assert_eq!(seen.len(), 344);
    assert_eq!(total_size, 24_212_591, "complete source corpus size drift");

    // The DAT manifest must account for every file; unregistered extras could
    // otherwise silently inflate the corpus or evade provenance review.
    fn scan(dir: &Path, root: &Path, listed: &HashSet<String>, visited: &mut usize) {
        for entry in fs::read_dir(dir).expect("source directory") {
            let entry = entry.expect("directory entry");
            let path = entry.path();
            if path.is_dir() {
                scan(&path, root, listed, visited);
            } else {
                let relative = path.strip_prefix(root).expect("source path");
                let key = relative
                    .to_str()
                    .expect("UTF-8 relative path")
                    .replace('\\', "/");
                assert!(listed.contains(&key), "unregistered metadata source {key}");
                *visited += 1;
            }
        }
    }
    let archive_root = root.join("archive/libretro-bulk");
    let mut visited = 0;
    scan(
        &archive_root.join("metadat"),
        &archive_root,
        &seen,
        &mut visited,
    );
    assert_eq!(visited, 344);
}
