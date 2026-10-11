//! Original game-series, mode, language, distribution, title and external-ID
//! source bindings. Every query response is SHA-256 checked against its JSONL.
//! None of these claims establish canonical game or release identities.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const BASE: &str = "data/wikidata/relations-v1";
const IDS: [&str; 9] = [
    "P179", "P404", "P407", "P495", "P437", "P750", "P1476", "P1733", "P2725",
];

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
    distinct_items: usize,
    entity_value_bindings: usize,
    query_limit: usize,
    properties: Vec<String>,
    property_counts: BTreeMap<String, usize>,
    rdf_value_type_counts: BTreeMap<String, usize>,
}

#[derive(Debug, Serialize)]
pub struct RelationClaim {
    pub platform: String,
    pub item_qid: String,
    pub property: String,
    pub value_entity_qid: Option<String>,
    pub raw_binding: Value,
    pub source_ordinal: usize,
    pub source_path: String,
    pub source_sha256: String,
    pub source_response_sha256: String,
    pub source_query_sha256: String,
    pub captured_at_utc: String,
    pub interpretation: &'static str,
}

pub struct WikidataRelationCatalog {
    claims: Vec<RelationClaim>,
    platforms: Vec<String>,
    item_observations: usize,
    entity_values: usize,
    counts: BTreeMap<String, usize>,
}

fn invalid(message: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(message.into())
}
fn sha256(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}
fn qid_uri(uri: &str) -> Option<&str> {
    let value = uri
        .strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/entity/"))?;
    value
        .strip_prefix('Q')
        .is_some_and(|digits| {
            !digits.is_empty()
                && !digits.starts_with('0')
                && digits.bytes().all(|b| b.is_ascii_digit())
        })
        .then_some(value)
}
fn property_uri(uri: &str) -> Option<&str> {
    let value = uri
        .strip_prefix("http://www.wikidata.org/prop/direct/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/prop/direct/"))?;
    IDS.contains(&value).then_some(value)
}
fn pinned(
    directory: &Path,
    filename: &str,
    expected_bytes: usize,
    expected_hash: &str,
) -> Result<Vec<u8>, CatalogError> {
    let path = directory.join(filename);
    if fs::symlink_metadata(&path)?.file_type().is_symlink() {
        return Err(invalid("Wikidata source file is a symbolic link"));
    }
    let bytes = fs::read(&path)?;
    if bytes.len() != expected_bytes || sha256(&bytes) != expected_hash {
        return Err(invalid(format!(
            "Wikidata original relation source checksum mismatch: {}",
            path.display()
        )));
    }
    Ok(bytes)
}
fn validated(value: &Value) -> Result<(&str, &str, Option<&str>, &str), CatalogError> {
    if value["item"]["type"] != "uri" || value["property"]["type"] != "uri" {
        return Err(invalid("Wikidata subject/property must be RDF URIs"));
    }
    let item = value["item"]["value"]
        .as_str()
        .and_then(qid_uri)
        .ok_or_else(|| invalid("invalid source game QID"))?;
    let property = value["property"]["value"]
        .as_str()
        .and_then(property_uri)
        .ok_or_else(|| invalid("unexpected relation/identifier property"))?;
    let kind = value["value"]["type"]
        .as_str()
        .ok_or_else(|| invalid("missing RDF value kind"))?;
    if !matches!(kind, "uri" | "literal" | "typed-literal" | "bnode")
        || value["value"]["value"].as_str().is_none_or(str::is_empty)
    {
        return Err(invalid("invalid raw RDF property value"));
    }
    let entity = if kind == "uri" {
        value["value"]["value"].as_str().and_then(qid_uri)
    } else {
        None
    };
    Ok((item, property, entity, kind))
}

impl WikidataRelationCatalog {
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let register: Register =
            serde_json::from_slice(&fs::read(root.join("sources/wikidata-v1.json"))?)?;
        if register.schema_version != 1
            || register.provider != "wikidata"
            || register.provider_license != "CC0-1.0"
            || register.platforms.len() != 16
        {
            return Err(invalid("Wikidata platform source register mismatch"));
        }
        let mut declared_platforms = HashSet::new();
        let mut claims = Vec::new();
        let mut platforms = Vec::new();
        let mut total_items = 0;
        let mut entity_values = 0;
        let mut counts: BTreeMap<String, usize> = BTreeMap::new();
        for scope in &register.platforms {
            if !declared_platforms.insert(&scope.platform)
                || scope.platform.is_empty()
                || !scope
                    .platform
                    .bytes()
                    .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
                || qid_uri(&format!(
                    "http://www.wikidata.org/entity/{}",
                    scope.wikidata_platform
                ))
                .is_none()
            {
                return Err(invalid(
                    "duplicate or invalid Wikidata platform registration",
                ));
            }
            if selection != "all" && selection != scope.platform {
                continue;
            }
            let folder = root.join(BASE).join(&scope.platform);
            if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
                return Err(invalid(
                    "Wikidata original source folder must not be a symlink",
                ));
            }
            let manifest: Manifest =
                serde_json::from_slice(&fs::read(folder.join("manifest.json"))?)?;
            if manifest.schema_version != 1
                || manifest.source != "Wikidata"
                || manifest.license != "CC0-1.0"
                || manifest.source_revision != "live-query-capture"
                || manifest.platform != scope.platform
                || manifest.wikidata_platform != scope.wikidata_platform
                || manifest.captured_at_utc.is_empty()
                || manifest.source_query_path != "query.rq"
                || manifest.source_response_path != "response.json"
                || manifest.source_bindings_path != "bindings.jsonl"
                || manifest.properties != IDS
                || !matches!(manifest.query_limit, 10_000 | 30_000)
                || manifest.source_rows == 0
                || manifest.source_rows >= manifest.query_limit
                || manifest.distinct_items == 0
            {
                return Err(invalid(format!(
                    "invalid Wikidata relation source manifest: {}",
                    scope.platform
                )));
            }
            let query = pinned(
                &folder,
                "query.rq",
                manifest.source_query_bytes,
                &manifest.source_query_sha256,
            )?;
            let query_text = std::str::from_utf8(&query)
                .map_err(|_| invalid("non-UTF-8 original source query"))?;
            if !query_text.contains(&format!("wd:{}", scope.wikidata_platform))
                || !query_text.contains(&format!("LIMIT {}", manifest.query_limit))
                || !query_text.contains("SELECT DISTINCT ?item ?property ?value")
                || IDS
                    .iter()
                    .any(|property| !query_text.contains(&format!("wdt:{property}")))
            {
                return Err(invalid("source query property/platform scope changed"));
            }
            let response = pinned(
                &folder,
                "response.json",
                manifest.source_response_bytes,
                &manifest.source_response_sha256,
            )?;
            let source: Value = serde_json::from_slice(&response)?;
            if source["head"]["vars"] != json!(["item", "property", "value"]) {
                return Err(invalid("unexpected Wikidata response variable names"));
            }
            let bindings = source["results"]["bindings"]
                .as_array()
                .ok_or_else(|| invalid("missing original Wikidata response bindings"))?;
            if bindings.len() != manifest.source_rows {
                return Err(invalid("source response/manifest row count mismatch"));
            }
            let text = pinned(
                &folder,
                "bindings.jsonl",
                manifest.source_bindings_bytes,
                &manifest.source_bindings_sha256,
            )?;
            let raw = std::str::from_utf8(&text)
                .map_err(|_| invalid("non-UTF-8 original Wikidata relation JSONL"))?;
            let lines: Vec<_> = raw.lines().collect();
            if !raw.ends_with('\n') || lines.len() != manifest.source_rows {
                return Err(invalid("source text and manifest row counts differ"));
            }
            let mut item_ids = HashSet::new();
            let mut scope_properties = BTreeMap::new();
            let mut kinds = BTreeMap::new();
            let mut scope_entity_values = 0;
            for (index, line) in lines.iter().enumerate() {
                let value: Value = serde_json::from_str(line)?;
                if value != bindings[index] {
                    return Err(invalid("pinned response/JSONL bindings differ"));
                }
                let (item, property, entity, kind) = validated(&value)?;
                item_ids.insert(item.to_owned());
                *scope_properties
                    .entry(property.to_owned())
                    .or_insert(0usize) += 1;
                *kinds.entry(kind.to_owned()).or_insert(0usize) += 1;
                if entity.is_some() {
                    scope_entity_values += 1;
                }
                claims.push(RelationClaim {
                    platform: scope.platform.clone(),
                    item_qid: item.to_owned(),
                    property: property.to_owned(),
                    value_entity_qid: entity.map(str::to_owned),
                    raw_binding: value,
                    source_ordinal: index + 1,
                    source_path: format!("{BASE}/{}/bindings.jsonl", scope.platform),
                    source_sha256: manifest.source_bindings_sha256.clone(),
                    source_response_sha256: manifest.source_response_sha256.clone(),
                    source_query_sha256: manifest.source_query_sha256.clone(),
                    captured_at_utc: manifest.captured_at_utc.clone(),
                    interpretation:
                        "independent-wikidata-source-claim-not-verified-game-or-release-identity",
                });
            }
            if item_ids.len() != manifest.distinct_items
                || scope_entity_values != manifest.entity_value_bindings
                || scope_properties != manifest.property_counts
                || kinds != manifest.rdf_value_type_counts
            {
                return Err(invalid(
                    "source relation property, RDF type or item counts differ",
                ));
            }
            for (key, value) in scope_properties {
                *counts.entry(key).or_insert(0) += value;
            }
            total_items += manifest.distinct_items;
            entity_values += scope_entity_values;
            platforms.push(scope.platform.clone());
        }
        if platforms.is_empty() || (selection == "all" && platforms.len() != 16) {
            return Err(invalid(format!(
                "unsupported or incomplete relation platform: {selection}"
            )));
        }
        Ok(Self {
            claims,
            platforms,
            item_observations: total_items,
            entity_values,
            counts,
        })
    }

    pub fn platforms(&self) -> &[String] {
        &self.platforms
    }
    pub fn total_claims(&self) -> usize {
        self.claims.len()
    }
    pub fn item_observations(&self) -> usize {
        self.item_observations
    }
    pub fn entity_values(&self) -> usize {
        self.entity_values
    }
    pub fn property_counts(&self) -> &BTreeMap<String, usize> {
        &self.counts
    }
    pub fn search(
        &self,
        qid: Option<&str>,
        property: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&RelationClaim>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid
                .is_some_and(|x| qid_uri(&format!("http://www.wikidata.org/entity/{x}")).is_none())
            || property.is_some_and(|x| !IDS.contains(&x))
        {
            return Err(invalid("source relation search requires valid QID, property P179/P404/P407/P495/P437/P750/P1476/P1733/P2725 and limit 1..=200"));
        }
        let mut total = 0;
        let mut matches = Vec::new();
        for record in &self.claims {
            if qid.is_some_and(|name| record.item_qid != name)
                || property.is_some_and(|name| record.property != name)
            {
                continue;
            }
            total += 1;
            if matches.len() < limit {
                matches.push(record);
            }
        }
        Ok((total, matches))
    }
}

#[cfg(test)]
mod tests {
    use super::{property_uri, qid_uri, WikidataRelationCatalog};
    use std::path::Path;

    #[test]
    fn distinguish_original_entity_values_from_identifiers_and_language_literals() {
        assert_eq!(
            qid_uri("http://www.wikidata.org/entity/Q2156030"),
            Some("Q2156030")
        );
        assert_eq!(qid_uri("http://www.wikidata.org/entity/Q0"), None);
        assert_eq!(
            property_uri("http://www.wikidata.org/prop/direct/P1733"),
            Some("P1733")
        );
        assert_eq!(
            property_uri("http://www.wikidata.org/prop/direct/P136"),
            None
        );
    }

    #[test]
    fn verify_all_committed_relation_responses_and_external_identifiers() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = WikidataRelationCatalog::open(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 16);
        assert_eq!(catalog.total_claims(), 92_621);
        assert_eq!(catalog.item_observations(), 14_772);
        assert_eq!(catalog.entity_values(), 83_806);
        assert_eq!(catalog.property_counts()["P1733"], 2_624);
        assert_eq!(catalog.property_counts()["P2725"], 658);
        let (total, matches) = catalog.search(None, Some("P1476"), 3).unwrap();
        assert_eq!(total, 5_532);
        assert_eq!(matches.len(), 3);
        assert!(matches.iter().all(|row| row.source_sha256.len() == 64));
        assert!(WikidataRelationCatalog::open(&root, "invalid").is_err());
        let atari = WikidataRelationCatalog::open(&root, "atari2600").unwrap();
        let (found, entries) = atari.search(Some("Q100701966"), None, 10).unwrap();
        assert!(found > 0);
        assert!(entries.iter().any(|record| record.property == "P404"));
    }
}
