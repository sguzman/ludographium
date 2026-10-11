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

#[derive(Debug, Deserialize)]
struct ExpandedRegister {
    schema_version: u32,
    source: String,
    license: String,
    query_limit: usize,
    platforms: Vec<RegisteredPlatform>,
}

#[derive(Debug, Deserialize)]
struct ExpandedManifest {
    schema_version: u32,
    source: String,
    license: String,
    source_revision: String,
    source_register: String,
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

    /// Source-grounded nine-property snapshots for console expansions v1-v4.
    pub fn open_expanded(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_expanded_cohorts(
            root.as_ref(),
            selection,
            &[(1, 3), (2, 4), (3, 6), (4, 6)],
            "data/wikidata/expanded-relations-v1",
            19,
        )
    }

    /// Additional source-grounded relation claims for console expansions v5-v7.
    pub fn open_expanded_v2(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_expanded_cohorts(
            root.as_ref(),
            selection,
            &[(5, 6), (6, 6), (7, 6)],
            "data/wikidata/expanded-relations-v2",
            18,
        )
    }

    /// Independently captured v8 relations and identifier statements.
    pub fn open_expanded_v3(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_expanded_cohorts(
            root.as_ref(),
            selection,
            &[(8, 12)],
            "data/wikidata/expanded-relations-v3",
            12,
        )
    }

    /// Query all 65 independent P400 platform partitions without merging game identities.
    /// A single platform reads only the registered source cohort for that platform.
    pub fn open_combined(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let mut selected = None;
        if selection != "all" {
            for version in 0..=8 {
                let register = if version == 0 {
                    "sources/wikidata-v1.json".to_owned()
                } else {
                    format!("sources/wikidata-platform-expansion-v{version}.json")
                };
                let raw: Value = serde_json::from_slice(&fs::read(root.join(register))?)?;
                let scopes = raw["platforms"]
                    .as_array()
                    .ok_or_else(|| invalid("combined source register is missing platforms"))?;
                if scopes.iter().any(|scope| scope["platform"] == selection) {
                    let cohort = match version {
                        0 => 0,
                        1..=4 => 1,
                        5..=7 => 2,
                        8 => 3,
                        _ => unreachable!(),
                    };
                    if selected.replace(cohort).is_some() {
                        return Err(invalid("duplicate platform across independent source cohorts"));
                    }
                }
            }
            if selected.is_none() {
                return Err(invalid("unknown combined source platform"));
            }
        }
        let mut parts = Vec::new();
        for cohort in 0..4 {
            if selected.is_some_and(|value| value != cohort) {
                continue;
            }
            let source = match cohort {
                0 => Self::open(root, selection)?,
                1 => Self::open_expanded(root, selection)?,
                2 => Self::open_expanded_v2(root, selection)?,
                3 => Self::open_expanded_v3(root, selection)?,
                _ => unreachable!(),
            };
            parts.push(source);
        }
        let mut seen = HashSet::new();
        let mut combined = Self {
            claims: Vec::new(),
            platforms: Vec::new(),
            item_observations: 0,
            entity_values: 0,
            counts: BTreeMap::new(),
        };
        for mut source in parts {
            for platform in &source.platforms {
                if !seen.insert(platform.clone()) {
                    return Err(invalid("combined source cohorts repeated platform"));
                }
            }
            combined.claims.append(&mut source.claims);
            combined.platforms.append(&mut source.platforms);
            combined.item_observations += source.item_observations;
            combined.entity_values += source.entity_values;
            for (kind, count) in source.counts { *combined.counts.entry(kind).or_insert(0) += count; }
        }
        if combined.platforms.is_empty()
            || (selection == "all" && combined.platforms.len() != 65)
        {
            return Err(invalid("incomplete 65-scope combined source collection"));
        }
        Ok(combined)
    }

    fn open_expanded_cohorts(
        root: &Path,
        selection: &str,
        cohorts: &[(usize, usize)],
        source_base: &str,
        expected_total: usize,
    ) -> Result<Self, CatalogError> {
        let mut seen_platforms = HashSet::new();
        let mut seen_qids = HashSet::new();
        let mut claims = Vec::new();
        let mut platforms = Vec::new();
        let mut item_observations = 0;
        let mut entity_values = 0;
        let mut counts = BTreeMap::new();

        for &(version, expected_platforms) in cohorts {
            let register_path = format!("sources/wikidata-platform-expansion-v{version}.json");
            let register: ExpandedRegister =
                serde_json::from_slice(&fs::read(root.join(&register_path))?)?;
            if register.schema_version != 1
                || register.source != "Wikidata"
                || register.license != "CC0-1.0"
                || register.query_limit != 20_000
                || register.platforms.len() != expected_platforms
            {
                return Err(invalid("invalid expanded relation platform register"));
            }
            for scope in &register.platforms {
                if scope.platform.is_empty()
                    || !scope
                        .platform
                        .bytes()
                        .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
                    || qid_uri(&format!(
                        "http://www.wikidata.org/entity/{}",
                        scope.wikidata_platform
                    ))
                    .is_none()
                    || !seen_platforms.insert(scope.platform.clone())
                    || !seen_qids.insert(scope.wikidata_platform.clone())
                {
                    return Err(invalid("duplicate or malformed expanded relation scope"));
                }
                if selection != "all" && selection != scope.platform {
                    continue;
                }
                let folder = root.join(source_base).join(&scope.platform);
                if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
                    return Err(invalid("expanded relation folder is a symbolic link"));
                }
                let manifest: ExpandedManifest =
                    serde_json::from_slice(&fs::read(folder.join("manifest.json"))?)?;
                if manifest.schema_version != 1
                    || manifest.source != "Wikidata"
                    || manifest.license != "CC0-1.0"
                    || manifest.source_revision != "live-query-capture"
                    || manifest.source_register != register_path
                    || manifest.platform != scope.platform
                    || manifest.wikidata_platform != scope.wikidata_platform
                    || manifest.captured_at_utc.is_empty()
                    || manifest.source_query_path != "query.rq"
                    || manifest.source_response_path != "response.json"
                    || manifest.source_bindings_path != "bindings.jsonl"
                    || manifest.properties != IDS
                    || manifest.query_limit != 30_000
                    || manifest.source_rows >= manifest.query_limit
                    || (manifest.source_rows == 0) != (manifest.distinct_items == 0)
                {
                    return Err(invalid("invalid expanded relation manifest"));
                }
                let query = pinned(
                    &folder,
                    "query.rq",
                    manifest.source_query_bytes,
                    &manifest.source_query_sha256,
                )?;
                let query_text = std::str::from_utf8(&query)
                    .map_err(|_| invalid("non-UTF-8 expanded relation query"))?;
                if !query_text.contains(&format!("wd:{}", scope.wikidata_platform))
                    || !query_text.contains("wdt:P31 wd:Q7889")
                    || !query_text.contains("wdt:P400")
                    || !query_text.contains("SELECT DISTINCT ?item ?property ?value")
                    || !query_text.contains("LIMIT 30000")
                    || IDS
                        .iter()
                        .any(|property| !query_text.contains(&format!("wdt:{property}")))
                {
                    return Err(invalid("expanded relation query scope mismatch"));
                }
                let response = pinned(
                    &folder,
                    "response.json",
                    manifest.source_response_bytes,
                    &manifest.source_response_sha256,
                )?;
                let source: Value = serde_json::from_slice(&response)?;
                if source["head"]["vars"] != json!(["item", "property", "value"]) {
                    return Err(invalid("unexpected expanded relation result columns"));
                }
                let bindings = source["results"]["bindings"]
                    .as_array()
                    .ok_or_else(|| invalid("missing expanded source bindings"))?;
                if bindings.len() != manifest.source_rows {
                    return Err(invalid("expanded response row count mismatch"));
                }
                let text = pinned(
                    &folder,
                    "bindings.jsonl",
                    manifest.source_bindings_bytes,
                    &manifest.source_bindings_sha256,
                )?;
                let raw = std::str::from_utf8(&text)
                    .map_err(|_| invalid("non-UTF-8 expanded relation JSONL"))?;
                let lines: Vec<_> = raw.lines().collect();
                if lines.len() != manifest.source_rows || (!raw.is_empty() && !raw.ends_with('\n'))
                {
                    return Err(invalid("expanded relation JSONL row count mismatch"));
                }
                let mut item_ids = HashSet::new();
                let mut scope_properties = BTreeMap::new();
                let mut kinds = BTreeMap::new();
                for (ordinal, line) in lines.iter().enumerate() {
                    let record: Value = serde_json::from_str(line)?;
                    if record != bindings[ordinal] {
                        return Err(invalid("expanded relation response and JSONL differ"));
                    }
                    let (item, property, entity, kind) = validated(&record)?;
                    item_ids.insert(item.to_owned());
                    *scope_properties
                        .entry(property.to_owned())
                        .or_insert(0usize) += 1;
                    *kinds.entry(kind.to_owned()).or_insert(0usize) += 1;
                    *counts.entry(property.to_owned()).or_insert(0usize) += 1;
                    if entity.is_some() {
                        entity_values += 1;
                    }
                    claims.push(RelationClaim {
                        platform: scope.platform.clone(),
                        item_qid: item.to_owned(),
                        property: property.to_owned(),
                        value_entity_qid: entity.map(str::to_owned),
                        raw_binding: record,
                        source_ordinal: ordinal + 1,
                        source_path: format!("{source_base}/{}/bindings.jsonl", scope.platform),
                        source_sha256: manifest.source_bindings_sha256.clone(),
                        source_response_sha256: manifest.source_response_sha256.clone(),
                        source_query_sha256: manifest.source_query_sha256.clone(),
                        captured_at_utc: manifest.captured_at_utc.clone(),
                        interpretation:
                            "independent-expanded-wikidata-source-claim-not-verified-game-identity",
                    });
                }
                if item_ids.len() != manifest.distinct_items
                    || scope_properties != manifest.property_counts
                    || kinds != manifest.rdf_value_type_counts
                {
                    return Err(invalid("expanded relation RDF evidence count mismatch"));
                }
                item_observations += item_ids.len();
                platforms.push(scope.platform.clone());
            }
        }
        if platforms.is_empty() || (selection == "all" && platforms.len() != expected_total) {
            return Err(invalid("unknown or incomplete expanded relation scope"));
        }
        Ok(Self {
            claims,
            platforms,
            item_observations,
            entity_values,
            counts,
        })
    }

    pub fn claims(&self) -> &[RelationClaim] {
        &self.claims
    }
    pub fn referenced_entity_qids(&self) -> std::collections::BTreeSet<String> {
        self.claims
            .iter()
            .filter_map(|claim| claim.value_entity_qid.clone())
            .collect()
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
    /// Exact source-identifier reverse lookup; never normalize case, parse as
    /// a number, or infer that equal strings prove identical game editions.
    pub fn search_external_id(
        &self,
        property: &str,
        identifier: &str,
        limit: usize,
    ) -> Result<(usize, usize, usize, Vec<&RelationClaim>), CatalogError> {
        if !matches!(property, "P1733" | "P2725")
            || identifier.is_empty()
            || !(1..=200).contains(&limit)
        {
            return Err(invalid(
                "exact provider ID search requires P1733 or P2725, nonempty raw ID, and limit 1..=200",
            ));
        }
        let mut total = 0;
        let mut qids = std::collections::BTreeSet::new();
        let mut platforms = std::collections::BTreeSet::new();
        let mut matches = Vec::new();
        for claim in &self.claims {
            if claim.property != property
                || claim.raw_binding["value"]["value"] != identifier
                || !matches!(
                    claim.raw_binding["value"]["type"].as_str(),
                    Some("literal" | "typed-literal")
                )
            {
                continue;
            }
            total += 1;
            qids.insert(claim.item_qid.as_str());
            platforms.insert(claim.platform.as_str());
            if matches.len() < limit {
                matches.push(claim);
            }
        }
        Ok((total, qids.len(), platforms.len(), matches))
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
    fn verify_all_37_expanded_relation_scopes_with_unmodified_evidence() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let first = WikidataRelationCatalog::open_expanded(&root, "all").unwrap();
        assert_eq!(first.platforms().len(), 19);
        assert_eq!(first.total_claims(), 18_999);
        assert_eq!(first.item_observations(), 3_108);
        assert_eq!(first.property_counts()["P1733"], 633);
        assert_eq!(first.property_counts()["P2725"], 186);
        let (_, claims) = first.search(None, Some("P179"), 2).unwrap();
        assert_eq!(claims.len(), 2);
        assert!(claims.iter().all(|claim| {
            claim.source_path.contains("expanded-relations-v1")
                && claim.source_sha256.len() == 64
                && claim.interpretation.contains("not-verified")
        }));
        let second = WikidataRelationCatalog::open_expanded_v2(&root, "all").unwrap();
        assert_eq!(second.platforms().len(), 18);
        assert_eq!(second.total_claims(), 1_461);
        assert_eq!(second.item_observations(), 303);
        assert_eq!(second.property_counts()["P1733"], 20);
        assert_eq!(second.property_counts()["P2725"], 7);
        let (_, records) = second.search(None, Some("P404"), 2).unwrap();
        assert_eq!(records.len(), 2);
        assert!(records[0].source_path.contains("expanded-relations-v2"));
        for empty in [
            "casioloopy",
            "tigergamecom",
            "gameparkgp32",
            "intertonvc4000",
        ] {
            let scope = WikidataRelationCatalog::open_expanded_v2(&root, empty).unwrap();
            assert_eq!(scope.total_claims(), 0);
            assert_eq!(scope.platforms(), &[empty.to_string()]);
        }
        assert!(WikidataRelationCatalog::open_expanded_v2(&root, "unknown").is_err());
    }

    #[test]
    fn independently_pinned_v8_relation_claims_verify_offline() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = WikidataRelationCatalog::open_expanded_v3(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 12);
        assert_eq!(catalog.total_claims(), 123);
        assert_eq!(catalog.item_observations(), 25);
        assert_eq!(catalog.property_counts().values().sum::<usize>(), 123);
        let (_, source) = catalog.search(None, None, 1).unwrap();
        assert!(source[0].source_path.contains("expanded-relations-v3"));
        for zero in ["arduboyincarduboy", "vtechcreativision", "vtechvsmile"] {
            let scope = WikidataRelationCatalog::open_expanded_v3(&root, zero).unwrap();
            assert_eq!(scope.platforms(), &[zero.to_owned()]);
            assert_eq!(scope.total_claims(), 0);
        }
        assert!(WikidataRelationCatalog::open_expanded_v3(&root, "unknown").is_err());
    }

    #[test]
    fn combined_relation_source_keeps_all_65_platforms_independent() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let all = WikidataRelationCatalog::open_combined(&root, "all").unwrap();
        assert_eq!(all.platforms().len(), 65);
        assert_eq!(all.total_claims(), 113_204);
        assert_eq!(all.item_observations(), 18_208);
        assert_eq!(all.property_counts().values().sum::<usize>(), 113_204);
        let selected = WikidataRelationCatalog::open_combined(&root, "mobilezeebo").unwrap();
        assert_eq!(selected.platforms(), &["mobilezeebo".to_owned()]);
        assert_eq!(selected.total_claims(), 100);
        assert!(WikidataRelationCatalog::open_combined(&root, "unregistered").is_err());
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
        let (claims, qids, platforms, examples) =
            catalog.search_external_id("P1733", "15750", 10).unwrap();
        assert!(claims >= 2);
        assert_eq!(qids, 2);
        assert!(platforms >= 1);
        assert!(!examples.is_empty());
        assert!(catalog.search_external_id("P1476", "15750", 10).is_err());
    }
}
