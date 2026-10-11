//! Independent CC0 platform-extension source observations.
//! The original 16-platform accession remains immutable. No work/media join.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const BASE: &str = "data/wikidata/platform-expansion-v1";

#[derive(Deserialize)]
struct Register {
    schema_version: u32,
    source: String,
    license: String,
    query_limit: usize,
    platforms: Vec<Platform>,
}
#[derive(Deserialize)]
struct Platform {
    platform: String,
    wikidata_platform: String,
}
#[derive(Deserialize)]
struct Manifest {
    schema_version: u32,
    source: String,
    license: String,
    source_revision: String,
    platform: String,
    wikidata_platform: String,
    captured_at_utc: String,
    source_query_path: String,
    source_query_sha256: String,
    source_query_bytes: usize,
    source_response_path: String,
    source_response_sha256: String,
    source_response_bytes: usize,
    source_bindings_path: String,
    source_bindings_sha256: String,
    source_bindings_bytes: usize,
    source_rows: usize,
    distinct_item_qids: usize,
    rows_with_english_label: usize,
    rows_with_publication_date: usize,
    #[serde(default)]
    rows_with_nonliteral_publication: usize,
    query_limit: usize,
}

#[derive(Debug, Serialize)]
pub struct ExpandedWikidataObservation {
    pub platform: String,
    pub item_qid: String,
    pub english_label: Option<String>,
    pub publication_binding_kind: Option<String>,
    pub raw_binding: Value,
    pub source_ordinal: usize,
    pub source_path: String,
    pub source_sha256: String,
    pub source_response_sha256: String,
    pub source_query_sha256: String,
    pub captured_at_utc: String,
    pub interpretation: &'static str,
}

pub struct ExpandedWikidataCatalog {
    observations: Vec<ExpandedWikidataObservation>,
    platforms: Vec<String>,
    distinct_item_observations: usize,
    literal_date_claims: usize,
    nonliteral_publication_bindings: usize,
    english_label_rows: usize,
    platform_row_counts: BTreeMap<String, usize>,
}

fn invalid(message: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(message.into())
}
fn sha256(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}
fn qid(value: &str) -> bool {
    value.strip_prefix('Q').is_some_and(|digits| {
        !digits.is_empty()
            && !digits.starts_with('0')
            && digits.bytes().all(|b| b.is_ascii_digit())
    })
}
fn item_uri(value: &str) -> Option<&str> {
    let result = value.strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| value.strip_prefix("https://www.wikidata.org/entity/"))?;
    qid(result).then_some(result)
}
fn original(folder: &Path, name: &str, bytes: usize, hash: &str) -> Result<Vec<u8>, CatalogError> {
    let path = folder.join(name);
    if fs::symlink_metadata(&path)?.file_type().is_symlink() {
        return Err(invalid("Pinned Wikidata source must not be a symbolic link"));
    }
    let body = fs::read(&path)?;
    if body.len() != bytes || sha256(&body) != hash {
        return Err(invalid(format!("Pinned Wikidata source differs: {}", path.display())));
    }
    Ok(body)
}

impl ExpandedWikidataCatalog {
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let register: Register = serde_json::from_slice(
            &fs::read(root.join("sources/wikidata-platform-expansion-v1.json"))?
        )?;
        if register.schema_version != 1 || register.source != "Wikidata"
            || register.license != "CC0-1.0" || register.query_limit != 20_000
            || register.platforms.len() != 3
        {
            return Err(invalid("Unexpected Wikidata platform expansion registration"));
        }
        let mut seen = HashSet::new();
        let mut observations = Vec::new();
        let mut platforms = Vec::new();
        let mut distinct_item_observations = 0;
        let mut literal_date_claims = 0;
        let mut nonliteral_publication_bindings = 0;
        let mut english_label_rows = 0;
        let mut platform_row_counts = BTreeMap::new();
        for scope in register.platforms {
            let approved = matches!(
                (scope.platform.as_str(), scope.wikidata_platform.as_str()),
                ("atari7800", "Q753600")
                    | ("sonyplaystationportable", "Q170325")
                    | ("sonyplaystationvita", "Q188808")
            );
            if !approved || !seen.insert(scope.platform.clone()) {
                return Err(invalid("Unverified or repeated expansion platform mapping"));
            }
            if selection != "all" && selection != scope.platform {
                continue;
            }
            let folder = root.join(BASE).join(&scope.platform);
            if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
                return Err(invalid("Pinned source folder is a symbolic link"));
            }
            let manifest: Manifest = serde_json::from_slice(
                &fs::read(folder.join("manifest.json"))?
            )?;
            if manifest.schema_version != 1 || manifest.source != "Wikidata"
                || manifest.license != "CC0-1.0"
                || manifest.source_revision != "live-query-capture"
                || manifest.platform != scope.platform
                || manifest.wikidata_platform != scope.wikidata_platform
                || manifest.query_limit != register.query_limit
                || manifest.source_rows == 0
                || manifest.source_rows >= manifest.query_limit
                || manifest.distinct_item_qids == 0
                || manifest.source_query_path != "query.rq"
                || manifest.source_response_path != "response.json"
                || manifest.source_bindings_path != "bindings.jsonl"
                || manifest.captured_at_utc.is_empty()
            {
                return Err(invalid(format!("Invalid source manifest for {}", scope.platform)));
            }
            let query = original(
                &folder, "query.rq", manifest.source_query_bytes, &manifest.source_query_sha256
            )?;
            let query_text = std::str::from_utf8(&query)
                .map_err(|_| invalid("Non-UTF-8 Wikidata source query"))?;
            if !query_text.contains(&format!("wd:{}", scope.wikidata_platform))
                || !query_text.contains("wdt:P31 wd:Q7889")
                || !query_text.contains("wdt:P400")
                || !query_text.contains("wdt:P577")
                || !query_text.contains("LIMIT 20000")
            {
                return Err(invalid("Original platform-expansion query scope mismatch"));
            }
            let response = original(
                &folder, "response.json", manifest.source_response_bytes,
                &manifest.source_response_sha256,
            )?;
            let response_json: Value = serde_json::from_slice(&response)?;
            if response_json["head"]["vars"] != json!(["item", "itemLabel", "publication"]) {
                return Err(invalid("Unexpected original Wikidata response columns"));
            }
            let bindings = response_json["results"]["bindings"].as_array()
                .ok_or_else(|| invalid("Missing original Wikidata bindings"))?;
            if bindings.len() != manifest.source_rows {
                return Err(invalid("Original response and manifest row counts disagree"));
            }
            let raw_text = original(
                &folder, "bindings.jsonl", manifest.source_bindings_bytes,
                &manifest.source_bindings_sha256,
            )?;
            let text = std::str::from_utf8(&raw_text)
                .map_err(|_| invalid("Non-UTF-8 original JSONL bindings"))?;
            let lines: Vec<&str> = text.lines().collect();
            if !text.ends_with('\n') || lines.len() != manifest.source_rows {
                return Err(invalid("Original JSONL rows do not match manifest"));
            }
            let mut unique_items = HashSet::new();
            let mut labels = 0;
            let mut dates = 0;
            let mut nonliteral = 0;
            for (index, line) in lines.iter().enumerate() {
                let record: Value = serde_json::from_str(line)?;
                if record != bindings[index] || record["item"]["type"] != "uri" {
                    return Err(invalid("Original Wikidata response differs from JSONL evidence"));
                }
                let item = record["item"]["value"].as_str().and_then(item_uri)
                    .ok_or_else(|| invalid("Original item is not a valid Wikidata QID"))?;
                unique_items.insert(item.to_owned());
                let english_label = match record.get("itemLabel") {
                    None => None,
                    Some(value) => {
                        if value["type"] != "literal" || value["xml:lang"] != "en" {
                            return Err(invalid("Unexpected English source label RDF type"));
                        }
                        labels += 1;
                        Some(value["value"].as_str()
                            .ok_or_else(|| invalid("Original English label is not text"))?
                            .to_owned())
                    }
                };
                let publication_binding_kind = match record.get("publication") {
                    None => None,
                    Some(value) => {
                        let kind = value["type"].as_str()
                            .ok_or_else(|| invalid("Missing publication RDF type"))?;
                        if !matches!(kind, "literal" | "typed-literal" | "uri" | "bnode")
                            || value["value"].as_str().is_none_or(str::is_empty)
                        {
                            return Err(invalid("Invalid raw publication RDF binding"));
                        }
                        if matches!(kind, "literal" | "typed-literal") {
                            dates += 1;
                        } else {
                            nonliteral += 1;
                        }
                        Some(kind.to_owned())
                    }
                };
                observations.push(ExpandedWikidataObservation {
                    platform: scope.platform.clone(),
                    item_qid: item.to_owned(),
                    english_label,
                    publication_binding_kind,
                    raw_binding: record,
                    source_ordinal: index + 1,
                    source_path: format!("{BASE}/{}/bindings.jsonl", scope.platform),
                    source_sha256: manifest.source_bindings_sha256.clone(),
                    source_response_sha256: manifest.source_response_sha256.clone(),
                    source_query_sha256: manifest.source_query_sha256.clone(),
                    captured_at_utc: manifest.captured_at_utc.clone(),
                    interpretation: "attributed-source-evidence-not-canonical-work-media-or-release-identity",
                });
            }
            if unique_items.len() != manifest.distinct_item_qids
                || labels != manifest.rows_with_english_label
                || dates != manifest.rows_with_publication_date
                || nonliteral != manifest.rows_with_nonliteral_publication
            {
                return Err(invalid("Source item, label or RDF date count differs from pinned manifest"));
            }
            distinct_item_observations += unique_items.len();
            literal_date_claims += dates;
            english_label_rows += labels;
            nonliteral_publication_bindings += nonliteral;
            platform_row_counts.insert(scope.platform.clone(), manifest.source_rows);
            platforms.push(scope.platform);
        }
        if platforms.is_empty() || (selection == "all" && platforms.len() != 3) {
            return Err(invalid(format!("Unknown or incomplete source platform: {selection}")));
        }
        Ok(Self {
            observations, platforms, distinct_item_observations, literal_date_claims,
            nonliteral_publication_bindings, english_label_rows, platform_row_counts,
        })
    }
    pub fn platforms(&self) -> &[String] { &self.platforms }
    pub fn total_rows(&self) -> usize { self.observations.len() }
    pub fn distinct_item_observations(&self) -> usize { self.distinct_item_observations }
    pub fn literal_date_claims(&self) -> usize { self.literal_date_claims }
    pub fn nonliteral_publication_bindings(&self) -> usize {
        self.nonliteral_publication_bindings
    }
    pub fn english_label_rows(&self) -> usize { self.english_label_rows }
    pub fn platform_row_counts(&self) -> &BTreeMap<String, usize> { &self.platform_row_counts }

    pub fn search(
        &self, qid_filter: Option<&str>, title: Option<&str>, limit: usize
    ) -> Result<(usize, Vec<&ExpandedWikidataObservation>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid_filter.is_some_and(|value| !qid(value))
            || title.is_some_and(|value| value.trim().is_empty())
        {
            return Err(invalid("Require valid source QID, nonblank title and limit 1..=200"));
        }
        let needle = title.map(str::to_lowercase);
        let mut total = 0;
        let mut rows = Vec::new();
        for entry in &self.observations {
            if qid_filter.is_some_and(|value| entry.item_qid != value)
                || needle.as_ref().is_some_and(|value| {
                    !entry.english_label.as_ref().is_some_and(|label| {
                        label.to_lowercase().contains(value)
                    })
                })
            {
                continue;
            }
            total += 1;
            if rows.len() < limit { rows.push(entry); }
        }
        Ok((total, rows))
    }
}

#[cfg(test)]
mod tests {
    use super::ExpandedWikidataCatalog;
    use std::path::Path;
    #[test]
    fn all_three_new_source_platforms_verify_offline() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 3);
        assert_eq!(catalog.total_rows(), 3_888);
        assert_eq!(catalog.distinct_item_observations(), 2_254);
        assert_eq!(catalog.nonliteral_publication_bindings(), 5);
        assert_eq!(catalog.literal_date_claims(), 3_699);
        assert_eq!(catalog.platform_row_counts()["atari7800"], 101);
        assert_eq!(catalog.platform_row_counts()["sonyplaystationportable"], 2_088);
        assert_eq!(catalog.platform_row_counts()["sonyplaystationvita"], 1_699);
        let vita = ExpandedWikidataCatalog::open(&root, "sonyplaystationvita").unwrap();
        assert_eq!(vita.nonliteral_publication_bindings(), 5);
        let (count, rows) = catalog.search(None, None, 1).unwrap();
        assert_eq!(count, 3_888);
        assert_eq!(rows.len(), 1);
        assert!(ExpandedWikidataCatalog::open(&root, "unknown").is_err());
    }
}
