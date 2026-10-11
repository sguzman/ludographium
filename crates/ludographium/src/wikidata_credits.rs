//! Review-only cross-provider developer and publisher name evidence.
//! Equal names support an observation candidate, never authenticate a game,
//! release, credit, company or publisher identity.
use crate::original_dat::{OriginalCreditEvidence, OriginalDatCatalog};
use crate::wikidata_candidates::WikidataCandidateCatalog;
use crate::wikidata_entity_labels::WikidataEntityLabelCatalog;
use crate::wikidata_properties::WikidataPropertyCatalog;
use crate::CatalogError;
use serde::Serialize;
use std::collections::{BTreeMap, HashMap, HashSet};

#[derive(Debug, Clone, Serialize)]
pub struct WikidataCreditEvidence {
    pub source_ordinal: usize,
    pub value_qid: Option<String>,
    pub english_label: Option<String>,
    pub raw_value: String,
    pub source_path: String,
    pub source_sha256: String,
    pub source_label_path: Option<String>,
    pub source_label_sha256: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct CreditComparison {
    pub platform: String,
    pub source_ordinal: usize,
    pub source_title: String,
    pub source_blob_sha: String,
    pub wikidata_item_qid: String,
    pub credit_type: &'static str,
    pub wikidata_property: &'static str,
    pub title_candidate_status: &'static str,
    pub credit_evidence_status: &'static str,
    pub libretro_claims: Vec<OriginalCreditEvidence>,
    pub wikidata_claims: Vec<WikidataCreditEvidence>,
    pub interpretation: &'static str,
}

pub struct WikidataCreditAudit {
    comparisons: Vec<CreditComparison>,
    counts: BTreeMap<String, BTreeMap<String, usize>>,
}

fn name_key(input: &str) -> String {
    input.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase()
}

fn compare_claims(
    source: &[OriginalCreditEvidence],
    wikidata: &[WikidataCreditEvidence],
) -> &'static str {
    if source.is_empty() && wikidata.is_empty() {
        return "both_sources_missing";
    }
    if source.is_empty() {
        return "libretro_credit_missing";
    }
    if wikidata.is_empty() {
        return "wikidata_credit_missing";
    }
    let originals: HashSet<String> = source.iter()
        .map(|claim| name_key(&claim.raw_value))
        .filter(|value| !value.is_empty())
        .collect();
    let names: HashSet<String> = wikidata.iter()
        .filter_map(|claim| claim.english_label.as_deref())
        .map(name_key)
        .filter(|value| !value.is_empty())
        .collect();
    if names.is_empty() {
        "wikidata_english_label_missing"
    } else if !originals.is_disjoint(&names) {
        "identical_observed_name"
    } else {
        "different_observed_names"
    }
}

impl WikidataCreditAudit {
    /// Both upstream providers remain separate. Cross-provider links are
    /// inherited from the title candidate review index, never promoted.
    pub fn build(
        original: &OriginalDatCatalog,
        properties: &WikidataPropertyCatalog,
        labels: &WikidataEntityLabelCatalog,
        candidates: &WikidataCandidateCatalog,
    ) -> Self {
        let source = original.reconciliation_credits();
        let mut index: HashMap<(String, String, String), Vec<WikidataCreditEvidence>> =
            HashMap::new();
        for entry in properties.claims() {
            if !matches!(entry.property.as_str(), "P123" | "P178") {
                continue;
            }
            let label = entry.value_qid.as_deref().and_then(|id| labels.lookup(id));
            index.entry((
                entry.platform.clone(),
                entry.item_qid.clone(),
                entry.property.clone(),
            )).or_default().push(WikidataCreditEvidence {
                source_ordinal: entry.source_ordinal,
                value_qid: entry.value_qid.clone(),
                english_label: label.and_then(|v| v.english_label.clone()),
                raw_value: entry.raw_binding["value"]["value"]
                    .as_str().unwrap_or_default().to_owned(),
                source_path: entry.source_path.clone(),
                source_sha256: entry.source_sha256.clone(),
                source_label_path: label.map(|v| v.source_path.clone()),
                source_label_sha256: label.map(|v| v.source_sha256.clone()),
            });
        }
        let mut counts: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
        let mut comparisons = Vec::new();
        for candidate in candidates.candidates() {
            for (credit, property) in [("developer", "P178"), ("publisher", "P123")] {
                let libretro_claims = source
                    .get(&(candidate.platform.clone(), candidate.source_ordinal, credit.to_owned()))
                    .cloned()
                    .unwrap_or_default();
                let wikidata_claims = index
                    .get(&(candidate.platform.clone(), candidate.wikidata_qid.clone(), property.to_owned()))
                    .cloned()
                    .unwrap_or_default();
                let status = compare_claims(&libretro_claims, &wikidata_claims);
                *counts.entry(credit.to_owned()).or_default()
                    .entry(status.to_owned()).or_insert(0) += 1;
                comparisons.push(CreditComparison {
                    platform: candidate.platform.clone(),
                    source_ordinal: candidate.source_ordinal,
                    source_title: candidate.source_title.clone(),
                    source_blob_sha: candidate.source_blob_sha.clone(),
                    wikidata_item_qid: candidate.wikidata_qid.clone(),
                    credit_type: credit,
                    wikidata_property: property,
                    title_candidate_status: candidate.status,
                    credit_evidence_status: status,
                    libretro_claims,
                    wikidata_claims,
                    interpretation: "review-only-name-evidence-not-verified-game-or-company-identity",
                });
            }
        }
        Self { comparisons, counts }
    }

    pub fn counts(&self) -> &BTreeMap<String, BTreeMap<String, usize>> {
        &self.counts
    }

    /// Return a bounded review list without truncating whole-corpus counts.
    pub fn search(
        &self, title: Option<&str>, qid: Option<&str>, limit: usize
    ) -> Result<(usize, Vec<&CreditComparison>), CatalogError> {
        if !(1..=200).contains(&limit) || title.is_some_and(|t| t.trim().is_empty()) {
            return Err(CatalogError::Invalid(
                "credit evidence requires nonblank title and limit 1..=200".into(),
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut count = 0;
        let mut results = Vec::new();
        for comparison in &self.comparisons {
            if qid.is_some_and(|id| comparison.wikidata_item_qid != id)
                || needle.as_ref().is_some_and(|q| {
                    !comparison.source_title.to_lowercase().contains(q)
                })
            {
                continue;
            }
            count += 1;
            if results.len() < limit {
                results.push(comparison);
            }
        }
        Ok((count, results))
    }
}

#[cfg(test)]
mod tests {
    use super::{compare_claims, name_key, WikidataCreditAudit, WikidataCreditEvidence};
    use crate::original_dat::{OriginalCreditEvidence, OriginalDatCatalog};
    use crate::wikidata_candidates::WikidataCandidateCatalog;
    use crate::wikidata_entity_labels::WikidataEntityLabelCatalog;
    use crate::wikidata_properties::WikidataPropertyCatalog;
    use crate::wikidata_text::WikidataTextCatalog;
    use std::path::Path;

    #[test]
    fn source_names_are_only_whitespace_and_case_normalized() {
        assert_eq!(name_key("HAL   Laboratory"), "hal laboratory");
        assert_eq!(name_key("Sega / Nintendo"), "sega / nintendo");
        let left = vec![OriginalCreditEvidence {
            raw_value: "  HAL   Laboratory  ".to_owned(),
            field: "developer".to_owned(),
            source_kind: "matched_bibliographic_dat",
            source_path: "example.dat".to_owned(),
            source_blob_sha: "example".to_owned(),
            source_ordinal: 1,
        }];
        let right = vec![WikidataCreditEvidence {
            source_ordinal: 1,
            value_qid: Some("Q123".to_owned()),
            english_label: Some("hal laboratory".to_owned()),
            raw_value: "http://www.wikidata.org/entity/Q123".to_owned(),
            source_path: "sample.jsonl".to_owned(),
            source_sha256: "fixture".to_owned(),
            source_label_path: None,
            source_label_sha256: None,
        }];
        assert_eq!(compare_claims(&left, &right), "identical_observed_name");
        assert_eq!(compare_claims(&left, &[]), "wikidata_credit_missing");
        assert_eq!(compare_claims(&[], &right), "libretro_credit_missing");
    }

    #[test]
    fn compares_all_review_candidates_without_assigning_credit_identities() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let original = OriginalDatCatalog::open(&root, "all")
            .unwrap().with_enrichment(&root).unwrap();
        let wiki = WikidataTextCatalog::open(&root, "all").unwrap();
        let properties = WikidataPropertyCatalog::open(&root, "all").unwrap();
        let labels = WikidataEntityLabelCatalog::open(&root).unwrap();
        labels.verify_referenced_qids(&properties).unwrap();
        let candidates = WikidataCandidateCatalog::reconcile(&original, &wiki);
        let audit = WikidataCreditAudit::build(&original, &properties, &labels, &candidates);
        assert_eq!(candidates.summary().total_candidate_links, 8971);
        for credit in ["developer", "publisher"] {
            assert_eq!(audit.counts()[credit].values().sum::<usize>(), 8971);
        }
        let (total, sample) = audit.search(None, None, 2).unwrap();
        assert_eq!(total, 2 * 8971);
        assert_eq!(sample.len(), 2);
        assert!(sample.iter().all(|entry| {
            entry.interpretation.contains("review-only")
                && entry.title_candidate_status != ""
        }));
    }
}
