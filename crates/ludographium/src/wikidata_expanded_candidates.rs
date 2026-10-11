//! Noncanonical, same-platform Libretro/Wikidata title correspondences for
//! the three additional source partitions. Never infer work/release identity.
use crate::original_dat::OriginalDatCatalog;
use crate::wikidata_candidates::title_key;
use crate::wikidata_platform_expansion::ExpandedWikidataCatalog;
use crate::CatalogError;
use serde::Serialize;
use std::collections::{BTreeMap, HashSet};

#[derive(Debug, Serialize)]
pub struct ExpandedTitleCandidate {
    pub platform: String,
    pub libretro_source_ordinal: usize,
    pub libretro_source_title: String,
    pub libretro_source_path: String,
    pub libretro_source_blob_sha: String,
    pub wikidata_item_qid: String,
    pub wikidata_english_label: String,
    pub wikidata_source_path: String,
    pub wikidata_source_sha256: String,
    pub wikidata_title_row_ordinals: Vec<usize>,
    pub conservative_title_key: String,
    pub competing_item_qids: usize,
    pub status: &'static str,
    pub interpretation: &'static str,
}

pub struct ExpandedTitleCandidateCatalog {
    links: Vec<ExpandedTitleCandidate>,
    platform_ids: Vec<String>,
    source_records_with_candidate: usize,
    ambiguous_candidate_links: usize,
}

fn qid(value: &str) -> bool {
    value.strip_prefix('Q').is_some_and(|digits| {
        !digits.is_empty() && !digits.starts_with('0') && digits.bytes().all(|b| b.is_ascii_digit())
    })
}

impl ExpandedTitleCandidateCatalog {
    pub fn reconcile(base: &OriginalDatCatalog, wikidata: &ExpandedWikidataCatalog) -> Self {
        type LabelProvenance = (String, String, String, Vec<usize>);
        let mut labels: BTreeMap<(String, String), BTreeMap<String, LabelProvenance>> =
            BTreeMap::new();
        for item in wikidata.observations() {
            let Some(label) = item.english_label.as_deref() else {
                continue;
            };
            let key = title_key(label);
            if key.is_empty() {
                continue;
            }
            let entry = labels
                .entry((item.platform.clone(), key))
                .or_default()
                .entry(item.item_qid.clone())
                .or_insert_with(|| {
                    (
                        label.to_owned(),
                        item.source_path.clone(),
                        item.source_sha256.clone(),
                        Vec::new(),
                    )
                });
            entry.3.push(item.source_ordinal);
        }
        let mut links = Vec::new();
        let wanted: HashSet<&str> = wikidata.platforms().iter().map(String::as_str).collect();
        let mut ambiguous_candidate_links = 0;
        let mut source_records_with_candidate = 0;
        for (platform, ordinal, title, path, sha) in base.reconciliation_titles() {
            if !wanted.contains(platform) {
                continue;
            }
            let key = title_key(title);
            let Some(group) = labels.get(&(platform.to_owned(), key.clone())) else {
                continue;
            };
            source_records_with_candidate += 1;
            for (qid, (label, source_path, source_sha, row_ordinals)) in group {
                let ambiguous = group.len() > 1;
                if ambiguous {
                    ambiguous_candidate_links += 1;
                }
                links.push(ExpandedTitleCandidate {
                    platform: platform.to_owned(),
                    libretro_source_ordinal: ordinal,
                    libretro_source_title: title.to_owned(),
                    libretro_source_path: path.to_owned(),
                    libretro_source_blob_sha: sha.to_owned(),
                    wikidata_item_qid: qid.clone(),
                    wikidata_english_label: label.clone(),
                    wikidata_source_path: source_path.clone(),
                    wikidata_source_sha256: source_sha.clone(),
                    wikidata_title_row_ordinals: row_ordinals.clone(),
                    conservative_title_key: key.clone(),
                    competing_item_qids: group.len(),
                    status: if ambiguous {
                        "ambiguous_wikidata_title"
                    } else {
                        "same_platform_title_candidate"
                    },
                    interpretation:
                        "noncanonical-title-review-evidence-not-verified-game-or-release-identity",
                });
            }
        }
        Self {
            links,
            platform_ids: wikidata.platforms().to_vec(),
            source_records_with_candidate,
            ambiguous_candidate_links,
        }
    }

    pub fn platforms(&self) -> &[String] {
        &self.platform_ids
    }
    pub fn total_links(&self) -> usize {
        self.links.len()
    }
    pub fn source_records_with_candidate(&self) -> usize {
        self.source_records_with_candidate
    }
    pub fn ambiguous_links(&self) -> usize {
        self.ambiguous_candidate_links
    }
    pub fn search(
        &self,
        qid_filter: Option<&str>,
        title: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&ExpandedTitleCandidate>), CatalogError> {
        if !(1..=200).contains(&limit)
            || qid_filter.is_some_and(|name| !qid(name))
            || title.is_some_and(|text| text.trim().is_empty())
        {
            return Err(CatalogError::Invalid(
                "Require valid QID, nonblank source title and limit 1..=200".into(),
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut count = 0;
        let mut results = Vec::new();
        for link in &self.links {
            if qid_filter.is_some_and(|name| link.wikidata_item_qid != name)
                || needle
                    .as_ref()
                    .is_some_and(|text| !link.libretro_source_title.to_lowercase().contains(text))
            {
                continue;
            }
            count += 1;
            if results.len() < limit {
                results.push(link);
            }
        }
        Ok((count, results))
    }
}

#[cfg(test)]
mod tests {
    use super::ExpandedTitleCandidateCatalog;
    use crate::original_dat::OriginalDatCatalog;
    use crate::wikidata_platform_expansion::ExpandedWikidataCatalog;
    use std::path::Path;

    #[test]
    fn v6_corpus_wide_title_review_retains_empty_source_noncoverage() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let original = OriginalDatCatalog::open(&root, "all").unwrap();
        let wikidata = ExpandedWikidataCatalog::open_v6(&root, "all").unwrap();
        let review = ExpandedTitleCandidateCatalog::reconcile(&original, &wikidata);
        assert_eq!(review.platforms().len(), 6);
        let (total, sample) = review.search(None, None, 1).unwrap();
        assert_eq!(total, review.total_links());
        assert_eq!(sample.len(), total.min(1));
        if let Some(first) = sample.first() {
            assert!(first.wikidata_source_path.contains("platform-expansion-v6"));
            assert!(first.interpretation.contains("noncanonical"));
            assert!(!first.wikidata_title_row_ordinals.is_empty());
        }

        let zero_source = ExpandedWikidataCatalog::open_v6(&root, "tigergamecom").unwrap();
        let zero_review = ExpandedTitleCandidateCatalog::reconcile(&original, &zero_source);
        assert_eq!(zero_review.platforms(), &["tigergamecom".to_string()]);
        assert_eq!(zero_review.total_links(), 0);
        assert_eq!(zero_review.source_records_with_candidate(), 0);
        assert_eq!(zero_review.ambiguous_links(), 0);
    }

    #[test]
    fn new_source_title_candidates_do_not_merge_distinct_editions_or_dates() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let original = OriginalDatCatalog::open(&root, "all").unwrap();
        let wikidata = ExpandedWikidataCatalog::open(&root, "all").unwrap();
        let matches = ExpandedTitleCandidateCatalog::reconcile(&original, &wikidata);
        assert_eq!(matches.platforms().len(), 3);
        assert!(matches.total_links() > 0);
        assert!(matches.source_records_with_candidate() > 0);
        let (total, rows) = matches.search(None, None, 2).unwrap();
        assert_eq!(total, matches.total_links());
        assert_eq!(rows.len(), 2);
        assert!(rows.iter().all(|row| {
            !row.wikidata_title_row_ordinals.is_empty()
                && row.wikidata_source_sha256.len() == 64
                && row.libretro_source_blob_sha.len() == 40
                && row.interpretation.contains("not-verified")
        }));
        assert!(matches.search(Some("Q0"), None, 3).is_err());
    }
}
