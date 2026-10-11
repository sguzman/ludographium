//! QID-scoped, read-only projection across three independently pinned
//! Wikidata source accessions. This is not a Libretro or canonical work join.
use crate::wikidata_entity_labels::WikidataEntityLabelCatalog;
use crate::wikidata_localized_titles::WikidataLocalizedTitleCatalog;
use crate::wikidata_properties::WikidataPropertyCatalog;
use crate::wikidata_relations::WikidataRelationCatalog;
use crate::wikidata_text::WikidataTextCatalog;
use crate::CatalogError;
use serde::Serialize;
use serde_json::{json, Value};
use std::collections::BTreeMap;

#[derive(Debug, Serialize)]
pub struct WikidataSourceItem {
    pub platform: String,
    pub qid: String,
    pub english_label: Option<String>,
    pub source_presence: &'static str,
    pub original_title_date_observation: Option<Value>,
    pub property_claims: BTreeMap<String, Vec<Value>>,
    pub relation_claims: BTreeMap<String, Vec<Value>>,
    pub relation_source_present: bool,
    pub localized_names: BTreeMap<String, Vec<Value>>,
    pub localized_source_present: bool,
    pub interpretation: &'static str,
}

pub struct WikidataItemProjection {
    entries: Vec<WikidataSourceItem>,
    original_item_observations: usize,
    property_item_observations: usize,
    relation_item_observations: usize,
    localized_item_observations: usize,
    relation_only: usize,
    localized_only: usize,
    relation_and_localized_only: usize,
    only_title_date: usize,
    only_properties: usize,
}

fn valid_qid(value: &str) -> bool {
    value.strip_prefix('Q').is_some_and(|digits| {
        !digits.is_empty() && !digits.starts_with('0') && digits.bytes().all(|b| b.is_ascii_digit())
    })
}

impl WikidataItemProjection {
    /// Merge by *exact* platform and stable Wikidata QID only. Preserve the
    /// originating title/date and property accessions as independent evidence,
    /// including records present in only one of the two capture periods.
    pub fn build(
        text: &WikidataTextCatalog,
        properties: &WikidataPropertyCatalog,
        labels: &WikidataEntityLabelCatalog,
        relations: &WikidataRelationCatalog,
        relation_labels: &WikidataEntityLabelCatalog,
        localized: &WikidataLocalizedTitleCatalog,
    ) -> Result<Self, CatalogError> {
        let mut index: BTreeMap<(String, String), WikidataSourceItem> = BTreeMap::new();
        let mut title_count = 0;
        for original in text.all_source_observations() {
            let platform = original["platform"]
                .as_str()
                .ok_or_else(|| {
                    CatalogError::Invalid("missing Wikidata text observation platform".into())
                })?
                .to_owned();
            let qid = original["qid"]
                .as_str()
                .ok_or_else(|| CatalogError::Invalid("missing original Wikidata QID".into()))?
                .to_owned();
            let label = original["english_label"].as_str().map(str::to_owned);
            let entry = index
                .entry((platform.clone(), qid.clone()))
                .or_insert_with(|| WikidataSourceItem {
                    platform,
                    qid,
                    english_label: None,
                    source_presence: "title_date_source_only",
                    original_title_date_observation: None,
                    property_claims: BTreeMap::new(),
                    relation_claims: BTreeMap::new(),
                    relation_source_present: false,
                    localized_names: BTreeMap::new(),
                    localized_source_present: false,
                    interpretation:
                        "independent-source-evidence-not-verified-game-or-release-identity",
                });
            if entry
                .original_title_date_observation
                .replace(original)
                .is_some()
            {
                return Err(CatalogError::Invalid(
                    "duplicate pinned Wikidata title/date source observation".into(),
                ));
            }
            entry.english_label = label;
            title_count += 1;
        }
        for claim in properties.claims() {
            let entry = index
                .entry((claim.platform.clone(), claim.item_qid.clone()))
                .or_insert_with(|| WikidataSourceItem {
                    platform: claim.platform.clone(),
                    qid: claim.item_qid.clone(),
                    english_label: None,
                    source_presence: "property_source_only",
                    original_title_date_observation: None,
                    property_claims: BTreeMap::new(),
                    relation_claims: BTreeMap::new(),
                    relation_source_present: false,
                    localized_names: BTreeMap::new(),
                    localized_source_present: false,
                    interpretation:
                        "independent-source-evidence-not-verified-game-or-release-identity",
                });
            let english_label_evidence =
                claim.value_qid.as_deref().and_then(|id| labels.lookup(id));
            let projected = json!({
                "original_property_claim": claim,
                "value_english_label_evidence": english_label_evidence
            });
            entry
                .property_claims
                .entry(claim.property.clone())
                .or_default()
                .push(projected);
        }
        for claim in relations.claims() {
            let entry = index
                .entry((claim.platform.clone(), claim.item_qid.clone()))
                .or_insert_with(|| WikidataSourceItem {
                    platform: claim.platform.clone(),
                    qid: claim.item_qid.clone(),
                    english_label: None,
                    source_presence: "relation_source_only",
                    original_title_date_observation: None,
                    property_claims: BTreeMap::new(),
                    relation_claims: BTreeMap::new(),
                    relation_source_present: false,
                    localized_names: BTreeMap::new(),
                    localized_source_present: false,
                    interpretation:
                        "independent-source-evidence-not-verified-game-or-release-identity",
                });
            entry.relation_source_present = true;
            entry
                .relation_claims
                .entry(claim.property.clone())
                .or_default()
                .push(json!({
                    "original_relation_claim": claim,
                    "value_english_label_evidence": claim.value_entity_qid.as_deref()
                        .and_then(|qid| relation_labels.lookup(qid))
                }));
        }
        for claim in localized.claims() {
            let entry = index
                .entry((claim.platform.clone(), claim.item_qid.clone()))
                .or_insert_with(|| WikidataSourceItem {
                    platform: claim.platform.clone(),
                    qid: claim.item_qid.clone(),
                    english_label: None,
                    source_presence: "localized_source_only",
                    original_title_date_observation: None,
                    property_claims: BTreeMap::new(),
                    relation_claims: BTreeMap::new(),
                    relation_source_present: false,
                    localized_names: BTreeMap::new(),
                    localized_source_present: false,
                    interpretation: "independent-source-evidence-not-verified-game-or-release-identity",
                });
            entry.localized_source_present = true;
            entry.localized_names.entry(claim.language_tag.clone())
                .or_default().push(json!({"original_localized_name": claim}));
        }
        let mut localized_only = 0;
        let mut relation_and_localized_only = 0;
        let mut localized_items = 0;
        let mut relation_only = 0;
        let mut relation_items = 0;
        let mut only_title_date = 0;
        let mut only_properties = 0;
        let mut property_items = 0;
        for entry in index.values_mut() {
            let old = entry.original_title_date_observation.is_some();
            let new = !entry.property_claims.is_empty();
            if entry.relation_source_present {
                relation_items += 1;
            }
            if entry.localized_source_present {
                localized_items += 1;
            }
            match (old, new) {
                (true, true) => entry.source_presence = "both_independent_snapshots",
                (true, false) => {
                    entry.source_presence = "title_date_source_only";
                    only_title_date += 1;
                }
                (false, true) => {
                    entry.source_presence = "property_source_only";
                    only_properties += 1;
                }
                (false, false) if entry.relation_source_present && entry.localized_source_present => {
                    entry.source_presence = "relation_and_localized_sources_only";
                    relation_and_localized_only += 1;
                }
                (false, false) if entry.relation_source_present => {
                    entry.source_presence = "relation_source_only";
                    relation_only += 1;
                }
                (false, false) if entry.localized_source_present => {
                    entry.source_presence = "localized_source_only";
                    localized_only += 1;
                }
                (false, false) => {
                    return Err(CatalogError::Invalid(
                        "Wikidata item has no source evidence".into(),
                    ))
                }
            }
            if new {
                property_items += 1;
            }
        }
        if title_count != text.item_count()
            || property_items != properties.source_item_observations()
            || relation_items != relations.item_observations()
            || localized_items != localized.source_item_observations()
        {
            return Err(CatalogError::Invalid(
                "Wikidata independent snapshots have inconsistent item/QID counts".into(),
            ));
        }
        Ok(Self {
            entries: index.into_values().collect(),
            original_item_observations: title_count,
            property_item_observations: property_items,
            relation_item_observations: relation_items,
            localized_item_observations: localized_items,
            relation_only,
            localized_only,
            relation_and_localized_only,
            only_title_date,
            only_properties,
        })
    }

    pub fn total_items(&self) -> usize {
        self.entries.len()
    }
    pub fn title_date_source_items(&self) -> usize {
        self.original_item_observations
    }
    pub fn property_source_items(&self) -> usize {
        self.property_item_observations
    }
    pub fn relation_source_items(&self) -> usize {
        self.relation_item_observations
    }
    pub fn localized_source_items(&self) -> usize {
        self.localized_item_observations
    }
    pub fn localized_only(&self) -> usize {
        self.localized_only
    }
    pub fn relation_and_localized_only(&self) -> usize {
        self.relation_and_localized_only
    }
    pub fn relation_only(&self) -> usize {
        self.relation_only
    }
    pub fn title_date_only(&self) -> usize {
        self.only_title_date
    }
    pub fn property_only(&self) -> usize {
        self.only_properties
    }
    pub fn search(
        &self,
        qid: Option<&str>,
        title: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&WikidataSourceItem>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid.is_some_and(|value| !valid_qid(value))
            || title.is_some_and(|value| value.trim().is_empty())
        {
            return Err(CatalogError::Invalid(
                "Wikidata item review requires valid QID, nonblank title and limit 1..=200".into(),
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut count = 0;
        let mut results = Vec::new();
        for entry in &self.entries {
            if qid.is_some_and(|key| entry.qid != key)
                || needle.as_ref().is_some_and(|key| {
                    let primary = entry.english_label.as_ref()
                        .is_some_and(|value| value.to_lowercase().contains(key));
                    let localized = entry.localized_names.values().flatten().any(|name| {
                        name["original_localized_name"]["name"].as_str()
                            .is_some_and(|value| value.to_lowercase().contains(key))
                    });
                    !primary && !localized
                })
            {
                continue;
            }
            count += 1;
            if results.len() < limit {
                results.push(entry);
            }
        }
        Ok((count, results))
    }
}

#[cfg(test)]
mod tests {
    use super::WikidataItemProjection;
    use crate::wikidata_entity_labels::WikidataEntityLabelCatalog;
    use crate::wikidata_localized_titles::WikidataLocalizedTitleCatalog;
    use crate::wikidata_properties::WikidataPropertyCatalog;
    use crate::wikidata_relations::WikidataRelationCatalog;
    use crate::wikidata_text::WikidataTextCatalog;
    use std::path::Path;

    #[test]
    fn preserves_both_snapshots_in_independent_item_projection() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let text = WikidataTextCatalog::open(&root, "all").unwrap();
        let properties = WikidataPropertyCatalog::open(&root, "all").unwrap();
        let labels = WikidataEntityLabelCatalog::open(&root).unwrap();
        let relations = WikidataRelationCatalog::open(&root, "all").unwrap();
        let relation_labels = WikidataEntityLabelCatalog::open_relations(&root).unwrap();
        let localized = WikidataLocalizedTitleCatalog::open(&root, "all").unwrap();
        relation_labels.verify_relation_qids(&relations).unwrap();
        labels.verify_referenced_qids(&properties).unwrap();
        let projection = WikidataItemProjection::build(
            &text,
            &properties,
            &labels,
            &relations,
            &relation_labels,
            &localized,
        )
        .unwrap();
        assert_eq!(projection.title_date_source_items(), 15_868);
        assert_eq!(projection.property_source_items(), 14_759);
        assert_eq!(projection.relation_source_items(), 14_772);
        assert_eq!(projection.localized_source_items(), 15_731);
        assert!(projection.total_items() >= 15_868);
        assert!(projection.total_items() >= 15_868);
        assert_eq!(
            projection.title_date_only()
                + projection.property_only()
                + (projection.total_items()
                    - projection.title_date_only()
                    - projection.property_only()),
            projection.total_items(),
        );
        let (count, records) = projection.search(Some("Q379915"), None, 10).unwrap();
        assert!(count > 0);
        assert!(records.iter().any(|entry| {
            entry.platform == "atari2600"
                && entry.original_title_date_observation.is_some()
                && entry.property_claims.contains_key("P178")
                && entry.relation_source_present
                && entry.localized_source_present
        }));
    }
}
