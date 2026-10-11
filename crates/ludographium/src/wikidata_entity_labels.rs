//! Independently pinned CC0 English labels for QIDs named in Wikidata
//! developer, publisher and genre claims. These are evidence, not identities.
use crate::wikidata_properties::WikidataPropertyCatalog;
use crate::wikidata_relations::WikidataRelationCatalog;
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

const BASE: &str = "data/wikidata/property-labels-v1";
const RELATION_BASE: &str = "data/wikidata/relation-labels-v1";
const EXPANDED_BASE: &str = "data/wikidata/expanded-labels-v1";

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    source: String,
    license: String,
    captured_at_utc: String,
    #[serde(default)]
    source_property_manifest_inventory_sha256: Option<String>,
    #[serde(default)]
    source_relation_manifest_inventory_sha256: Option<String>,
    entity_inventory_path: String,
    entity_inventory_sha256: String,
    source_entity_qids: usize,
    english_label_observations: usize,
    query_batch_size: usize,
    query_partitions: usize,
    source_files: Vec<SourceFile>,
}

#[derive(Debug, Deserialize)]
struct SourceFile {
    path: String,
    bytes: usize,
    sha256: String,
}

#[derive(Debug, Serialize)]
pub struct EntityLabelEvidence {
    pub qid: String,
    pub english_label: Option<String>,
    pub source_path: String,
    pub source_sha256: String,
    pub source_query_sha256: String,
    pub source_response_sha256: String,
    pub captured_at_utc: String,
    pub interpretation: &'static str,
}

pub struct WikidataEntityLabelCatalog {
    entries: BTreeMap<String, EntityLabelEvidence>,
    label_count: usize,
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
        !digits.is_empty() && !digits.starts_with('0') && digits.bytes().all(|c| c.is_ascii_digit())
    })
}

fn entity_qid(uri: &str) -> Option<&str> {
    let name = uri
        .strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/entity/"))?;
    qid(name).then_some(name)
}

/// Recompute the exact GNU sha256sum manifest-inventory digest recorded at
/// capture time, preventing a label snapshot from being silently rebound to
/// another set of independent source manifests.
fn source_manifest_inventory_sha(root: &Path, accession: &str) -> Result<String, CatalogError> {
    let register: Value =
        serde_json::from_slice(&fs::read(root.join("sources/wikidata-v1.json"))?)?;
    let platforms = register["platforms"]
        .as_array()
        .ok_or_else(|| invalid("missing Wikidata source platform register"))?;
    if platforms.len() != 16 {
        return Err(invalid("incomplete Wikidata source platform register"));
    }
    let mut paths = Vec::new();
    for platform in platforms {
        let id = platform["platform"]
            .as_str()
            .ok_or_else(|| invalid("invalid Wikidata source platform"))?;
        if id.is_empty()
            || !id
                .bytes()
                .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
        {
            return Err(invalid("unsafe Wikidata source platform path"));
        }
        paths.push(format!("{accession}/{id}/manifest.json"));
    }
    paths.sort();
    paths.dedup();
    if paths.len() != 16 {
        return Err(invalid("duplicate Wikidata source platform manifest"));
    }
    let mut inventory = String::new();
    for relative in paths {
        let path = root.join(&relative);
        if fs::symlink_metadata(&path)?.file_type().is_symlink() {
            return Err(invalid("linked Wikidata source manifest is a symlink"));
        }
        let raw = fs::read(&path)?;
        inventory.push_str(&format!("{}  {relative}\n", sha256(&raw)));
    }
    Ok(sha256(inventory.as_bytes()))
}

/// Deterministically re-hash the 74 immutable source manifests used for
/// the expanded label inventory. This exactly matches the source accession's
/// four ordered shell globs and GNU sha256sum text format.
fn expanded_source_manifest_inventory_sha(root: &Path) -> Result<String, CatalogError> {
    let cohorts: [(&str, &[usize], usize); 4] = [
        ("data/wikidata/expanded-credits-v1", &[1, 2, 3, 4], 19),
        ("data/wikidata/expanded-credits-v2", &[5, 6, 7], 18),
        ("data/wikidata/expanded-relations-v1", &[1, 2, 3, 4], 19),
        ("data/wikidata/expanded-relations-v2", &[5, 6, 7], 18),
    ];
    let mut inventory = String::new();
    for (base, versions, expected_count) in cohorts {
        let mut platforms = BTreeSet::new();
        for version in versions {
            let register = format!("sources/wikidata-platform-expansion-v{version}.json");
            let source: Value = serde_json::from_slice(&fs::read(root.join(register))?)?;
            let entries = source["platforms"]
                .as_array()
                .ok_or_else(|| invalid("expanded label source platform register is malformed"))?;
            for entry in entries {
                let name = entry["platform"]
                    .as_str()
                    .ok_or_else(|| invalid("expanded label source platform is not text"))?;
                if name.is_empty()
                    || !name
                        .bytes()
                        .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
                    || !platforms.insert(name.to_owned())
                {
                    return Err(invalid("unsafe or repeated expanded label platform scope"));
                }
            }
        }
        if platforms.len() != expected_count {
            return Err(invalid("incomplete expanded source manifest inventory"));
        }
        for platform in platforms {
            let relative = format!("{base}/{platform}/manifest.json");
            let path = root.join(&relative);
            if fs::symlink_metadata(&path)?.file_type().is_symlink() {
                return Err(invalid("expanded label source manifest is a symlink"));
            }
            let bytes = fs::read(path)?;
            inventory.push_str(&format!("{}  {relative}\n", sha256(&bytes)));
        }
    }
    Ok(sha256(inventory.as_bytes()))
}

fn checked_file(folder: &Path, entry: &SourceFile) -> Result<Vec<u8>, CatalogError> {
    if entry.bytes == 0
        || entry.sha256.len() != 64
        || !entry.sha256.bytes().all(|b| b.is_ascii_hexdigit())
        || entry.path.contains('/')
        || entry.path.contains('\\')
        || entry.path == "."
        || entry.path == ".."
    {
        return Err(invalid("invalid Wikidata label source filename or digest"));
    }
    let path = folder.join(&entry.path);
    if fs::symlink_metadata(&path)?.file_type().is_symlink() {
        return Err(invalid("Wikidata label source is a symbolic link"));
    }
    let bytes = fs::read(path)?;
    if bytes.len() != entry.bytes || sha256(&bytes) != entry.sha256 {
        return Err(invalid(format!(
            "Wikidata entity label source checksum mismatch: {}",
            entry.path
        )));
    }
    Ok(bytes)
}

impl WikidataEntityLabelCatalog {
    /// Verify the complete pinned QID inventory and all three source files for
    /// every original batch, including raw SPARQL response/JSONL equivalence.
    pub fn open(root: impl AsRef<Path>) -> Result<Self, CatalogError> {
        Self::open_at(root.as_ref(), BASE, false)
    }

    /// Source-independent labels for game series, modes, languages, countries,
    /// distribution formats and distributors, never accepted identities.
    pub fn open_relations(root: impl AsRef<Path>) -> Result<Self, CatalogError> {
        Self::open_at(root.as_ref(), RELATION_BASE, true)
    }

    /// Source-derived label inventory across both expanded credit and relation cohorts.
    pub fn open_expanded(root: impl AsRef<Path>) -> Result<Self, CatalogError> {
        Self::open_at(root.as_ref(), EXPANDED_BASE, true)
    }

    fn open_at(root: &Path, base: &'static str, relation: bool) -> Result<Self, CatalogError> {
        let folder = root.join(base);
        if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
            return Err(invalid(
                "Wikidata label source directory is a symbolic link",
            ));
        }
        let manifest: Manifest = serde_json::from_slice(&fs::read(folder.join("manifest.json"))?)?;
        let source_manifest_sha = if relation {
            manifest
                .source_relation_manifest_inventory_sha256
                .as_deref()
        } else {
            manifest
                .source_property_manifest_inventory_sha256
                .as_deref()
        };
        let source_accession = if relation {
            "data/wikidata/relations-v1"
        } else {
            "data/wikidata/properties-v1"
        };
        let actual_source_manifest_sha = if base == EXPANDED_BASE {
            expanded_source_manifest_inventory_sha(root)?
        } else {
            source_manifest_inventory_sha(root, source_accession)?
        };
        if source_manifest_sha != Some(actual_source_manifest_sha.as_str()) {
            return Err(invalid(
                "original Wikidata label accession source-manifest inventory SHA-256 mismatch",
            ));
        }
        if manifest.schema_version != 1
            || manifest.source != "Wikidata"
            || manifest.license != "CC0-1.0"
            || manifest.captured_at_utc.is_empty()
            || !source_manifest_sha.is_some_and(|value| value.len() == 64)
            || manifest.entity_inventory_path != "entities.txt"
            || manifest.query_batch_size != 100
            || manifest.query_partitions == 0
            || manifest.source_files.len() != manifest.query_partitions * 3
        {
            return Err(invalid("invalid Wikidata label accession manifest"));
        }
        let inventory_path = folder.join("entities.txt");
        if fs::symlink_metadata(&inventory_path)?
            .file_type()
            .is_symlink()
        {
            return Err(invalid("Wikidata entity inventory is a symbolic link"));
        }
        let inventory_bytes = fs::read(&inventory_path)?;
        if sha256(&inventory_bytes) != manifest.entity_inventory_sha256 {
            return Err(invalid("Wikidata label QID inventory checksum mismatch"));
        }
        let inventory = std::str::from_utf8(&inventory_bytes)
            .map_err(|_| invalid("Wikidata entity inventory is not UTF-8"))?;
        let names: Vec<&str> = inventory.lines().collect();
        if !inventory.ends_with('\n')
            || names.len() != manifest.source_entity_qids
            || names.iter().any(|name| !qid(name))
            || names.windows(2).any(|pair| pair[0] >= pair[1])
        {
            return Err(invalid("Wikidata QID inventory is incomplete or unsorted"));
        }
        let expected: BTreeSet<&str> = names.iter().copied().collect();
        let batch_folder = folder.join("batches");
        if fs::symlink_metadata(&batch_folder)?
            .file_type()
            .is_symlink()
        {
            return Err(invalid("Wikidata label batch directory is a symbolic link"));
        }
        let mut source_files = BTreeMap::new();
        for entry in manifest.source_files {
            if source_files.insert(entry.path.clone(), entry).is_some() {
                return Err(invalid("duplicated Wikidata label source file"));
            }
        }
        let mut entries = BTreeMap::new();
        let mut labels = 0;
        for batch in 0..manifest.query_partitions {
            let basename = format!("part-{batch:04}");
            let query_file = format!("{basename}.rq");
            let response_file = format!("{basename}.response.json");
            let lines_file = format!("{basename}.jsonl");
            let get = |name: &str| -> Result<&SourceFile, CatalogError> {
                source_files
                    .get(name)
                    .ok_or_else(|| invalid(format!("missing Wikidata label source: {name}")))
            };
            let query_entry = get(&query_file)?;
            let query = checked_file(&batch_folder, query_entry)?;
            let query_text = std::str::from_utf8(&query)
                .map_err(|_| invalid("Wikidata entity label query is not UTF-8"))?;
            if !query_text.starts_with("SELECT ?entity ?label WHERE {")
                || !query_text.contains("VALUES ?entity {")
                || !query_text.contains("OPTIONAL { ?entity rdfs:label ?label")
                || !query_text.contains("LIMIT 1000")
            {
                return Err(invalid("unexpected Wikidata label query scope"));
            }
            let values = query_text
                .split_once("VALUES ?entity {")
                .and_then(|(_, remaining)| remaining.split_once('}'))
                .ok_or_else(|| invalid("missing Wikidata source query values"))?
                .0;
            let query_qids: BTreeSet<&str> = values
                .split_whitespace()
                .map(|token| {
                    token
                        .strip_prefix("wd:")
                        .ok_or_else(|| invalid("invalid Wikidata VALUES term"))
                })
                .collect::<Result<Vec<_>, _>>()?
                .into_iter()
                .collect();
            if query_qids.is_empty()
                || query_qids.len() > manifest.query_batch_size
                || query_qids.iter().any(|name| !qid(name))
            {
                return Err(invalid("invalid entity label query QID inventory"));
            }
            let response_entry = get(&response_file)?;
            let response = checked_file(&batch_folder, response_entry)?;
            let parsed: Value = serde_json::from_slice(&response)?;
            if parsed["head"]["vars"] != json!(["entity", "label"]) {
                return Err(invalid("unexpected Wikidata entity label response columns"));
            }
            let records = parsed["results"]["bindings"]
                .as_array()
                .ok_or_else(|| invalid("missing Wikidata label response rows"))?;
            let text_entry = get(&lines_file)?;
            let line_bytes = checked_file(&batch_folder, text_entry)?;
            let line_text = std::str::from_utf8(&line_bytes)
                .map_err(|_| invalid("Wikidata label JSONL is not UTF-8"))?;
            let jsonl: Vec<&str> = line_text.lines().collect();
            if records.len() != query_qids.len()
                || records.len() != jsonl.len()
                || !line_text.ends_with('\n')
            {
                return Err(invalid("Wikidata label batch count mismatch"));
            }
            let mut seen = BTreeSet::new();
            for (ordinal, line) in jsonl.iter().enumerate() {
                let entry: Value = serde_json::from_str(line)?;
                if entry != records[ordinal] || entry["entity"]["type"] != "uri" {
                    return Err(invalid("Wikidata label response and JSONL differ"));
                }
                let entity = entry["entity"]["value"]
                    .as_str()
                    .and_then(entity_qid)
                    .ok_or_else(|| invalid("invalid Wikidata label subject QID"))?;
                if !query_qids.contains(entity)
                    || !expected.contains(entity)
                    || !seen.insert(entity.to_owned())
                {
                    return Err(invalid("unexpected or duplicated Wikidata label QID"));
                }
                let label = match entry.get("label") {
                    None => None,
                    Some(value) => {
                        if value["type"] != "literal" || value["xml:lang"] != "en" {
                            return Err(invalid("unapproved English label binding"));
                        }
                        Some(
                            value["value"]
                                .as_str()
                                .ok_or_else(|| invalid("non-string entity label"))?
                                .to_owned(),
                        )
                    }
                };
                if label.is_some() {
                    labels += 1;
                }
                let evidence = EntityLabelEvidence {
                    qid: entity.to_owned(),
                    english_label: label,
                    source_path: format!("{base}/batches/{lines_file}"),
                    source_sha256: text_entry.sha256.clone(),
                    source_query_sha256: query_entry.sha256.clone(),
                    source_response_sha256: response_entry.sha256.clone(),
                    captured_at_utc: manifest.captured_at_utc.clone(),
                    interpretation: if base == EXPANDED_BASE {
                        "independent-expanded-wikidata-english-label-not-canonical-game-or-company"
                    } else if relation {
                        "independent-wikidata-relation-english-label-not-canonical-game-or-release"
                    } else {
                        "independent-wikidata-english-label-not-canonical-company-or-genre"
                    },
                };
                if entries.insert(entity.to_owned(), evidence).is_some() {
                    return Err(invalid("Wikidata QID appears in multiple label partitions"));
                }
            }
            if seen.iter().map(String::as_str).collect::<BTreeSet<_>>() != query_qids {
                return Err(invalid("Wikidata label response omitted queried entities"));
            }
        }
        if entries.len() != manifest.source_entity_qids
            || labels != manifest.english_label_observations
            || entries.keys().map(String::as_str).collect::<BTreeSet<_>>() != expected
        {
            return Err(invalid(
                "Wikidata English-label inventory/coverage mismatch",
            ));
        }
        Ok(Self {
            entries,
            label_count: labels,
        })
    }

    /// Verify that labels were collected for exactly the QID-valued entity
    /// references in the separately committed property source accession.
    pub fn verify_referenced_qids(
        &self,
        properties: &WikidataPropertyCatalog,
    ) -> Result<(), CatalogError> {
        let declared = properties.referenced_entity_qids();
        if declared != self.entries.keys().cloned().collect() {
            return Err(invalid(
                "Wikidata entity labels do not cover the original property QIDs",
            ));
        }
        Ok(())
    }

    /// Ensure every QID-valued source relation has an independent label
    /// observation, including QIDs with no English label at capture time.
    pub fn verify_relation_qids(
        &self,
        relations: &WikidataRelationCatalog,
    ) -> Result<(), CatalogError> {
        if relations.referenced_entity_qids() != self.entries.keys().cloned().collect() {
            return Err(invalid(
                "Wikidata relation entity-label QIDs do not match pinned source relations",
            ));
        }
        Ok(())
    }

    /// Verify that the expanded label inventory is exactly the union of
    /// entity-QID references from both independently pinned source families.
    pub fn verify_expanded_referenced_qids(
        &self,
        credits_v1: &WikidataPropertyCatalog,
        credits_v2: &WikidataPropertyCatalog,
        relations_v1: &WikidataRelationCatalog,
        relations_v2: &WikidataRelationCatalog,
    ) -> Result<(), CatalogError> {
        let mut declared = credits_v1.referenced_entity_qids();
        declared.extend(credits_v2.referenced_entity_qids());
        declared.extend(relations_v1.referenced_entity_qids());
        declared.extend(relations_v2.referenced_entity_qids());
        if declared != self.entries.keys().cloned().collect() {
            return Err(invalid(
                "expanded label inventory differs from QIDs referenced by pinned source claims",
            ));
        }
        Ok(())
    }

    pub fn total_qids(&self) -> usize {
        self.entries.len()
    }
    pub fn english_label_count(&self) -> usize {
        self.label_count
    }
    pub fn lookup(&self, qid: &str) -> Option<&EntityLabelEvidence> {
        self.entries.get(qid)
    }
}

#[cfg(test)]
mod tests {
    use super::WikidataEntityLabelCatalog;
    use crate::wikidata_properties::WikidataPropertyCatalog;
    use crate::wikidata_relations::WikidataRelationCatalog;
    use std::path::Path;

    #[test]
    fn pinned_entity_labels_are_complete_and_source_grounded() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let labels = WikidataEntityLabelCatalog::open(&root).unwrap();
        assert_eq!(labels.total_qids(), 2_768);
        assert_eq!(labels.english_label_count(), 2_614);
        assert_eq!(
            labels.lookup("Q107").unwrap().english_label.as_deref(),
            Some("space")
        );
        let source = WikidataPropertyCatalog::open(&root, "all").unwrap();
        labels.verify_referenced_qids(&source).unwrap();
        assert!(labels.lookup("Q0").is_none());
    }

    #[test]
    fn expanded_source_labels_are_complete_and_independently_provenanced() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let labels = WikidataEntityLabelCatalog::open_expanded(&root).unwrap();
        assert_eq!(labels.total_qids(), 2_255);
        assert_eq!(labels.english_label_count(), 2_079);
        assert!(labels.lookup("Q0").is_none());
        let credits_v1 = WikidataPropertyCatalog::open_expanded(&root, "all").unwrap();
        let credits_v2 = WikidataPropertyCatalog::open_expanded_v2(&root, "all").unwrap();
        let relations_v1 = WikidataRelationCatalog::open_expanded(&root, "all").unwrap();
        let relations_v2 = WikidataRelationCatalog::open_expanded_v2(&root, "all").unwrap();
        labels
            .verify_expanded_referenced_qids(
                &credits_v1,
                &credits_v2,
                &relations_v1,
                &relations_v2,
            )
            .unwrap();
        let sample = labels.lookup("Q100350796").unwrap();
        assert_eq!(sample.source_sha256.len(), 64);
        assert!(sample.source_path.contains("expanded-labels-v1"));
        assert!(sample.interpretation.contains("not-canonical"));
    }

    #[test]
    fn captured_relations_have_separately_verified_entity_labels() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let labels = WikidataEntityLabelCatalog::open_relations(&root).unwrap();
        assert_eq!(labels.total_qids(), 1_837);
        assert_eq!(labels.english_label_count(), 1_639);
        let claims = WikidataRelationCatalog::open(&root, "all").unwrap();
        labels.verify_relation_qids(&claims).unwrap();
        assert!(labels.lookup("Q0").is_none());
        assert!(labels.lookup("Q208850").is_some());
    }
}
