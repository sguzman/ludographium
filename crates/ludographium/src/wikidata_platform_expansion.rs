//! Independent CC0 platform-extension source observations.
//! The original 16-platform accession remains immutable. No work/media join.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const BASE_V1: &str = "data/wikidata/platform-expansion-v1";
const BASE_V2: &str = "data/wikidata/platform-expansion-v2";
const BASE_V3: &str = "data/wikidata/platform-expansion-v3";
const BASE_V4: &str = "data/wikidata/platform-expansion-v4";
const BASE_V5: &str = "data/wikidata/platform-expansion-v5";
const BASE_V6: &str = "data/wikidata/platform-expansion-v6";
const BASE_V7: &str = "data/wikidata/platform-expansion-v7";
const MAP_V1: &[(&str, &str)] = &[
    ("atari7800", "Q753600"),
    ("sonyplaystationportable", "Q170325"),
    ("sonyplaystationvita", "Q188808"),
];
const MAP_V2: &[(&str, &str)] = &[
    ("atarijaguar", "Q650601"),
    ("atarilynx", "Q753657"),
    ("bandaiwonderswan", "Q1065792"),
    ("bandaiwonderswancolor", "Q1048035"),
];

const MAP_V3: &[(&str, &str)] = &[
    ("nintendofamilycomputerdisksystem", "Q135321"),
    ("snkneogeopocket", "Q939881"),
    ("snkneogeopocketcolor", "Q1977455"),
    ("segasg1000", "Q1136956"),
    ("sega32x", "Q1063978"),
    ("necpcengineturbografx16", "Q1057377"),
];

const MAP_V4: &[(&str, &str)] = &[
    ("atari5200", "Q743222"),
    ("colecocolecovision", "Q1046862"),
    ("gcevectrex", "Q767631"),
    ("mattelintellivision", "Q1061441"),
    ("magnavoxodyssey2", "Q576932"),
    ("nintendopokemonmini", "Q1759168"),
];

const MAP_V5: &[(&str, &str)] = &[
    ("casioloopy", "Q661952"),
    ("casiopv1000", "Q60407"),
    ("watarasupervision", "Q732683"),
    ("necpcenginesupergrafx", "Q202375"),
    ("segapico", "Q1374482"),
    ("nintendosatellaview", "Q1193565"),
];

const MAP_V6: &[(&str, &str)] = &[
    ("gg", "Q751719"),
    ("nintendonewnintendo3ds", "Q17679679"),
    ("nintendonintendodsi", "Q637178"),
    ("nintendonintendo64dd", "Q253044"),
    ("tigergamecom", "Q2498396"),
    ("fairchildchannelf", "Q1053294"),
];

const MAP_V7: &[(&str, &str)] = &[
    ("emersonarcadia2001", "Q1196518"),
    ("epochsupercassettevision", "Q8018077"),
    ("gameparkgp32", "Q426119"),
    ("intertonvc4000", "Q302411"),
    ("rcastudioii", "Q1143954"),
    ("segabeena", "Q4686254"),
];

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
        !digits.is_empty() && !digits.starts_with('0') && digits.bytes().all(|b| b.is_ascii_digit())
    })
}
fn item_uri(value: &str) -> Option<&str> {
    let result = value
        .strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| value.strip_prefix("https://www.wikidata.org/entity/"))?;
    qid(result).then_some(result)
}
fn original(folder: &Path, name: &str, bytes: usize, hash: &str) -> Result<Vec<u8>, CatalogError> {
    let path = folder.join(name);
    if fs::symlink_metadata(&path)?.file_type().is_symlink() {
        return Err(invalid(
            "Pinned Wikidata source must not be a symbolic link",
        ));
    }
    let body = fs::read(&path)?;
    if body.len() != bytes || sha256(&body) != hash {
        return Err(invalid(format!(
            "Pinned Wikidata source differs: {}",
            path.display()
        )));
    }
    Ok(body)
}

impl ExpandedWikidataCatalog {
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V1,
            "sources/wikidata-platform-expansion-v1.json",
            MAP_V1,
        )
    }

    pub fn open_v2(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V2,
            "sources/wikidata-platform-expansion-v2.json",
            MAP_V2,
        )
    }

    pub fn open_v3(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V3,
            "sources/wikidata-platform-expansion-v3.json",
            MAP_V3,
        )
    }

    pub fn open_v4(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V4,
            "sources/wikidata-platform-expansion-v4.json",
            MAP_V4,
        )
    }

    pub fn open_v5(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V5,
            "sources/wikidata-platform-expansion-v5.json",
            MAP_V5,
        )
    }

    pub fn open_v6(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V6,
            "sources/wikidata-platform-expansion-v6.json",
            MAP_V6,
        )
    }

    pub fn open_v7(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(
            root.as_ref(),
            selection,
            BASE_V7,
            "sources/wikidata-platform-expansion-v7.json",
            MAP_V7,
        )
    }

    fn open_source(
        root: &Path,
        selection: &str,
        base: &str,
        register_path: &str,
        approved_platforms: &[(&str, &str)],
    ) -> Result<Self, CatalogError> {
        let register: Register = serde_json::from_slice(&fs::read(root.join(register_path))?)?;
        if register.schema_version != 1
            || register.source != "Wikidata"
            || register.license != "CC0-1.0"
            || register.query_limit != 20_000
            || register.platforms.len() != approved_platforms.len()
        {
            return Err(invalid(
                "Unexpected Wikidata platform expansion registration",
            ));
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
            let approved = approved_platforms.iter().any(|(platform, qid)| {
                *platform == scope.platform && *qid == scope.wikidata_platform
            });
            if !approved || !seen.insert(scope.platform.clone()) {
                return Err(invalid("Unverified or repeated expansion platform mapping"));
            }
            if selection != "all" && selection != scope.platform {
                continue;
            }
            let folder = root.join(base).join(&scope.platform);
            if fs::symlink_metadata(&folder)?.file_type().is_symlink() {
                return Err(invalid("Pinned source folder is a symbolic link"));
            }
            let manifest: Manifest =
                serde_json::from_slice(&fs::read(folder.join("manifest.json"))?)?;
            if manifest.schema_version != 1
                || manifest.source != "Wikidata"
                || manifest.license != "CC0-1.0"
                || manifest.source_revision != "live-query-capture"
                || manifest.platform != scope.platform
                || manifest.wikidata_platform != scope.wikidata_platform
                || manifest.query_limit != register.query_limit
                || manifest.source_rows >= manifest.query_limit
                || (!matches!(base, BASE_V5 | BASE_V6 | BASE_V7)
                    && (manifest.source_rows == 0 || manifest.distinct_item_qids == 0))
                || (matches!(base, BASE_V5 | BASE_V6 | BASE_V7)
                    && ((manifest.source_rows == 0) != (manifest.distinct_item_qids == 0)))
                || manifest.source_query_path != "query.rq"
                || manifest.source_response_path != "response.json"
                || manifest.source_bindings_path != "bindings.jsonl"
                || manifest.captured_at_utc.is_empty()
            {
                return Err(invalid(format!(
                    "Invalid source manifest for {}",
                    scope.platform
                )));
            }
            let query = original(
                &folder,
                "query.rq",
                manifest.source_query_bytes,
                &manifest.source_query_sha256,
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
                &folder,
                "response.json",
                manifest.source_response_bytes,
                &manifest.source_response_sha256,
            )?;
            let response_json: Value = serde_json::from_slice(&response)?;
            if response_json["head"]["vars"] != json!(["item", "itemLabel", "publication"]) {
                return Err(invalid("Unexpected original Wikidata response columns"));
            }
            let bindings = response_json["results"]["bindings"]
                .as_array()
                .ok_or_else(|| invalid("Missing original Wikidata bindings"))?;
            if bindings.len() != manifest.source_rows {
                return Err(invalid(
                    "Original response and manifest row counts disagree",
                ));
            }
            let raw_text = original(
                &folder,
                "bindings.jsonl",
                manifest.source_bindings_bytes,
                &manifest.source_bindings_sha256,
            )?;
            let text = std::str::from_utf8(&raw_text)
                .map_err(|_| invalid("Non-UTF-8 original JSONL bindings"))?;
            let lines: Vec<&str> = text.lines().collect();
            if (!text.is_empty() && !text.ends_with('\n')) || lines.len() != manifest.source_rows {
                return Err(invalid("Original JSONL rows do not match manifest"));
            }
            let mut unique_items = HashSet::new();
            let mut labels = 0;
            let mut dates = 0;
            let mut nonliteral = 0;
            for (index, line) in lines.iter().enumerate() {
                let record: Value = serde_json::from_str(line)?;
                if record != bindings[index] || record["item"]["type"] != "uri" {
                    return Err(invalid(
                        "Original Wikidata response differs from JSONL evidence",
                    ));
                }
                let item = record["item"]["value"]
                    .as_str()
                    .and_then(item_uri)
                    .ok_or_else(|| invalid("Original item is not a valid Wikidata QID"))?;
                unique_items.insert(item.to_owned());
                let english_label = match record.get("itemLabel") {
                    None => None,
                    Some(value) => {
                        if value["type"] != "literal" || value["xml:lang"] != "en" {
                            return Err(invalid("Unexpected English source label RDF type"));
                        }
                        labels += 1;
                        Some(
                            value["value"]
                                .as_str()
                                .ok_or_else(|| invalid("Original English label is not text"))?
                                .to_owned(),
                        )
                    }
                };
                let publication_binding_kind = match record.get("publication") {
                    None => None,
                    Some(value) => {
                        let kind = value["type"]
                            .as_str()
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
                    source_path: format!("{base}/{}/bindings.jsonl", scope.platform),
                    source_sha256: manifest.source_bindings_sha256.clone(),
                    source_response_sha256: manifest.source_response_sha256.clone(),
                    source_query_sha256: manifest.source_query_sha256.clone(),
                    captured_at_utc: manifest.captured_at_utc.clone(),
                    interpretation:
                        "attributed-source-evidence-not-canonical-work-media-or-release-identity",
                });
            }
            if unique_items.len() != manifest.distinct_item_qids
                || labels != manifest.rows_with_english_label
                || dates != manifest.rows_with_publication_date
                || nonliteral != manifest.rows_with_nonliteral_publication
            {
                return Err(invalid(
                    "Source item, label or RDF date count differs from pinned manifest",
                ));
            }
            distinct_item_observations += unique_items.len();
            literal_date_claims += dates;
            english_label_rows += labels;
            nonliteral_publication_bindings += nonliteral;
            platform_row_counts.insert(scope.platform.clone(), manifest.source_rows);
            platforms.push(scope.platform);
        }
        if platforms.is_empty()
            || (selection == "all" && platforms.len() != approved_platforms.len())
        {
            return Err(invalid(format!(
                "Unknown or incomplete source platform: {selection}"
            )));
        }
        Ok(Self {
            observations,
            platforms,
            distinct_item_observations,
            literal_date_claims,
            nonliteral_publication_bindings,
            english_label_rows,
            platform_row_counts,
        })
    }
    pub fn observations(&self) -> &[ExpandedWikidataObservation] {
        &self.observations
    }
    pub fn platforms(&self) -> &[String] {
        &self.platforms
    }
    pub fn total_rows(&self) -> usize {
        self.observations.len()
    }
    pub fn distinct_item_observations(&self) -> usize {
        self.distinct_item_observations
    }
    pub fn literal_date_claims(&self) -> usize {
        self.literal_date_claims
    }
    pub fn nonliteral_publication_bindings(&self) -> usize {
        self.nonliteral_publication_bindings
    }
    pub fn english_label_rows(&self) -> usize {
        self.english_label_rows
    }
    pub fn platform_row_counts(&self) -> &BTreeMap<String, usize> {
        &self.platform_row_counts
    }

    pub fn search(
        &self,
        qid_filter: Option<&str>,
        title: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&ExpandedWikidataObservation>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid_filter.is_some_and(|value| !qid(value))
            || title.is_some_and(|value| value.trim().is_empty())
        {
            return Err(invalid(
                "Require valid source QID, nonblank title and limit 1..=200",
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut total = 0;
        let mut rows = Vec::new();
        for entry in &self.observations {
            if qid_filter.is_some_and(|value| entry.item_qid != value)
                || needle.as_ref().is_some_and(|value| {
                    !entry
                        .english_label
                        .as_ref()
                        .is_some_and(|label| label.to_lowercase().contains(value))
                })
            {
                continue;
            }
            total += 1;
            if rows.len() < limit {
                rows.push(entry);
            }
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
        assert_eq!(
            catalog.platform_row_counts()["sonyplaystationportable"],
            2_088
        );
        assert_eq!(catalog.platform_row_counts()["sonyplaystationvita"], 1_699);
        let vita = ExpandedWikidataCatalog::open(&root, "sonyplaystationvita").unwrap();
        assert_eq!(vita.nonliteral_publication_bindings(), 5);
        let (count, rows) = catalog.search(None, None, 1).unwrap();
        assert_eq!(count, 3_888);
        assert_eq!(rows.len(), 1);
        assert!(ExpandedWikidataCatalog::open(&root, "unknown").is_err());
    }

    #[test]
    fn four_additional_atari_and_wonderswan_partitions_are_verified() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open_v2(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 4);
        assert_eq!(catalog.total_rows(), 305);
        assert_eq!(catalog.distinct_item_observations(), 206);
        assert_eq!(catalog.literal_date_claims(), 282);
        assert_eq!(catalog.nonliteral_publication_bindings(), 0);
        assert_eq!(catalog.platform_row_counts()["atarijaguar"], 101);
        assert_eq!(catalog.platform_row_counts()["atarilynx"], 89);
        assert_eq!(catalog.platform_row_counts()["bandaiwonderswan"], 75);
        assert_eq!(catalog.platform_row_counts()["bandaiwonderswancolor"], 40);
        assert!(ExpandedWikidataCatalog::open_v2(&root, "invalid").is_err());
    }

    #[test]
    fn six_more_source_platforms_are_hash_verified_and_independent() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open_v3(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 6);
        assert_eq!(catalog.total_rows(), 1_148);
        assert_eq!(catalog.distinct_item_observations(), 655);
        assert_eq!(catalog.literal_date_claims(), 1_114);
        assert_eq!(catalog.nonliteral_publication_bindings(), 0);
        assert_eq!(
            catalog.platform_row_counts()["nintendofamilycomputerdisksystem"],
            319
        );
        assert_eq!(catalog.platform_row_counts()["snkneogeopocket"], 5);
        assert_eq!(catalog.platform_row_counts()["snkneogeopocketcolor"], 45);
        assert_eq!(catalog.platform_row_counts()["segasg1000"], 88);
        assert_eq!(catalog.platform_row_counts()["sega32x"], 98);
        assert_eq!(
            catalog.platform_row_counts()["necpcengineturbografx16"],
            593
        );
        assert!(ExpandedWikidataCatalog::open_v3(&root, "invalid").is_err());
        let (count, result) = catalog.search(None, None, 1).unwrap();
        assert_eq!(count, 1_148);
        assert_eq!(result.len(), 1);
        assert!(result[0].source_path.contains("platform-expansion-v3"));
    }

    #[test]
    fn legacy_home_console_and_pokemon_mini_source_evidence_is_preserved() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open_v4(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 6);
        assert_eq!(catalog.total_rows(), 482);
        assert_eq!(catalog.distinct_item_observations(), 356);
        assert_eq!(catalog.literal_date_claims(), 425);
        assert_eq!(catalog.nonliteral_publication_bindings(), 0);
        assert_eq!(catalog.platform_row_counts()["atari5200"], 109);
        assert_eq!(catalog.platform_row_counts()["colecocolecovision"], 191);
        assert_eq!(catalog.platform_row_counts()["gcevectrex"], 19);
        assert_eq!(catalog.platform_row_counts()["mattelintellivision"], 123);
        assert_eq!(catalog.platform_row_counts()["magnavoxodyssey2"], 30);
        assert_eq!(catalog.platform_row_counts()["nintendopokemonmini"], 10);
        let (total, samples) = catalog.search(None, None, 1).unwrap();
        assert_eq!(total, 482);
        assert!(samples[0].source_path.contains("platform-expansion-v4"));
        assert!(ExpandedWikidataCatalog::open_v4(&root, "invalid").is_err());
    }

    #[test]
    fn seventh_source_cohort_preserves_six_scopes_and_two_empty_responses() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open_v7(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 6);
        assert_eq!(catalog.total_rows(), 20);
        assert_eq!(catalog.distinct_item_observations(), 14);
        assert_eq!(catalog.english_label_rows(), 18);
        assert_eq!(catalog.literal_date_claims(), 20);
        assert_eq!(catalog.nonliteral_publication_bindings(), 0);
        assert_eq!(catalog.platform_row_counts()["emersonarcadia2001"], 3);
        assert_eq!(
            catalog.platform_row_counts()["epochsupercassettevision"],
            14
        );
        assert_eq!(catalog.platform_row_counts()["gameparkgp32"], 0);
        assert_eq!(catalog.platform_row_counts()["intertonvc4000"], 0);
        assert_eq!(catalog.platform_row_counts()["rcastudioii"], 1);
        assert_eq!(catalog.platform_row_counts()["segabeena"], 2);
        for platform in ["gameparkgp32", "intertonvc4000"] {
            let empty = ExpandedWikidataCatalog::open_v7(&root, platform).unwrap();
            let (count, rows) = empty.search(None, None, 2).unwrap();
            assert_eq!(count, 0);
            assert!(rows.is_empty());
        }
        assert!(ExpandedWikidataCatalog::open_v7(&root, "unknown").is_err());
        assert!(catalog.search(Some("Q0"), None, 1).is_err());
        assert!(catalog.observations().iter().all(|item| {
            item.source_path.contains("platform-expansion-v7")
                && item.source_sha256.len() == 64
                && item.interpretation.contains("not-canonical")
        }));
    }

    #[test]
    fn sixth_source_cohort_preserves_zero_result_and_nonliteral_evidence() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open_v6(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 6);
        assert_eq!(catalog.total_rows(), 662);
        assert_eq!(catalog.distinct_item_observations(), 309);
        assert_eq!(catalog.english_label_rows(), 575);
        assert_eq!(catalog.literal_date_claims(), 642);
        assert_eq!(catalog.nonliteral_publication_bindings(), 2);
        assert_eq!(catalog.platform_row_counts()["gg"], 321);
        assert_eq!(catalog.platform_row_counts()["nintendonewnintendo3ds"], 127);
        assert_eq!(catalog.platform_row_counts()["nintendonintendodsi"], 209);
        assert_eq!(catalog.platform_row_counts()["nintendonintendo64dd"], 3);
        assert_eq!(catalog.platform_row_counts()["tigergamecom"], 0);
        assert_eq!(catalog.platform_row_counts()["fairchildchannelf"], 2);
        let empty = ExpandedWikidataCatalog::open_v6(&root, "tigergamecom").unwrap();
        let (zero_count, zero_rows) = empty.search(None, None, 5).unwrap();
        assert_eq!(zero_count, 0);
        assert!(zero_rows.is_empty());
        let (count, rows) = catalog.search(None, None, 1).unwrap();
        assert_eq!(count, 662);
        assert_eq!(rows.len(), 1);
        assert!(rows[0].source_path.contains("platform-expansion-v6"));
        assert!(rows[0].interpretation.contains("not-canonical"));
        assert!(ExpandedWikidataCatalog::open_v6(&root, "unknown").is_err());
        assert!(catalog.search(Some("Q0"), None, 2).is_err());
    }

    #[test]
    fn preserve_zero_result_queries_without_inventing_console_games() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let catalog = ExpandedWikidataCatalog::open_v5(&root, "all").unwrap();
        assert_eq!(catalog.platforms().len(), 6);
        assert_eq!(catalog.total_rows(), 35);
        assert_eq!(catalog.distinct_item_observations(), 22);
        assert_eq!(catalog.literal_date_claims(), 34);
        assert_eq!(catalog.nonliteral_publication_bindings(), 0);
        assert_eq!(catalog.platform_row_counts()["casioloopy"], 0);
        assert_eq!(catalog.platform_row_counts()["casiopv1000"], 11);
        assert_eq!(catalog.platform_row_counts()["watarasupervision"], 1);
        assert_eq!(catalog.platform_row_counts()["necpcenginesupergrafx"], 5);
        assert_eq!(catalog.platform_row_counts()["segapico"], 6);
        assert_eq!(catalog.platform_row_counts()["nintendosatellaview"], 12);
        let empty = ExpandedWikidataCatalog::open_v5(&root, "casioloopy").unwrap();
        let (count, returned) = empty.search(None, None, 3).unwrap();
        assert_eq!(count, 0);
        assert!(returned.is_empty());
        assert!(ExpandedWikidataCatalog::open_v5(&root, "unknown").is_err());
    }
}
