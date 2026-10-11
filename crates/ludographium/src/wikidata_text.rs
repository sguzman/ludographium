//! Read the pinned, CC0 Wikidata source JSONL as evidence, not verified game identities.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{collections::HashSet, fs, path::Path};

const REVISION: &str = "2026-10-09-pinned-sparql-snapshot";
const SNAPSHOT_SHA: &str = "db9d4c66041de776438b4316b34e1c648671889aea944efc6268446252f68734";

#[derive(Deserialize)]
struct Register {
    schema_version: u32,
    provider: String,
    provider_license: String,
    platforms: Vec<RegisterPlatform>,
}
#[derive(Deserialize)]
struct RegisterPlatform {
    platform: String,
    wikidata_platform: String,
}
#[derive(Deserialize)]
struct Manifest {
    schema_version: u32,
    kind: String,
    source_revision: String,
    source_snapshot_sha256: String,
    platform_collections: usize,
    item_platform_observations: usize,
    literal_date_claims: usize,
    original_query_rows: usize,
    files: Vec<ManifestFile>,
}
#[derive(Deserialize)]
struct ManifestFile {
    platform: String,
    wikidata_platform: String,
    text_path: String,
    text_sha256: String,
    text_bytes: usize,
    distinct_items: usize,
    source_rows: usize,
    source_response_sha256: String,
    source_query_sha256: String,
    received_at_utc: String,
}
#[derive(Debug, Deserialize, Serialize)]
pub struct WikidataDate {
    #[serde(rename = "type")]
    pub kind: String,
    pub value: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub datatype: Option<String>,
    #[serde(rename = "xml:lang", skip_serializing_if = "Option::is_none")]
    pub language: Option<String>,
}
#[derive(Debug, Deserialize, Serialize)]
pub struct WikidataItem {
    pub qid: String,
    pub english_label: Option<String>,
    pub dates: Vec<WikidataDate>,
}
struct Platform {
    id: String,
    wikidata_platform: String,
    source_sha256: String,
    received_at_utc: String,
    items: Vec<WikidataItem>,
}
pub struct WikidataTextCatalog {
    platforms: Vec<Platform>,
}

fn invalid(message: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(message.into())
}
fn valid_qid(qid: &str) -> bool {
    qid.strip_prefix('Q').is_some_and(|digits| {
        !digits.is_empty() && !digits.starts_with('0') && digits.bytes().all(|b| b.is_ascii_digit())
    })
}
fn valid_sha256(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|b| b.is_ascii_hexdigit())
}
fn sha256(bytes: &[u8]) -> String {
    let mut digest = Sha256::new();
    digest.update(bytes);
    format!("{:x}", digest.finalize())
}
fn parse_items(bytes: &[u8], platform: &str) -> Result<Vec<WikidataItem>, CatalogError> {
    let raw = std::str::from_utf8(bytes)
        .map_err(|_| invalid(format!("non-UTF-8 Wikidata source: {platform}")))?;
    let mut seen = HashSet::new();
    let mut records = Vec::new();
    for (ordinal, line) in raw.lines().enumerate() {
        if line.trim().is_empty() {
            return Err(invalid(format!(
                "blank Wikidata JSONL line at {platform}:{}",
                ordinal + 1
            )));
        }
        let record: WikidataItem = serde_json::from_str(line)?;
        if !valid_qid(&record.qid)
            || !seen.insert(record.qid.clone())
            || record
                .english_label
                .as_ref()
                .is_some_and(|x| x.trim().is_empty())
            || record
                .dates
                .iter()
                .any(|d| d.kind.is_empty() || d.value.is_empty())
        {
            return Err(invalid(format!(
                "malformed Wikidata record at {platform}:{}",
                ordinal + 1
            )));
        }
        records.push(record);
    }
    Ok(records)
}

impl WikidataTextCatalog {
    /// Hash-verify the original Git-committed JSONL and cross-check source registers.
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let register: Register =
            serde_json::from_slice(&fs::read(root.join("sources/wikidata-v1.json"))?)?;
        let manifest: Manifest =
            serde_json::from_slice(&fs::read(root.join("data/wikidata/v1/manifest.json"))?)?;
        if register.schema_version != 1
            || register.provider != "wikidata"
            || register.provider_license != "CC0-1.0"
            || register.platforms.len() != 16
            || manifest.schema_version != 1
            || manifest.kind != "wikidata-console-text-corpus"
            || manifest.source_revision != REVISION
            || manifest.source_snapshot_sha256 != SNAPSHOT_SHA
            || manifest.platform_collections != 16
            || manifest.item_platform_observations != 15_868
            || manifest.literal_date_claims != 29_333
            || manifest.original_query_rows != 30_341
            || manifest.files.len() != 16
        {
            return Err(invalid("Wikidata register/manifest mismatch"));
        }
        let mut registered = HashSet::new();
        for entry in &register.platforms {
            if entry.platform.is_empty()
                || !entry
                    .platform
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
                || !valid_qid(&entry.wikidata_platform)
                || !registered.insert((entry.platform.clone(), entry.wikidata_platform.clone()))
            {
                return Err(invalid(
                    "invalid or duplicate Wikidata platform registration",
                ));
            }
        }
        let mut declared = HashSet::new();
        let mut declared_items = 0usize;
        let mut declared_rows = 0usize;
        let mut platforms = Vec::new();
        for entry in &manifest.files {
            if !registered.contains(&(entry.platform.clone(), entry.wikidata_platform.clone()))
                || !declared.insert((entry.platform.clone(), entry.wikidata_platform.clone()))
                || entry.text_path != format!("{}.jsonl", entry.platform)
                || !valid_sha256(&entry.text_sha256)
                || !valid_sha256(&entry.source_response_sha256)
                || !valid_sha256(&entry.source_query_sha256)
                || entry.text_bytes == 0
                || entry.distinct_items == 0
                || entry.source_rows < entry.distinct_items
                || entry.received_at_utc.is_empty()
            {
                return Err(invalid("invalid Wikidata source manifest entry"));
            }
            declared_items += entry.distinct_items;
            declared_rows += entry.source_rows;
            if selection != "all" && selection != entry.platform {
                continue;
            }
            let path = root.join("data/wikidata/v1").join(&entry.text_path);
            if fs::symlink_metadata(&path)?.file_type().is_symlink() {
                return Err(invalid("Wikidata source must not be a symbolic link"));
            }
            let bytes = fs::read(&path)?;
            if bytes.len() != entry.text_bytes || sha256(&bytes) != entry.text_sha256 {
                return Err(invalid(format!(
                    "Wikidata source checksum mismatch: {}",
                    entry.platform
                )));
            }
            let items = parse_items(&bytes, &entry.platform)?;
            if items.len() != entry.distinct_items {
                return Err(invalid(format!(
                    "Wikidata source record-count mismatch: {}",
                    entry.platform
                )));
            }
            platforms.push(Platform {
                id: entry.platform.clone(),
                wikidata_platform: entry.wikidata_platform.clone(),
                source_sha256: entry.text_sha256.clone(),
                received_at_utc: entry.received_at_utc.clone(),
                items,
            });
        }
        if declared != registered
            || declared_items != manifest.item_platform_observations
            || declared_rows != manifest.original_query_rows
            || platforms.is_empty()
        {
            return Err(invalid(format!(
                "unsupported or incomplete Wikidata platform: {selection}"
            )));
        }
        if selection == "all" {
            let count: usize = platforms
                .iter()
                .flat_map(|p| &p.items)
                .flat_map(|i| &i.dates)
                .filter(|d| matches!(d.kind.as_str(), "literal" | "typed-literal"))
                .count();
            if count != manifest.literal_date_claims {
                return Err(invalid("Wikidata publication-date count mismatch"));
            }
        }
        Ok(Self { platforms })
    }

    pub fn platform_ids(&self) -> impl Iterator<Item = &str> {
        self.platforms.iter().map(|p| p.id.as_str())
    }
    pub fn item_count(&self) -> usize {
        self.platforms.iter().map(|p| p.items.len()).sum()
    }
    /// Count literal publication-date claims; retain other RDF bindings raw.
    pub fn date_count(&self) -> usize {
        self.platforms
            .iter()
            .flat_map(|p| &p.items)
            .flat_map(|i| &i.dates)
            .filter(|d| matches!(d.kind.as_str(), "literal" | "typed-literal"))
            .count()
    }
    pub fn snapshot_sha256(&self) -> &str {
        SNAPSHOT_SHA
    }
    fn format_item(&self, platform: &Platform, item: &WikidataItem) -> Value {
        json!({
            "platform": platform.id,
            "wikidata_platform": platform.wikidata_platform,
            "qid": item.qid,
            "english_label": item.english_label,
            "dates": item.dates,
            "source": {
                "id": "wikidata",
                "license": "CC0-1.0",
                "revision": REVISION,
                "path": format!("data/wikidata/v1/{}.jsonl", platform.id),
                "sha256": platform.source_sha256,
                "received_at_utc": platform.received_at_utc,
                "snapshot_sha256": SNAPSHOT_SHA,
            },
            "interpretation": "independent-wikidata-observation-not-verified-game-identity"
        })
    }
    pub fn lookup_qid(&self, qid: &str) -> Result<Vec<Value>, CatalogError> {
        if !valid_qid(qid) {
            return Err(invalid(
                "Wikidata QID must be Q followed by a positive decimal integer",
            ));
        }
        Ok(self
            .platforms
            .iter()
            .flat_map(|platform| {
                platform
                    .items
                    .iter()
                    .filter(move |item| item.qid == qid)
                    .map(|item| self.format_item(platform, item))
            })
            .collect())
    }
    /// Search source labels, or list original observations when no query is supplied.
    pub fn search_titles(
        &self,
        query: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<Value>), CatalogError> {
        if !(1..=200).contains(&limit) || query.is_some_and(|q| q.trim().is_empty()) {
            return Err(invalid(
                "Wikidata title query must be nonblank, limit 1..=200",
            ));
        }
        let needle = query.map(str::to_lowercase);
        let mut total = 0;
        let mut matches = Vec::new();
        for platform in &self.platforms {
            for item in &platform.items {
                if needle.as_ref().is_some_and(|q| {
                    !item
                        .english_label
                        .as_ref()
                        .is_some_and(|label| label.to_lowercase().contains(q))
                }) {
                    continue;
                }
                total += 1;
                if matches.len() < limit {
                    matches.push(self.format_item(platform, item));
                }
            }
        }
        Ok((total, matches))
    }
}

#[cfg(test)]
mod tests {
    use super::{parse_items, valid_qid, WikidataTextCatalog};
    use std::path::Path;
    #[test]
    fn rejects_duplicate_and_invalid_source_identifiers() {
        assert!(valid_qid("Q379915"));
        assert!(!valid_qid("Q0"));
        assert!(!valid_qid("Q01"));
        assert!(!valid_qid("QABC"));
        let raw = br#"{"qid":"Q42","english_label":"Answer","dates":[]}
{"qid":"Q42","english_label":"Answer","dates":[]}
"#;
        assert!(parse_items(raw, "fixture").is_err());
        let nonliteral = br#"{"qid":"Q77","english_label":null,"dates":[{"type":"uri","value":"http://www.wikidata.org/.well-known/genid/example"}]}
"#;
        assert_eq!(
            parse_items(nonliteral, "fixture").unwrap()[0].dates[0].kind,
            "uri"
        );
    }
    #[test]
    fn verifies_all_original_wikidata_text_sources_and_qid_lookup() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let all = WikidataTextCatalog::open(&root, "all").unwrap();
        assert_eq!(all.platform_ids().count(), 16);
        assert_eq!(all.item_count(), 15_868);
        assert_eq!(all.date_count(), 29_333);
        let atari = WikidataTextCatalog::open(&root, "atari2600").unwrap();
        let items = atari.lookup_qid("Q379915").unwrap();
        assert_eq!(items.len(), 1);
        assert_eq!(items[0]["english_label"], "Adventure");
        assert_eq!(items[0]["dates"][0]["value"], "1980-01-01T00:00:00Z");
        assert_eq!(items[0]["source"]["license"], "CC0-1.0");
        let (total, matches) = atari.search_titles(Some("ADVENTURE"), 5).unwrap();
        assert!(total > 0);
        assert!(!matches.is_empty());
        assert!(WikidataTextCatalog::open(&root, "unsupported").is_err());
    }
}
