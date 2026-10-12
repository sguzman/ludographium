//! Same-platform localized-label and alternate-title equality candidates.
//! These are independent source claims, not work, region or release identities.
use crate::original_dat::OriginalDatCatalog;
use crate::wikidata_expanded_candidates::ExpandedTitleCandidateCatalog;
use crate::wikidata_candidates::{title_key, WikidataCandidateCatalog};
use crate::wikidata_localized_titles::WikidataLocalizedTitleCatalog;
use crate::CatalogError;
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet, HashSet};

#[derive(Clone, Debug, Serialize)]
pub struct LocalizedTitleEvidence {
    pub name: String,
    pub language_tag: String,
    pub name_kind: &'static str,
    pub source_ordinal: usize,
    pub source_path: String,
    pub source_sha256: String,
    pub source_response_sha256: String,
    pub source_query_sha256: String,
}

#[derive(Debug, Serialize)]
pub struct LocalizedTitleCandidate {
    pub platform: String,
    pub original_source_ordinal: usize,
    pub original_source_title: String,
    pub original_source_path: String,
    pub original_source_blob_sha: String,
    pub wikidata_item_qid: String,
    pub normalized_title_key: String,
    pub localized_name_evidence: Vec<LocalizedTitleEvidence>,
    pub competing_wikidata_qids: usize,
    pub already_present_in_english_label_candidates: bool,
    pub status: &'static str,
    pub interpretation: &'static str,
}

pub struct WikidataLocalizedCandidateCatalog {
    pairs: Vec<LocalizedTitleCandidate>,
    scope: Vec<String>,
    source_records_with_matches: usize,
    ambiguous_links: usize,
    new_pairs_outside_english: usize,
    evidence_by_language: BTreeMap<String, usize>,
}

#[derive(Debug, Serialize)]
pub struct LocalizedCandidateSummary<'a> {
    pub platforms_searched: &'a [String],
    pub total_candidate_pairs: usize,
    pub original_records_with_candidates: usize,
    pub ambiguous_candidate_pairs: usize,
    pub candidate_pairs_absent_from_english_title_match: usize,
    pub contributing_original_name_claims_by_language: &'a BTreeMap<String, usize>,
    pub interpretation: &'static str,
}

impl WikidataLocalizedCandidateCatalog {
    /// Match only exact normalized original labels/aliases within the same
    /// platform; group all source label assertions for one item QID together.
    /// Never convert candidates into canonical work or release identifiers.
    pub fn reconcile(
        base: &OriginalDatCatalog,
        localized: &WikidataLocalizedTitleCatalog,
        english: &WikidataCandidateCatalog,
    ) -> Self {
        Self::reconcile_with_expanded(base, localized, english, &[])
    }

    /// Include the independent expanded English-label candidates when judging
    /// whether exact multilingual source matches are genuinely new.
    pub fn reconcile_with_expanded(
        base: &OriginalDatCatalog,
        localized: &WikidataLocalizedTitleCatalog,
        english: &WikidataCandidateCatalog,
        expanded: &[ExpandedTitleCandidateCatalog],
    ) -> Self {
        let scope = localized.platform_ids().to_vec();
        let permitted: HashSet<&str> = scope.iter().map(String::as_str).collect();
        let mut known_english: HashSet<(String, usize, String)> = english
            .candidates()
            .iter()
            .map(|candidate| {
                (
                    candidate.platform.clone(),
                    candidate.source_ordinal,
                    candidate.wikidata_qid.clone(),
                )
            })
            .collect();
        for source in expanded {
            for candidate in source.candidates() {
                known_english.insert((
                    candidate.platform.clone(),
                    candidate.libretro_source_ordinal,
                    candidate.wikidata_item_qid.clone(),
                ));
            }
        }
        let mut source_by_key: BTreeMap<
            (String, String),
            BTreeMap<String, Vec<LocalizedTitleEvidence>>,
        > = BTreeMap::new();
        for claim in localized.claims() {
            let normalized = title_key(&claim.name);
            if normalized.is_empty() {
                continue;
            }
            source_by_key
                .entry((claim.platform.clone(), normalized))
                .or_default()
                .entry(claim.item_qid.clone())
                .or_default()
                .push(LocalizedTitleEvidence {
                    name: claim.name.clone(),
                    language_tag: claim.language_tag.clone(),
                    name_kind: claim.name_kind,
                    source_ordinal: claim.source_ordinal,
                    source_path: claim.source_path.clone(),
                    source_sha256: claim.source_sha256.clone(),
                    source_response_sha256: claim.source_response_sha256.clone(),
                    source_query_sha256: claim.source_query_sha256.clone(),
                });
        }
        let mut pairs = Vec::new();
        let mut source_records_with_matches = 0;
        let mut ambiguous_links = 0;
        let mut new_pairs_outside_english = 0;
        let mut evidence_by_language = BTreeMap::new();
        for (platform, source_ordinal, title, source_path, source_sha) in
            base.reconciliation_titles()
        {
            if !permitted.contains(platform) {
                continue;
            }
            let normalized = title_key(title);
            let Some(items) = source_by_key.get(&(platform.to_owned(), normalized.clone())) else {
                continue;
            };
            source_records_with_matches += 1;
            let ambiguous = items.len() > 1;
            for (qid, evidence) in items {
                let originally_english =
                    known_english.contains(&(platform.to_owned(), source_ordinal, qid.clone()));
                if !originally_english {
                    new_pairs_outside_english += 1;
                }
                if ambiguous {
                    ambiguous_links += 1;
                }
                let distinct_names: BTreeSet<(String, usize)> = evidence
                    .iter()
                    .map(|claim| (claim.source_path.clone(), claim.source_ordinal))
                    .collect();
                debug_assert_eq!(distinct_names.len(), evidence.len());
                for original in evidence {
                    *evidence_by_language
                        .entry(original.language_tag.clone())
                        .or_insert(0) += 1;
                }
                pairs.push(LocalizedTitleCandidate {
                    platform: platform.to_owned(),
                    original_source_ordinal: source_ordinal,
                    original_source_title: title.to_owned(),
                    original_source_path: source_path.to_owned(),
                    original_source_blob_sha: source_sha.to_owned(),
                    wikidata_item_qid: qid.clone(),
                    normalized_title_key: normalized.clone(),
                    localized_name_evidence: evidence.clone(),
                    competing_wikidata_qids: items.len(),
                    already_present_in_english_label_candidates: originally_english,
                    status: if ambiguous {
                        "ambiguous_localized_title_candidate"
                    } else {
                        "single_qid_localized_title_candidate"
                    },
                    interpretation: "review-only-exact-title-evidence-not-verified-game-localization-or-release-identity",
                });
            }
        }
        Self {
            pairs,
            scope,
            source_records_with_matches,
            ambiguous_links,
            new_pairs_outside_english,
            evidence_by_language,
        }
    }

    pub fn summary(&self) -> LocalizedCandidateSummary<'_> {
        LocalizedCandidateSummary {
            platforms_searched: &self.scope,
            total_candidate_pairs: self.pairs.len(),
            original_records_with_candidates: self.source_records_with_matches,
            ambiguous_candidate_pairs: self.ambiguous_links,
            candidate_pairs_absent_from_english_title_match: self.new_pairs_outside_english,
            contributing_original_name_claims_by_language: &self.evidence_by_language,
            interpretation:
                "source-label-equivalence-is-not-canonical-work-edition-or-locale-evidence",
        }
    }

    pub fn search(
        &self,
        title: Option<&str>,
        qid: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&LocalizedTitleCandidate>), CatalogError> {
        if !(1..=200).contains(&limit)
            || title.is_some_and(|value| value.trim().is_empty())
            || qid.is_some_and(|value| {
                !value.strip_prefix('Q').is_some_and(|digits| {
                    !digits.is_empty()
                        && !digits.starts_with('0')
                        && digits.bytes().all(|b| b.is_ascii_digit())
                })
            })
        {
            return Err(CatalogError::Invalid(
                "localized candidate review requires valid QID, nonblank title and limit 1..=200"
                    .into(),
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut total = 0;
        let mut results = Vec::new();
        for candidate in &self.pairs {
            if qid.is_some_and(|value| candidate.wikidata_item_qid != value)
                || needle.as_ref().is_some_and(|value| {
                    !candidate
                        .original_source_title
                        .to_lowercase()
                        .contains(value)
                })
            {
                continue;
            }
            total += 1;
            if results.len() < limit {
                results.push(candidate);
            }
        }
        Ok((total, results))
    }
}

#[cfg(test)]
mod tests {
    use super::WikidataLocalizedCandidateCatalog;
    use crate::original_dat::OriginalDatCatalog;
    use crate::wikidata_candidates::WikidataCandidateCatalog;
    use crate::wikidata_localized_titles::WikidataLocalizedTitleCatalog;
    use crate::wikidata_text::WikidataTextCatalog;
    use std::path::Path;

    #[test]
    fn original_multilingual_names_remain_noncanonical_title_review_evidence() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let source = OriginalDatCatalog::open(&root, "all").unwrap();
        let original_english = WikidataTextCatalog::open(&root, "all").unwrap();
        let english = WikidataCandidateCatalog::reconcile(&source, &original_english);
        let localized = WikidataLocalizedTitleCatalog::open(&root, "all").unwrap();
        let audit = WikidataLocalizedCandidateCatalog::reconcile(&source, &localized, &english);
        let summary = audit.summary();
        assert_eq!(summary.platforms_searched.len(), 16);
        assert!(summary.total_candidate_pairs > 0);
        assert!(summary.original_records_with_candidates > 0);
        assert!(summary.contributing_original_name_claims_by_language.len() > 4);
        assert!(summary.candidate_pairs_absent_from_english_title_match > 0);
        let (total, rows) = audit.search(Some("Adventure"), Some("Q379915"), 5).unwrap();
        assert!(total > 0);
        assert!(rows.iter().all(|record| {
            record.platform == "atari2600"
                && record.original_source_blob_sha.len() == 40
                && record
                    .localized_name_evidence
                    .iter()
                    .all(|name| name.source_sha256.len() == 64 && !name.language_tag.is_empty())
                && record.interpretation.contains("review-only")
        }));
        let (matches, limited) = audit.search(None, None, 1).unwrap();
        assert_eq!(matches, summary.total_candidate_pairs);
        assert_eq!(limited.len(), 1);
        assert!(audit.search(None, Some("Q0"), 3).is_err());
    }
}
