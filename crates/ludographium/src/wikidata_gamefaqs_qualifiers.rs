//! Complete original GameFAQs (P4769) statement-level source observations.
//! The optional P400 qualifier belongs to the statement, not necessarily the
//! P400 item platform used to select a Wikidata query partition.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const BASE: &str = "data/wikidata/gamefaqs-qualifiers-v1";

#[derive(Deserialize)]
struct Register {
    schema_version: u32,
    provider: String,
    provider_license: String,
    platforms: Vec<RegisteredPlatform>,
}
#[derive(Deserialize)]
struct RegisteredPlatform {
    platform: String,
    wikidata_platform: String,
}
#[derive(Deserialize)]
struct Manifest {
    schema_version: u32,
    source: String,
    license: String,
    platform: String,
    wikidata_platform: String,
    source_revision: String,
    captured_at_utc: String,
    property: String,
    optional_qualifier: String,
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
    distinct_source_statements: usize,
    rows_with_explicit_platform_qualifier: usize,
    query_limit: usize,
}

#[derive(Debug, Serialize)]
pub struct GameFaqsStatement {
    pub platform: String,
    pub source_platform_qid: String,
    pub item_qid: String,
    pub statement_uri: String,
    pub identifier: String,
    pub qualifier_platform_qid: Option<String>,
    pub qualifier_scope: &'static str,
    pub raw_binding: Value,
    pub source_ordinal: usize,
    pub source_path: String,
    pub source_sha256: String,
    pub source_query_sha256: String,
    pub source_response_sha256: String,
    pub captured_at_utc: String,
    pub interpretation: &'static str,
}

pub struct GameFaqsQualifierCatalog {
    claims: Vec<GameFaqsStatement>,
    platforms: Vec<String>,
    counts: BTreeMap<String, usize>,
    distinct_statements_per_partition: usize,
}

fn invalid(message: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(message.into())
}
fn digest(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}
fn qid(value: &str) -> bool {
    value.strip_prefix('Q').is_some_and(|digits| {
        !digits.is_empty() && !digits.starts_with('0')
            && digits.bytes().all(|byte| byte.is_ascii_digit())
    })
}
fn item_qid(uri: &str) -> Option<&str> {
    let id = uri
        .strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/entity/"))?;
    qid(id).then_some(id)
}
fn original(directory: &Path, name: &str, bytes: usize, sha: &str) -> Result<Vec<u8>, CatalogError> {
    let path = directory.join(name);
    if fs::symlink_metadata(&path)?.file_type().is_symlink() {
        return Err(invalid("Original GameFAQs source file is a symbolic link"));
    }
    let source = fs::read(path)?;
    if source.len() != bytes || digest(&source) != sha {
        return Err(invalid(format!("GameFAQs source digest mismatch: {name}")));
    }
    Ok(source)
}

impl GameFaqsQualifierCatalog {
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let register: Register =
            serde_json::from_slice(&fs::read(root.join("sources/wikidata-v1.json"))?)?;
        if register.schema_version != 1
            || register.provider != "wikidata"
            || register.provider_license != "CC0-1.0"
            || register.platforms.len() != 16
        {
            return Err(invalid("Wikidata platform registry mismatch"));
        }
        let mut registered = HashSet::new();
        let mut claims = Vec::new();
        let mut platforms = Vec::new();
        let mut counts = BTreeMap::new();
        let mut distinct_statements_per_partition = 0;
        for platform in register.platforms {
            if !registered.insert(platform.platform.clone())
                || platform.platform.is_empty()
                || !platform.platform.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
                || !qid(&platform.wikidata_platform)
            {
                return Err(invalid("Invalid registered source platform"));
            }
            if selection != "all" && selection != platform.platform {
                continue;
            }
            let folder = root.join(BASE).join(&platform.platform);
            if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
                return Err(invalid("GameFAQs source folder must not be a symlink"));
            }
            let m: Manifest = serde_json::from_slice(&fs::read(folder.join("manifest.json"))?)?;
            if m.schema_version != 1
                || m.source != "Wikidata"
                || m.license != "CC0-1.0"
                || m.source_revision != "live-query-capture"
                || m.platform != platform.platform
                || m.wikidata_platform != platform.wikidata_platform
                || m.property != "P4769"
                || m.optional_qualifier != "P400"
                || m.source_query_path != "query.rq"
                || m.source_response_path != "response.json"
                || m.source_bindings_path != "bindings.jsonl"
                || m.captured_at_utc.is_empty()
                || m.query_limit != 30_000
                || m.source_rows == 0
                || m.source_rows >= m.query_limit
                || m.distinct_source_statements == 0
                || m.rows_with_explicit_platform_qualifier > m.source_rows
            {
                return Err(invalid(format!("GameFAQs source manifest mismatch: {}", platform.platform)));
            }
            let query = original(&folder, "query.rq", m.source_query_bytes, &m.source_query_sha256)?;
            let query_text = std::str::from_utf8(&query)
                .map_err(|_| invalid("Non-UTF-8 GameFAQs original SPARQL query"))?;
            if !query_text.contains(&format!("wd:{}", platform.wikidata_platform))
                || !query_text.contains("p:P4769")
                || !query_text.contains("ps:P4769")
                || !query_text.contains("pq:P400")
                || !query_text.contains("LIMIT 30000")
            {
                return Err(invalid("GameFAQs query platform/property scope differs"));
            }
            let response = original(&folder, "response.json", m.source_response_bytes,
                &m.source_response_sha256)?;
            let response_json: Value = serde_json::from_slice(&response)?;
            if response_json["head"]["vars"]
                != json!(["item", "statement", "identifier", "qualifiedPlatform"])
            {
                return Err(invalid("GameFAQs response bindings schema changed"));
            }
            let rows = response_json["results"]["bindings"].as_array()
                .ok_or_else(|| invalid("Missing original statement response rows"))?;
            if rows.len() != m.source_rows {
                return Err(invalid("Original GameFAQs response row count differs"));
            }
            let raw = original(&folder, "bindings.jsonl", m.source_bindings_bytes,
                &m.source_bindings_sha256)?;
            let source = std::str::from_utf8(&raw)
                .map_err(|_| invalid("Non-UTF-8 original GameFAQs JSONL"))?;
            let lines: Vec<_> = source.lines().collect();
            if !source.ends_with('\n') || lines.len() != rows.len() {
                return Err(invalid("Original GameFAQs JSONL row count differs"));
            }
            let mut statement_uris = HashSet::new();
            let mut qualified = 0;
            for (ordinal, line) in lines.iter().enumerate() {
                let row: Value = serde_json::from_str(line)?;
                if row != rows[ordinal] || row["item"]["type"] != "uri"
                    || row["statement"]["type"] != "uri"
                {
                    return Err(invalid("GameFAQs original response/JSONL row mismatch"));
                }
                let game = row["item"]["value"].as_str().and_then(item_qid)
                    .ok_or_else(|| invalid("Invalid GameFAQs game QID"))?;
                let statement = row["statement"]["value"].as_str()
                    .ok_or_else(|| invalid("Missing GameFAQs original statement URI"))?;
                let actual_statement_prefix = format!("http://www.wikidata.org/entity/statement/{game}-");
                let alternate_statement_prefix = format!("https://www.wikidata.org/entity/statement/{game}-");
                if !(statement.starts_with(&actual_statement_prefix)
                    || statement.starts_with(&alternate_statement_prefix))
                    || (row["identifier"]["type"] != "literal"
                        && row["identifier"]["type"] != "typed-literal")
                {
                    return Err(invalid("GameFAQs subject, statement or identifier RDF type differs"));
                }
                let identifier = row["identifier"]["value"].as_str()
                    .filter(|value| !value.is_empty())
                    .ok_or_else(|| invalid("Missing GameFAQs source identifier"))?;
                let qualifier = match row.get("qualifiedPlatform") {
                    None => None,
                    Some(record) => {
                        if record["type"] != "uri" {
                            return Err(invalid("GameFAQs platform qualifier is not an RDF URI"));
                        }
                        qualified += 1;
                        Some(record["value"].as_str().and_then(item_qid)
                            .ok_or_else(|| invalid("Invalid Wikidata P400 qualifier QID"))?
                            .to_owned())
                    }
                };
                let scope = match qualifier.as_deref() {
                    None => "no_explicit_platform_qualifier",
                    Some(value) if value == platform.wikidata_platform => {
                        "qualifier_equals_selected_item_platform"
                    }
                    Some(_) => "qualifier_names_other_platform",
                };
                *counts.entry(scope.to_owned()).or_insert(0) += 1;
                statement_uris.insert(statement.to_owned());
                claims.push(GameFaqsStatement {
                    platform: platform.platform.clone(),
                    source_platform_qid: platform.wikidata_platform.clone(),
                    item_qid: game.to_owned(),
                    statement_uri: statement.to_owned(),
                    identifier: identifier.to_owned(),
                    qualifier_platform_qid: qualifier,
                    qualifier_scope: scope,
                    raw_binding: row,
                    source_ordinal: ordinal + 1,
                    source_path: format!("{BASE}/{}/bindings.jsonl", platform.platform),
                    source_sha256: m.source_bindings_sha256.clone(),
                    source_query_sha256: m.source_query_sha256.clone(),
                    source_response_sha256: m.source_response_sha256.clone(),
                    captured_at_utc: m.captured_at_utc.clone(),
                    interpretation: "original-wikidata-statement-and-qualifier-not-provider-verified-game-release-identity",
                });
            }
            if qualified != m.rows_with_explicit_platform_qualifier
                || statement_uris.len() != m.distinct_source_statements
            {
                return Err(invalid("Original GameFAQs source qualifier/statement counts differ"));
            }
            distinct_statements_per_partition += statement_uris.len();
            platforms.push(platform.platform);
        }
        if platforms.is_empty() || (selection == "all" && platforms.len() != 16) {
            return Err(invalid(format!("Unknown or incomplete GameFAQs platform: {selection}")));
        }
        Ok(Self { claims, platforms, counts, distinct_statements_per_partition })
    }

    pub fn total_rows(&self) -> usize {
        self.claims.len()
    }
    pub fn source_partitions(&self) -> &[String] {
        &self.platforms
    }
    pub fn qualifier_counts(&self) -> &BTreeMap<String, usize> {
        &self.counts
    }
    pub fn distinct_source_statements_per_partition(&self) -> usize {
        self.distinct_statements_per_partition
    }
    pub fn search(
        &self,
        game_qid: Option<&str>,
        identifier: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&GameFaqsStatement>), CatalogError> {
        if !(1..=200).contains(&limit)
            || game_qid.is_some_and(|name| !qid(name))
            || identifier.is_some_and(str::is_empty)
        {
            return Err(invalid("Invalid GameFAQs search: valid QID and/or raw ID, limit 1..=200"));
        }
        let mut count = 0;
        let mut results = Vec::new();
        for row in &self.claims {
            if game_qid.is_some_and(|qid| qid != row.item_qid)
                || identifier.is_some_and(|id| id != row.identifier)
            {
                continue;
            }
            count += 1;
            if results.len() < limit {
                results.push(row);
            }
        }
        Ok((count, results))
    }
}

#[cfg(test)]
mod tests {
    use super::GameFaqsQualifierCatalog;
    use std::path::Path;

    #[test]
    fn preserve_source_qualifiers_without_promoting_item_platforms_into_qualifiers() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = GameFaqsQualifierCatalog::open(&root, "all").unwrap();
        assert_eq!(catalog.source_partitions().len(), 16);
        assert_eq!(catalog.total_rows(), 23_623);
        assert_eq!(catalog.distinct_source_statements_per_partition(), 23_623);
        assert_eq!(catalog.qualifier_counts()["no_explicit_platform_qualifier"], 497);
        assert_eq!(catalog.qualifier_counts()["qualifier_equals_selected_item_platform"], 9_042);
        assert_eq!(catalog.qualifier_counts()["qualifier_names_other_platform"], 14_084);
        let atari = GameFaqsQualifierCatalog::open(&root, "atari2600").unwrap();
        let (count, sample) = atari.search(None, None, 3).unwrap();
        assert_eq!(count, 313);
        assert_eq!(sample.len(), 3);
        assert!(sample.iter().all(|row| row.source_sha256.len() == 64));
        assert!(GameFaqsQualifierCatalog::open(&root, "bogus").is_err());
    }
}
