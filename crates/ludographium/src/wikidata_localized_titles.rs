//! Hash-verified original multilingual Wikidata game labels and alternate
//! titles. A language-tagged name is a source claim, not regional identity.
use crate::CatalogError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::path::Path;

const BASE: &str = "data/wikidata/localized-titles-v1";
const PREFIXES: [&str; 10] = ["en", "ja", "es", "zh", "fr", "de", "it", "ko", "ar", "pt"];
const RDFS: &str = "http://www.w3.org/2000/01/rdf-schema#label";
const SKOS: &str = "http://www.w3.org/2004/02/skos/core#altLabel";

#[derive(Debug, Deserialize)]
struct Register {
    schema_version: u32,
    provider: String,
    provider_license: String,
    platforms: Vec<Platform>,
}
#[derive(Debug, Deserialize)]
struct Platform {
    platform: String,
    wikidata_platform: String,
}
#[derive(Debug, Deserialize)]
struct ExpandedRegister {
    schema_version: u32,
    kind: String,
    source: String,
    license: String,
    query_limit: usize,
    platforms: Vec<Platform>,
}

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: u32,
    source: String,
    license: String,
    source_revision: String,
    platform: String,
    wikidata_platform: String,
    #[serde(default)]
    source_register: Option<String>,
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
    language_prefix_scope: Vec<String>,
    predicate_counts: BTreeMap<String, usize>,
    language_tag_counts: BTreeMap<String, usize>,
}

#[derive(Debug, Serialize)]
pub struct LocalizedTitleClaim {
    pub platform: String,
    pub item_qid: String,
    pub language_tag: String,
    pub name: String,
    pub name_kind: &'static str,
    pub original_binding: Value,
    pub source_ordinal: usize,
    pub source_path: String,
    pub source_sha256: String,
    pub source_response_sha256: String,
    pub source_query_sha256: String,
    pub captured_at_utc: String,
    pub interpretation: &'static str,
}

pub struct WikidataLocalizedTitleCatalog {
    claims: Vec<LocalizedTitleClaim>,
    platforms: Vec<String>,
    observed_items: usize,
    languages: BTreeMap<String, usize>,
    name_kinds: BTreeMap<String, usize>,
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
fn qid_uri(uri: &str) -> Option<&str> {
    let id = uri
        .strip_prefix("http://www.wikidata.org/entity/")
        .or_else(|| uri.strip_prefix("https://www.wikidata.org/entity/"))?;
    id.strip_prefix('Q')
        .is_some_and(|x| {
            !x.is_empty() && !x.starts_with('0') && x.bytes().all(|b| b.is_ascii_digit())
        })
        .then_some(id)
}
fn accepted_language(lang: &str) -> bool {
    let lang = lang.to_ascii_lowercase();
    let segments: Vec<_> = lang.split('-').collect();
    !segments.is_empty()
        && PREFIXES.contains(&segments[0])
        && segments
            .iter()
            .all(|value| !value.is_empty() && value.bytes().all(|b| b.is_ascii_alphanumeric()))
}
fn verified_file(
    dir: &Path,
    name: &str,
    expected_size: usize,
    expected_sha: &str,
) -> Result<Vec<u8>, CatalogError> {
    let path = dir.join(name);
    if fs::symlink_metadata(&path)?.file_type().is_symlink() {
        return Err(invalid("Wikidata localized source is a symbolic link"));
    }
    let bytes = fs::read(&path)?;
    if bytes.len() != expected_size || sha256(&bytes) != expected_sha {
        return Err(invalid(format!(
            "Wikidata localized source digest/length mismatch: {}",
            path.display()
        )));
    }
    Ok(bytes)
}
fn parse_original(row: &Value) -> Result<(&str, &'static str, &str, &str), CatalogError> {
    if row["item"]["type"] != "uri"
        || row["predicate"]["type"] != "uri"
        || row["label"]["type"] != "literal"
    {
        return Err(invalid("unexpected original localized source RDF type"));
    }
    let item = row["item"]["value"]
        .as_str()
        .and_then(qid_uri)
        .ok_or_else(|| invalid("invalid localized source game QID"))?;
    let name_kind = match row["predicate"]["value"].as_str() {
        Some(RDFS) => "label",
        Some(SKOS) => "altLabel",
        _ => return Err(invalid("unapproved localized name predicate")),
    };
    let lang = row["label"]["xml:lang"]
        .as_str()
        .ok_or_else(|| invalid("missing original language tag"))?;
    if !accepted_language(lang) {
        return Err(invalid(
            "localized name language tag is outside declared source scope",
        ));
    }
    let name = row["label"]["value"]
        .as_str()
        .filter(|value| !value.is_empty())
        .ok_or_else(|| invalid("empty localized source name"))?;
    Ok((item, name_kind, lang, name))
}

impl WikidataLocalizedTitleCatalog {
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(root.as_ref(), selection, "baseline", false)
    }

    pub fn open_expanded(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(root.as_ref(), selection, "expanded-v1", false)
    }

    pub fn open_expanded_v2(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        Self::open_source(root.as_ref(), selection, "expanded-v2", false)
    }

    /// Query every independent source cohort without conflating names or game identities.
    /// A platform-specific query loads only the matching source partition.
    pub fn open_combined(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let mut combined = Self {
            claims: Vec::new(),
            platforms: Vec::new(),
            observed_items: 0,
            languages: BTreeMap::new(),
            name_kinds: BTreeMap::new(),
            platform_row_counts: BTreeMap::new(),
        };
        let mut seen = HashSet::new();
        for cohort in ["baseline", "expanded-v1", "expanded-v2"] {
            let mut source = Self::open_source(root, selection, cohort, true)?;
            for platform in &source.platforms {
                if !seen.insert(platform.clone()) {
                    return Err(invalid(format!(
                        "localized source platform is registered in multiple cohorts: {platform}"
                    )));
                }
            }
            combined.platforms.append(&mut source.platforms);
            combined.claims.append(&mut source.claims);
            combined.observed_items += source.observed_items;
            for (tag, count) in source.languages {
                *combined.languages.entry(tag).or_insert(0) += count;
            }
            for (kind, count) in source.name_kinds {
                *combined.name_kinds.entry(kind).or_insert(0) += count;
            }
            combined
                .platform_row_counts
                .extend(source.platform_row_counts);
        }
        if combined.platforms.is_empty() || (selection == "all" && combined.platforms.len() != 53) {
            return Err(invalid(format!(
                "unknown or incomplete combined localized source platform: {selection}"
            )));
        }
        Ok(combined)
    }

    fn open_source(
        root: &Path,
        selection: &str,
        cohort: &str,
        allow_empty_selection: bool,
    ) -> Result<Self, CatalogError> {
        let (base, registered, expected_platforms) = match cohort {
            "baseline" => {
                let register: Register =
                    serde_json::from_slice(&fs::read(root.join("sources/wikidata-v1.json"))?)?;
                if register.schema_version != 1
                    || register.provider != "wikidata"
                    || register.provider_license != "CC0-1.0"
                    || register.platforms.len() != 16
                {
                    return Err(invalid(
                        "independent Wikidata platform source register mismatch",
                    ));
                }
                let scopes: Vec<_> = register.platforms.into_iter().map(|p| (p, None)).collect();
                (BASE, scopes, 16)
            }
            "expanded-v1" | "expanded-v2" => {
                let (base, first, last, expected) = if cohort == "expanded-v1" {
                    ("data/wikidata/expanded-localized-v1", 1, 4, 19)
                } else {
                    ("data/wikidata/expanded-localized-v2", 5, 7, 18)
                };
                let mut scopes = Vec::new();
                for version in first..=last {
                    let path = format!("sources/wikidata-platform-expansion-v{version}.json");
                    let register: ExpandedRegister =
                        serde_json::from_slice(&fs::read(root.join(&path))?)?;
                    if register.schema_version != 1
                        || register.kind != "independent-wikidata-platform-expansion"
                        || register.source != "Wikidata"
                        || register.license != "CC0-1.0"
                        || register.query_limit != 20_000
                        || register.platforms.is_empty()
                    {
                        return Err(invalid(format!(
                            "expanded localized platform source register mismatch: {path}"
                        )));
                    }
                    scopes.extend(
                        register
                            .platforms
                            .into_iter()
                            .map(|p| (p, Some(path.clone()))),
                    );
                }
                if scopes.len() != expected {
                    return Err(invalid("expanded localized source platform count mismatch"));
                }
                (base, scopes, expected)
            }
            _ => return Err(invalid("unknown localized source cohort")),
        };
        let mut seen = HashSet::new();
        let mut claims = Vec::new();
        let mut platforms = Vec::new();
        let mut observed_items = 0;
        let mut languages = BTreeMap::new();
        let mut name_kinds = BTreeMap::new();
        let mut platform_row_counts = BTreeMap::new();
        for (platform, register_path) in &registered {
            if !seen.insert(&platform.platform)
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
                return Err(invalid(
                    "duplicate or invalid Wikidata platform registration",
                ));
            }
            if selection != "all" && selection != platform.platform {
                continue;
            }
            let dir = root.join(base).join(&platform.platform);
            if fs::symlink_metadata(&dir)?.file_type().is_symlink() {
                return Err(invalid("Wikidata localized source directory is a symlink"));
            }
            let manifest: Manifest = serde_json::from_slice(&fs::read(dir.join("manifest.json"))?)?;
            if manifest.schema_version != 1
                || manifest.source != "Wikidata"
                || manifest.license != "CC0-1.0"
                || manifest.source_revision != "live-query-capture"
                || manifest.source_register.as_deref() != register_path.as_deref()
                || manifest.platform != platform.platform
                || manifest.wikidata_platform != platform.wikidata_platform
                || manifest.captured_at_utc.is_empty()
                || manifest.source_query_path != "query.rq"
                || manifest.source_response_path != "response.json"
                || manifest.source_bindings_path != "bindings.jsonl"
                || manifest.query_limit != 50_000
                || (cohort == "baseline" && manifest.source_rows == 0)
                || manifest.source_rows >= manifest.query_limit
                || (manifest.source_rows == 0) != (manifest.distinct_items == 0)
                || manifest.language_prefix_scope != PREFIXES.map(str::to_owned)
            {
                return Err(invalid(format!(
                    "invalid source-localized title manifest: {}",
                    platform.platform
                )));
            }
            let query = verified_file(
                &dir,
                "query.rq",
                manifest.source_query_bytes,
                &manifest.source_query_sha256,
            )?;
            let original_query = std::str::from_utf8(&query)
                .map_err(|_| invalid("non-UTF-8 Wikidata localized query"))?;
            if !original_query.contains(&format!("wd:{}", platform.wikidata_platform))
                || !original_query.contains("rdfs:label skos:altLabel")
                || !original_query.contains("SELECT DISTINCT ?item ?predicate ?label")
                || !original_query.contains("LIMIT 50000")
            {
                return Err(invalid("localized SPARQL source scope mismatch"));
            }
            let response = verified_file(
                &dir,
                "response.json",
                manifest.source_response_bytes,
                &manifest.source_response_sha256,
            )?;
            let original: Value = serde_json::from_slice(&response)?;
            if original["head"]["vars"] != json!(["item", "predicate", "label"]) {
                return Err(invalid("unexpected localized source response columns"));
            }
            let bindings = original["results"]["bindings"]
                .as_array()
                .ok_or_else(|| invalid("missing localized source response rows"))?;
            if bindings.len() != manifest.source_rows {
                return Err(invalid(
                    "localized source manifest/response row count mismatch",
                ));
            }
            let text = verified_file(
                &dir,
                "bindings.jsonl",
                manifest.source_bindings_bytes,
                &manifest.source_bindings_sha256,
            )?;
            let raw = std::str::from_utf8(&text)
                .map_err(|_| invalid("non-UTF-8 original localized JSONL"))?;
            let lines: Vec<_> = raw.lines().collect();
            if (manifest.source_rows > 0 && !raw.ends_with('\n'))
                || lines.len() != manifest.source_rows
            {
                return Err(invalid("localized source JSONL row count mismatch"));
            }
            let mut item_ids = HashSet::new();
            let mut locale_counts: BTreeMap<String, usize> = BTreeMap::new();
            let mut kind_counts: BTreeMap<String, usize> = BTreeMap::new();
            for (index, line) in lines.iter().enumerate() {
                let original_row: Value = serde_json::from_str(line)?;
                if original_row != bindings[index] {
                    return Err(invalid(
                        "original localized JSONL and SPARQL response differ",
                    ));
                }
                let (item, kind, lang, name) = parse_original(&original_row)?;
                item_ids.insert(item.to_owned());
                *locale_counts.entry(lang.to_owned()).or_insert(0) += 1;
                *kind_counts.entry(kind.to_owned()).or_insert(0) += 1;
                claims.push(LocalizedTitleClaim {
                    platform: platform.platform.clone(),
                    item_qid: item.to_owned(),
                    language_tag: lang.to_owned(),
                    name: name.to_owned(),
                    name_kind: kind,
                    original_binding: original_row,
                    source_ordinal: index + 1,
                    source_path: format!("{base}/{}/bindings.jsonl", platform.platform),
                    source_sha256: manifest.source_bindings_sha256.clone(),
                    source_response_sha256: manifest.source_response_sha256.clone(),
                    source_query_sha256: manifest.source_query_sha256.clone(),
                    captured_at_utc: manifest.captured_at_utc.clone(),
                    interpretation:
                        "independent-language-tagged-name-not-a-verified-regional-game-title",
                });
            }
            if item_ids.len() != manifest.distinct_items
                || kind_counts != manifest.predicate_counts
                || locale_counts != manifest.language_tag_counts
            {
                return Err(invalid(
                    "original localized item, language or name-kind counts mismatch",
                ));
            }
            for (kind, n) in kind_counts {
                *name_kinds.entry(kind).or_insert(0) += n;
            }
            for (tag, n) in locale_counts {
                *languages.entry(tag).or_insert(0) += n;
            }
            platform_row_counts.insert(platform.platform.clone(), manifest.source_rows);
            platforms.push(platform.platform.clone());
            observed_items += manifest.distinct_items;
        }
        if (!allow_empty_selection && platforms.is_empty())
            || (selection == "all" && platforms.len() != expected_platforms)
        {
            return Err(invalid(format!(
                "unknown or incomplete localized source platform: {selection}"
            )));
        }
        Ok(Self {
            claims,
            platforms,
            observed_items,
            languages,
            name_kinds,
            platform_row_counts,
        })
    }

    pub fn claims(&self) -> &[LocalizedTitleClaim] {
        &self.claims
    }
    pub fn platform_ids(&self) -> &[String] {
        &self.platforms
    }
    pub fn total_claims(&self) -> usize {
        self.claims.len()
    }
    pub fn source_item_observations(&self) -> usize {
        self.observed_items
    }
    pub fn languages(&self) -> &BTreeMap<String, usize> {
        &self.languages
    }
    pub fn name_kinds(&self) -> &BTreeMap<String, usize> {
        &self.name_kinds
    }
    pub fn platform_row_counts(&self) -> &BTreeMap<String, usize> {
        &self.platform_row_counts
    }
    pub fn search(
        &self,
        qid: Option<&str>,
        title: Option<&str>,
        language: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&LocalizedTitleClaim>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid.is_some_and(|value| {
                qid_uri(&format!("http://www.wikidata.org/entity/{value}")).is_none()
            })
            || title.is_some_and(|value| value.trim().is_empty())
            || language.is_some_and(|value| !accepted_language(value))
            || (qid.is_some() && title.is_some())
        {
            return Err(invalid("localized name search requires valid QID, nonblank title, permitted language scope and limit 1..=200"));
        }
        let needle = title.map(str::to_lowercase);
        let lang = language.map(str::to_ascii_lowercase);
        let mut total = 0;
        let mut matches = Vec::new();
        for claim in &self.claims {
            if qid.is_some_and(|value| claim.item_qid != value)
                || needle
                    .as_ref()
                    .is_some_and(|value| !claim.name.to_lowercase().contains(value))
                || lang.as_ref().is_some_and(|value| {
                    let tag = claim.language_tag.to_ascii_lowercase();
                    tag != *value && !tag.starts_with(&format!("{value}-"))
                })
            {
                continue;
            }
            total += 1;
            if matches.len() < limit {
                matches.push(claim);
            }
        }
        Ok((total, matches))
    }
}

#[cfg(test)]
mod tests {
    use super::{accepted_language, WikidataLocalizedTitleCatalog};
    use std::path::Path;

    #[test]
    fn only_accepts_selected_language_subtags() {
        assert!(accepted_language("es-419"));
        assert!(accepted_language("zh-hant"));
        assert!(accepted_language("ja"));
        assert!(!accepted_language("not-a-language"));
        assert!(!accepted_language(""));
    }

    #[test]
    fn validates_all_original_localized_source_responses() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let source = WikidataLocalizedTitleCatalog::open(&root, "all").unwrap();
        assert_eq!(source.platform_ids().len(), 16);
        assert_eq!(source.total_claims(), 124_690);
        assert_eq!(source.source_item_observations(), 15_731);
        assert_eq!(source.name_kinds()["label"], 81_593);
        assert_eq!(source.name_kinds()["altLabel"], 43_097);
        assert_eq!(source.languages().values().sum::<usize>(), 124_690);
        let (total, matches) = source.search(None, None, Some("es"), 2).unwrap();
        assert!(total > 10_000);
        assert_eq!(matches.len(), 2);
        let (count, sample) = source.search(None, Some("Mario"), Some("ja"), 3).unwrap();
        assert!(count > 0);
        assert!(sample.iter().all(|row| row.source_sha256.len() == 64));
        assert!(WikidataLocalizedTitleCatalog::open(&root, "unknown").is_err());
        let expanded = WikidataLocalizedTitleCatalog::open_expanded(&root, "all").unwrap();
        assert_eq!(expanded.platform_ids().len(), 19);
        assert!(expanded.total_claims() > 0);
        assert_eq!(
            expanded.platform_row_counts().values().sum::<usize>(),
            expanded.total_claims()
        );
        let second = WikidataLocalizedTitleCatalog::open_expanded_v2(&root, "all").unwrap();
        assert_eq!(second.platform_ids().len(), 18);
        assert!(second.total_claims() > 0);
        assert_eq!(second.platform_row_counts()["gameparkgp32"], 0);
        assert_eq!(second.platform_row_counts()["tigergamecom"], 0);
        assert_eq!(second.platform_row_counts()["gg"], 1444);
        assert!(WikidataLocalizedTitleCatalog::open_expanded_v2(&root, "invalid").is_err());
        let combined = WikidataLocalizedTitleCatalog::open_combined(&root, "all").unwrap();
        assert_eq!(combined.platform_ids().len(), 53);
        assert_eq!(combined.total_claims(), 153_951);
        assert_eq!(
            combined.total_claims(),
            combined.platform_row_counts().values().sum()
        );
        assert_eq!(
            combined.source_item_observations(),
            15_731 + expanded.source_item_observations() + second.source_item_observations()
        );
        assert_eq!(combined.platform_row_counts()["gameparkgp32"], 0);
        assert_eq!(combined.platform_row_counts()["atari2600"], 1_856);
        assert!(WikidataLocalizedTitleCatalog::open_combined(&root, "unknown").is_err());
        let scoped = WikidataLocalizedTitleCatalog::open_combined(&root, "gg").unwrap();
        assert_eq!(scoped.platform_ids(), &["gg".to_owned()]);
        assert_eq!(scoped.total_claims(), 1_444);
    }
}
