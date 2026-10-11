//! Read committed Wikidata developer, publisher and genre source statements.
//! The 16 independent SPARQL source responses are hash-verified before use.
//! A QID-to-QID property claim is evidence, not a canonical game/company identity.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const BASE: &str = "data/wikidata/properties-v1";
const PROPERTY_IDS: [&str; 3] = ["P178", "P123", "P136"];

#[derive(Debug, Deserialize)]
struct Register {
    schema_version: u32,
    provider: String,
    provider_license: String,
    platforms: Vec<RegisteredPlatform>,
}
#[derive(Debug, Deserialize)]
struct RegisteredPlatform {
    platform: String,
    wikidata_platform: String,
}
#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    source: String,
    license: String,
    platform: String,
    wikidata_platform: String,
    source_revision: String,
    source_query_path: String,
    source_query_sha256: String,
    source_response_path: String,
    source_response_sha256: String,
    source_response_bytes: usize,
    source_bindings_path: String,
    source_bindings_sha256: String,
    source_bindings_bytes: usize,
    captured_at_utc: String,
    properties: Vec<String>,
    query_limit: usize,
    source_rows: usize,
    distinct_items: usize,
    #[serde(default)]
    non_entity_value_bindings: usize,
}

#[derive(Debug, Serialize)]
pub struct PropertyClaim {
    pub platform: String,
    pub item_qid: String,
    pub property: String,
    pub value_qid: Option<String>,
    pub raw_binding: Value,
    pub source_ordinal: usize,
    pub source_path: String,
    pub source_sha256: String,
    pub source_query_sha256: String,
    pub source_response_sha256: String,
    pub captured_at_utc: String,
    pub interpretation: &'static str,
}

pub struct WikidataPropertyCatalog {
    claims: Vec<PropertyClaim>,
    platforms: Vec<String>,
    source_item_observations: usize,
    non_entity_bindings: usize,
    properties: BTreeMap<String, usize>,
}

fn invalid(text: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(text.into())
}
fn digest(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}
fn qid_uri(uri: &str) -> Option<&str> {
    let raw = uri
        .strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/entity/"))?;
    if raw.strip_prefix('Q').is_some_and(|digits| {
        !digits.is_empty() && !digits.starts_with('0') && digits.bytes().all(|b| b.is_ascii_digit())
    }) {
        Some(raw)
    } else {
        None
    }
}
fn property_uri(uri: &str) -> Option<&str> {
    let value = uri
        .strip_prefix("http://www.wikidata.org/prop/direct/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/prop/direct/"))?;
    PROPERTY_IDS.contains(&value).then_some(value)
}
fn read_pinned(
    directory: &Path,
    name: &str,
    expected_bytes: Option<usize>,
    expected_sha: &str,
) -> Result<Vec<u8>, CatalogError> {
    if fs::symlink_metadata(directory.join(name))?
        .file_type()
        .is_symlink()
    {
        return Err(invalid(format!(
            "Wikidata source file is a symlink: {name}"
        )));
    }
    let bytes = fs::read(directory.join(name))?;
    if expected_bytes.is_some_and(|size| size != bytes.len()) || digest(&bytes) != expected_sha {
        return Err(invalid(format!(
            "Wikidata source checksum mismatch: {name}"
        )));
    }
    Ok(bytes)
}
fn validate_record(value: &Value) -> Result<(&str, &str, Option<&str>), CatalogError> {
    let item = value["item"]["value"]
        .as_str()
        .and_then(qid_uri)
        .ok_or_else(|| invalid("invalid Wikidata game item QID"))?;
    if value["item"]["type"] != "uri" || value["property"]["type"] != "uri" {
        return Err(invalid("invalid Wikidata source item/property RDF type"));
    }
    let property = value["property"]["value"]
        .as_str()
        .and_then(property_uri)
        .ok_or_else(|| invalid("unexpected Wikidata property ID"))?;
    let kind = value["value"]["type"]
        .as_str()
        .ok_or_else(|| invalid("missing original Wikidata value type"))?;
    if !matches!(kind, "uri" | "literal" | "typed-literal" | "bnode")
        || value["value"]["value"].as_str().is_none_or(str::is_empty)
    {
        return Err(invalid("malformed Wikidata source value binding"));
    }
    let qid = if kind == "uri" {
        value["value"]["value"].as_str().and_then(qid_uri)
    } else {
        None
    };
    Ok((item, property, qid))
}

impl WikidataPropertyCatalog {
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let register: Register =
            serde_json::from_slice(&fs::read(root.join("sources/wikidata-v1.json"))?)?;
        if register.schema_version != 1
            || register.provider != "wikidata"
            || register.provider_license != "CC0-1.0"
            || register.platforms.len() != 16
        {
            return Err(invalid("independent Wikidata source register mismatch"));
        }
        let mut seen_platforms = HashSet::new();
        let mut claims = Vec::new();
        let mut platforms = Vec::new();
        let mut item_observations = 0;
        let mut non_entity_bindings = 0;
        let mut properties = BTreeMap::new();
        for platform in &register.platforms {
            if !seen_platforms.insert(&platform.platform)
                || platform.platform.is_empty()
                || !platform
                    .platform
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
                || qid_uri(&format!(
                    "http://www.wikidata.org/entity/{}",
                    platform.wikidata_platform
                ))
                .is_none()
            {
                return Err(invalid("invalid registered Wikidata platform"));
            }
            if selection != "all" && selection != platform.platform {
                continue;
            }
            let folder = root.join(BASE).join(&platform.platform);
            if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
                return Err(invalid("Wikidata source folder must not be a symlink"));
            }
            let manifest: Manifest =
                serde_json::from_slice(&fs::read(folder.join("manifest.json"))?)?;
            if manifest.schema_version != 1
                || manifest.source != "Wikidata"
                || manifest.license != "CC0-1.0"
                || manifest.platform != platform.platform
                || manifest.wikidata_platform != platform.wikidata_platform
                || manifest.source_revision != "live-query-capture"
                || manifest.source_query_path != "query.rq"
                || manifest.source_response_path != "response.json"
                || manifest.source_bindings_path != "bindings.jsonl"
                || manifest.properties != PROPERTY_IDS
                || manifest.query_limit != 10_000
                || manifest.source_rows == 0
                || manifest.source_rows >= manifest.query_limit
                || manifest.distinct_items == 0
                || manifest.captured_at_utc.is_empty()
            {
                return Err(invalid(format!(
                    "invalid Wikidata property manifest: {}",
                    platform.platform
                )));
            }
            let query = read_pinned(&folder, "query.rq", None, &manifest.source_query_sha256)?;
            let query_text = std::str::from_utf8(&query)
                .map_err(|_| invalid("non-UTF-8 Wikidata source query"))?;
            if !query_text.contains(&format!("wd:{}", platform.wikidata_platform))
                || !query_text.contains("wdt:P178")
                || !query_text.contains("wdt:P123")
                || !query_text.contains("wdt:P136")
                || !query_text.contains("LIMIT 10000")
            {
                return Err(invalid("Wikidata source query scope mismatch"));
            }
            let response = read_pinned(
                &folder,
                "response.json",
                Some(manifest.source_response_bytes),
                &manifest.source_response_sha256,
            )?;
            let original: Value = serde_json::from_slice(&response)?;
            if original["head"]["vars"] != json!(["item", "property", "value"]) {
                return Err(invalid("unexpected Wikidata source response columns"));
            }
            let bindings = original["results"]["bindings"]
                .as_array()
                .ok_or_else(|| invalid("missing original Wikidata source response bindings"))?;
            if bindings.len() != manifest.source_rows {
                return Err(invalid("Wikidata original response row count mismatch"));
            }
            let text = read_pinned(
                &folder,
                "bindings.jsonl",
                Some(manifest.source_bindings_bytes),
                &manifest.source_bindings_sha256,
            )?;
            let raw = std::str::from_utf8(&text)
                .map_err(|_| invalid("non-UTF-8 Wikidata property JSONL"))?;
            let mut unique_items = HashSet::new();
            let mut non_entity = 0;
            let lines: Vec<_> = raw.lines().collect();
            if lines.len() != bindings.len() {
                return Err(invalid("source response and JSONL row counts differ"));
            }
            for (index, line) in lines.iter().enumerate() {
                let record: Value = serde_json::from_str(line)?;
                if record != bindings[index] {
                    return Err(invalid(
                        "Wikidata source response and JSONL evidence differ",
                    ));
                }
                let (item, property, entity) = validate_record(&record)?;
                unique_items.insert(item.to_owned());
                if entity.is_none() {
                    non_entity += 1;
                }
                *properties.entry(property.to_owned()).or_insert(0) += 1;
                claims.push(PropertyClaim {
                    platform: platform.platform.clone(),
                    item_qid: item.to_owned(),
                    property: property.to_owned(),
                    value_qid: entity.map(str::to_owned),
                    raw_binding: record,
                    source_ordinal: index + 1,
                    source_path: format!("{BASE}/{}/bindings.jsonl", platform.platform),
                    source_sha256: manifest.source_bindings_sha256.clone(),
                    source_query_sha256: manifest.source_query_sha256.clone(),
                    source_response_sha256: manifest.source_response_sha256.clone(),
                    captured_at_utc: manifest.captured_at_utc.clone(),
                    interpretation:
                        "original-attributed-wikidata-property-not-verified-game-identity",
                });
            }
            if unique_items.len() != manifest.distinct_items
                || non_entity != manifest.non_entity_value_bindings
            {
                return Err(invalid(format!(
                    "Wikidata property source item/value counts differ: {}",
                    platform.platform
                )));
            }
            item_observations += manifest.distinct_items;
            non_entity_bindings += non_entity;
            platforms.push(platform.platform.clone());
        }
        if platforms.is_empty() || (selection == "all" && platforms.len() != 16) {
            return Err(invalid(format!(
                "unknown or incomplete Wikidata source platform: {selection}"
            )));
        }
        Ok(Self {
            claims,
            platforms,
            source_item_observations: item_observations,
            non_entity_bindings,
            properties,
        })
    }

    pub fn platforms(&self) -> &[String] {
        &self.platforms
    }
    pub fn referenced_entity_qids(&self) -> std::collections::BTreeSet<String> {
        self.claims.iter().filter_map(|claim| claim.value_qid.clone()).collect()
    }

    pub fn total_claims(&self) -> usize {
        self.claims.len()
    }
    pub fn source_item_observations(&self) -> usize {
        self.source_item_observations
    }
    pub fn non_entity_bindings(&self) -> usize {
        self.non_entity_bindings
    }
    pub fn property_counts(&self) -> &BTreeMap<String, usize> {
        &self.properties
    }
    pub fn search(
        &self,
        qid: Option<&str>,
        property: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&PropertyClaim>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid
                .is_some_and(|x| qid_uri(&format!("http://www.wikidata.org/entity/{x}")).is_none())
            || property.is_some_and(|x| !PROPERTY_IDS.contains(&x))
        {
            return Err(invalid(
                "property query requires valid QID, P178/P123/P136, limit 1..=200",
            ));
        }
        let mut total = 0;
        let mut matched = Vec::new();
        for claim in &self.claims {
            if qid.is_some_and(|x| claim.item_qid != x)
                || property.is_some_and(|x| claim.property != x)
            {
                continue;
            }
            total += 1;
            if matched.len() < limit {
                matched.push(claim);
            }
        }
        Ok((total, matched))
    }
}

#[cfg(test)]
mod tests {
    use super::{property_uri, qid_uri, WikidataPropertyCatalog};
    use std::path::Path;
    #[test]
    fn rejects_non_qid_links_without_discarding_raw_evidence() {
        assert_eq!(qid_uri("http://www.wikidata.org/entity/Q123"), Some("Q123"));
        assert!(qid_uri("http://www.wikidata.org/.well-known/genid/value").is_none());
        assert!(qid_uri("http://www.wikidata.org/entity/Q0").is_none());
        assert_eq!(
            property_uri("http://www.wikidata.org/prop/direct/P178"),
            Some("P178")
        );
        assert!(property_uri("http://www.wikidata.org/prop/direct/P577").is_none());
    }
    #[test]
    fn verifies_all_sixteen_source_partitions_and_raw_bindings() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = WikidataPropertyCatalog::open(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 16);
        assert_eq!(catalog.total_claims(), 47_144);
        assert_eq!(catalog.source_item_observations(), 14_759);
        assert_eq!(catalog.non_entity_bindings(), 3);
        assert_eq!(catalog.property_counts().values().sum::<usize>(), 47_144);
        let (count, matches) = catalog.search(Some("Q379915"), None, 20).unwrap();
        assert!(count > 0);
        assert!(matches.iter().any(|item| item.platform == "atari2600"));
        let (unfiltered, limited) = catalog.search(None, Some("P178"), 1).unwrap();
        assert!(unfiltered > 0);
        assert_eq!(limited.len(), 1);
        assert!(WikidataPropertyCatalog::open(&root, "unknown").is_err());
    }
}
