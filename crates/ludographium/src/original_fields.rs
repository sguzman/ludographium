//! Read original, pinned Libretro bibliographic DATs without a database.
//! Claims are source observations. Matching them never asserts canonical identities.
use crate::original_dat::pairs;
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use sha1::{Digest, Sha1};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const REVISION: &str = "fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90";

#[derive(Debug, Deserialize)]
struct FieldRegister {
    schema_version: u32,
    source_id: String,
    repository_revision: String,
    declared_repository_license: String,
    #[serde(default)]
    kind: Option<String>,
    #[serde(default)]
    base_source_id: Option<String>,
    files: Vec<FieldFile>,
}

#[derive(Debug, Deserialize)]
struct FieldFile {
    platform: String,
    field: String,
    source_path: String,
    git_blob_sha: String,
    #[serde(default)]
    bytes: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct FieldResolution {
    pub status: String,
    pub base_source_ordinal: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct FieldClaim {
    pub platform: String,
    pub field: String,
    pub value: Option<String>,
    pub crc32: Option<String>,
    pub source_ordinal: usize,
    pub source_comment: Option<String>,
    pub source_fields: BTreeMap<String, String>,
    pub source_path: String,
    pub source_blob_sha: String,
    pub source_id: String,
    pub source_revision: String,
    pub resolution: FieldResolution,
}

#[derive(Debug)]
struct FieldRecord {
    ordinal: usize,
    values: BTreeMap<String, String>,
    crc32: Option<String>,
}

fn invalid(msg: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(msg.into())
}

fn blob_sha(bytes: &[u8]) -> String {
    let mut sha = Sha1::new();
    sha.update(format!("blob {}\0", bytes.len()).as_bytes());
    sha.update(bytes);
    format!("{:x}", sha.finalize())
}

fn field_directory(field: &str) -> Option<&'static str> {
    match field {
        "developer" => Some("developer"),
        "publisher" => Some("publisher"),
        "genre" => Some("genre"),
        "franchise" => Some("franchise"),
        "serial" => Some("serial"),
        "releaseyear" => Some("releaseyear"),
        "releasemonth" => Some("releasemonth"),
        "users" => Some("maxusers"),
        "esrb_rating" => Some("esrb"),
        "rumble" => Some("rumble"),
        _ => None,
    }
}

fn safe_file(entry: &FieldFile) -> bool {
    let Some(dir) = field_directory(&entry.field) else {
        return false;
    };
    let Some(name) = entry
        .source_path
        .strip_prefix(&format!("metadat/{dir}/"))
        .and_then(|name| name.strip_suffix(".dat"))
    else {
        return false;
    };
    !name.is_empty()
        && !name.contains('/')
        && !name.contains('\\')
        && name != "."
        && name != ".."
        && !entry.platform.is_empty()
        && entry
            .platform
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
        && entry.git_blob_sha.len() == 40
        && entry.git_blob_sha.bytes().all(|b| b.is_ascii_hexdigit())
}

fn add_rom(
    values: &mut BTreeMap<String, String>,
    crc: &mut Option<String>,
    attrs: BTreeMap<String, String>,
) -> Result<(), CatalogError> {
    for (key, value) in attrs {
        if key == "crc" {
            if value.len() != 8 || !value.bytes().all(|b| b.is_ascii_hexdigit()) || crc.is_some() {
                return Err(invalid("invalid or repeated bibliographic DAT CRC32"));
            }
            *crc = Some(value.to_ascii_uppercase());
        } else if values.insert(format!("rom_{key}"), value).is_some() {
            return Err(invalid("duplicate bibliographic ROM attribute"));
        }
    }
    Ok(())
}

/// Parse bibliographic DATs, which have comments and a per-field value
/// instead of an identification DAT's required name/media pair.
fn parse_field_dat(bytes: &[u8]) -> Result<Vec<FieldRecord>, CatalogError> {
    let text = std::str::from_utf8(bytes).map_err(|_| invalid("field DAT is not UTF-8"))?;
    let mut records = Vec::new();
    let mut values = BTreeMap::new();
    let mut crc = None;
    let mut in_game = false;
    let mut in_rom = false;
    for (index, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if !in_game {
            if line == "game (" {
                in_game = true;
                values.clear();
                crc = None;
            }
            continue;
        }
        if in_rom {
            if line == ")" {
                in_rom = false;
            } else if !line.is_empty() {
                add_rom(&mut values, &mut crc, pairs(line)?)?;
            }
        } else if line == ")" {
            records.push(FieldRecord {
                ordinal: records.len() + 1,
                values: std::mem::take(&mut values),
                crc32: crc.take(),
            });
            in_game = false;
        } else if line == "game (" {
            return Err(invalid(format!(
                "nested field DAT game at line {}",
                index + 1
            )));
        } else if line == "rom (" {
            in_rom = true;
        } else if let Some(attrs) = line.strip_prefix("rom (").and_then(|s| s.strip_suffix(')')) {
            add_rom(&mut values, &mut crc, pairs(attrs)?)?;
        } else if !line.is_empty() {
            let mut attrs = pairs(line)?;
            if attrs.len() != 1 {
                return Err(invalid(format!(
                    "invalid field DAT scalar at line {}",
                    index + 1
                )));
            }
            let (key, value) = attrs.pop_first().expect("one attribute");
            if values.insert(key, value).is_some() {
                return Err(invalid(format!(
                    "duplicate field DAT scalar at line {}",
                    index + 1
                )));
            }
        }
    }
    if in_game || in_rom {
        return Err(invalid("unterminated bibliographic DAT game/ROM"));
    }
    Ok(records)
}

fn register(root: &Path, filename: &str, count: usize) -> Result<FieldRegister, CatalogError> {
    let manifest: FieldRegister =
        serde_json::from_slice(&fs::read(root.join("sources").join(filename))?)?;
    let bulk = filename == "bulk-fields-v1.json";
    if manifest.schema_version != 1
        || manifest.source_id != "libretro-metadata"
        || manifest.repository_revision != REVISION
        || manifest.declared_repository_license != "CC-BY-SA-4.0"
        || manifest.files.len() != count
        || (bulk
            && (manifest.kind.as_deref() != Some("pinned-bulk-bibliographic-expansion")
                || manifest.base_source_id.as_deref() != Some("libretro-no-intro")))
    {
        return Err(invalid(format!(
            "invalid bibliographic source register: {filename}"
        )));
    }
    let mut seen = HashSet::new();
    for file in &manifest.files {
        if !safe_file(file)
            || !seen.insert((file.platform.as_str(), file.field.as_str()))
            || (bulk
                && file
                    .bytes
                    .is_none_or(|size| size == 0 || size >= 50_000_000))
        {
            return Err(invalid(format!(
                "invalid bibliographic source entry: {filename}"
            )));
        }
    }
    Ok(manifest)
}

/// Preserve every claim (including missing-CRC and unmatched claims) in original
/// per-file/per-occurrence order. The caller resolves them against its platform index.
pub(crate) fn load_claims(
    root: &Path,
    selected_platforms: &HashSet<String>,
) -> Result<Vec<FieldClaim>, CatalogError> {
    let original = register(root, "libretro-enrichment.json", 88)?;
    let bulk = register(root, "bulk-fields-v1.json", 279)?;
    let mut claims = Vec::new();
    let mut seen = HashSet::new();
    for (manifest, expanded) in [(&original, false), (&bulk, true)] {
        for entry in &manifest.files {
            if !seen.insert((entry.platform.as_str(), entry.field.as_str())) {
                return Err(invalid(
                    "duplicate bibliographic platform/field across registers",
                ));
            }
            if !selected_platforms.contains(&entry.platform) {
                continue;
            }
            let path = if expanded {
                root.join("archive/libretro-bulk").join(&entry.source_path)
            } else {
                root.join("archive/libretro-enrichment")
                    .join(&entry.platform)
                    .join(format!("{}.dat", entry.field))
            };
            let bytes = fs::read(&path)?;
            if entry.bytes.is_some_and(|expected| expected != bytes.len())
                || blob_sha(&bytes) != entry.git_blob_sha
            {
                return Err(invalid(format!(
                    "bibliographic source hash/size mismatch: {}/{}",
                    entry.platform, entry.field
                )));
            }
            for record in parse_field_dat(&bytes)? {
                claims.push(FieldClaim {
                    platform: entry.platform.clone(),
                    field: entry.field.clone(),
                    value: record
                        .values
                        .get(&entry.field)
                        .or_else(|| record.values.get(&format!("rom_{}", entry.field)))
                        .cloned(),
                    crc32: record.crc32,
                    source_ordinal: record.ordinal,
                    source_comment: record.values.get("comment").cloned(),
                    source_fields: record.values,
                    source_path: entry.source_path.clone(),
                    source_blob_sha: entry.git_blob_sha.clone(),
                    source_id: manifest.source_id.clone(),
                    source_revision: manifest.repository_revision.clone(),
                    resolution: FieldResolution {
                        status: "unresolved".to_owned(),
                        base_source_ordinal: None,
                    },
                });
            }
        }
    }
    Ok(claims)
}

#[cfg(test)]
mod tests {
    use super::{load_claims, parse_field_dat};
    use std::collections::HashSet;
    use std::path::Path;

    #[test]
    fn reads_field_records_and_multiline_crc_without_losing_provenance() {
        let raw = br#"game (
 comment "Demo"
 developer "Studio"
 rom (
  crc DEADBEEF
  serial "ABC"
 )
)
game (
 comment "Serial only"
 rom ( serial "X" )
)
"#;
        let records = parse_field_dat(raw).unwrap();
        assert_eq!(records.len(), 2);
        assert_eq!(records[0].crc32.as_deref(), Some("DEADBEEF"));
        assert_eq!(records[0].values["rom_serial"], "ABC");
        assert_eq!(records[1].crc32, None);
        assert_eq!(records[1].values["rom_serial"], "X");
    }

    #[test]
    fn reads_all_367_pinned_field_sources() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let base = serde_json::from_slice::<serde_json::Value>(
            &std::fs::read(root.join("sources/libretro-no-intro.json")).unwrap(),
        )
        .unwrap();
        let extended = serde_json::from_slice::<serde_json::Value>(
            &std::fs::read(root.join("sources/bulk-expansion-v1.json")).unwrap(),
        )
        .unwrap();
        let mut platforms = HashSet::new();
        for source in base["files"].as_array().unwrap() {
            platforms.insert(source["platform"].as_str().unwrap().to_owned());
        }
        for source in extended["platforms"].as_array().unwrap() {
            platforms.insert(source["platform"].as_str().unwrap().to_owned());
        }
        assert_eq!(platforms.len(), 75);
        let claims = load_claims(&root, &platforms).unwrap();
        assert_eq!(claims.len(), 167_640);
        assert!(claims.iter().any(|c| c.crc32.is_none()));
    }
}
