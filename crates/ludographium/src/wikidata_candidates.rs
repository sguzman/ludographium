//! Independent source-title correspondence candidates; never verified game identities.
//! Only same-platform normalized label equality is evaluated. No fuzzy matching.
use crate::original_dat::OriginalDatCatalog;
use crate::wikidata_text::WikidataTextCatalog;
use crate::CatalogError;
use serde::Serialize;
use std::collections::{BTreeMap, HashSet};

const REGIONS: &[&str] = &[
    "USA", "Europe", "World", "Japan", "Australia", "Brazil", "Canada",
    "Korea", "Asia", "China", "Taiwan", "Hong Kong", "France", "Germany",
    "Spain", "Italy", "Sweden", "Netherlands", "Russia", "UK",
];
const LANGUAGES: &[&str] = &[
    "En", "Fr", "De", "Es", "It", "Pt", "Ja", "Ko", "Zh", "Nl", "Ru", "Sv",
];

fn source_tag(tag: &str) -> bool {
    let parts: Vec<_> = tag.split(',').map(str::trim).collect();
    let regions = !parts.is_empty() && parts.iter().all(|part| REGIONS.contains(part));
    let languages = !parts.is_empty() && parts.iter().all(|part| LANGUAGES.contains(part));
    let revision = tag.strip_prefix("Rev ").is_some_and(|suffix| {
        (!suffix.is_empty() && suffix.bytes().all(|b| b.is_ascii_digit()))
            || (suffix.len() == 1 && suffix.bytes().all(|b| b.is_ascii_uppercase()))
    });
    regions || languages || revision
}

/// Remove only trailing *declared source tags*, never title-significant parentheses.
/// Whitespace and case are normalized; punctuation, spelling and accents are retained.
pub fn title_key(title: &str) -> String {
    let mut normalized = title.trim().to_owned();
    for _ in 0..12 {
        let Some(before_close) = normalized.strip_suffix(')') else {
            break;
        };
        let Some(open) = before_close.rfind(" (") else {
            break;
        };
        let tag = before_close[open + 2..].trim();
        if tag.contains('(') || tag.contains(')') || !source_tag(tag) {
            break;
        }
        normalized.truncate(open);
        normalized = normalized.trim_end().to_owned();
    }
    normalized.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase()
}

#[derive(Debug, Serialize)]
pub struct WikidataTitleCandidate {
    pub platform: String,
    pub source_ordinal: usize,
    pub source_title: String,
    pub source_path: String,
    pub source_blob_sha: String,
    pub wikidata_qid: String,
    pub wikidata_label: String,
    pub wikidata_source_path: String,
    pub wikidata_source_sha256: String,
    pub title_key: String,
    pub competing_wikidata_items: usize,
    pub status: &'static str,
    pub interpretation: &'static str,
}

pub struct WikidataCandidateCatalog {
    matches: Vec<WikidataTitleCandidate>,
    platform_ids: Vec<String>,
    ambiguous_links: usize,
    source_records_with_candidate: usize,
}

#[derive(Debug, Serialize)]
pub struct CandidateSummary<'a> {
    pub platforms_searched: &'a [String],
    pub total_candidate_links: usize,
    pub source_records_with_candidate: usize,
    pub ambiguous_candidate_links: usize,
}

impl WikidataCandidateCatalog {
    pub fn reconcile(base: &OriginalDatCatalog, wikidata: &WikidataTextCatalog) -> Self {
        let platforms: Vec<String> = wikidata.platform_ids().map(str::to_owned).collect();
        let wanted: HashSet<&str> = platforms.iter().map(String::as_str).collect();
        // Platform + exact conservative title key -> distinct Wikidata QIDs.
        let mut index: BTreeMap<(String, String), Vec<(String, String, String)>> =
            BTreeMap::new();
        for (platform, qid, label, sha) in wikidata.reconciliation_labels() {
            let key = title_key(label);
            if !key.is_empty() {
                index
                    .entry((platform.to_owned(), key))
                    .or_default()
                    .push((qid.to_owned(), label.to_owned(), sha.to_owned()));
            }
        }
        for candidates in index.values_mut() {
            candidates.sort_by(|a, b| a.0.cmp(&b.0));
            candidates.dedup_by(|a, b| a.0 == b.0);
        }

        let mut matches = Vec::new();
        let mut ambiguous_links = 0;
        let mut source_records_with_candidate = 0;
        for (platform, ordinal, title, source_path, source_sha) in base.reconciliation_titles() {
            if !wanted.contains(platform) {
                continue;
            }
            let key = title_key(title);
            let Some(candidates) = index.get(&(platform.to_owned(), key.clone())) else {
                continue;
            };
            source_records_with_candidate += 1;
            let ambiguous = candidates.len() > 1;
            for (qid, label, wikidata_sha) in candidates {
                if ambiguous {
                    ambiguous_links += 1;
                }
                matches.push(WikidataTitleCandidate {
                    platform: platform.to_owned(),
                    source_ordinal: ordinal,
                    source_title: title.to_owned(),
                    source_path: source_path.to_owned(),
                    source_blob_sha: source_sha.to_owned(),
                    wikidata_qid: qid.clone(),
                    wikidata_label: label.clone(),
                    wikidata_source_path: format!("data/wikidata/v1/{platform}.jsonl"),
                    wikidata_source_sha256: wikidata_sha.clone(),
                    title_key: key.clone(),
                    competing_wikidata_items: candidates.len(),
                    status: if ambiguous {
                        "ambiguous_wikidata_title"
                    } else {
                        "title_candidate"
                    },
                    interpretation: "noncanonical-title-evidence-not-verified-game-identity",
                });
            }
        }
        Self { matches, platform_ids: platforms, ambiguous_links, source_records_with_candidate }
    }

    pub fn summary(&self) -> CandidateSummary<'_> {
        CandidateSummary {
            platforms_searched: &self.platform_ids,
            total_candidate_links: self.matches.len(),
            source_records_with_candidate: self.source_records_with_candidate,
            ambiguous_candidate_links: self.ambiguous_links,
        }
    }

    /// Optionally inspect one QID or a source-title substring. Limit never changes
    /// the full-corpus aggregate counts or underlying candidate evidence.
    pub fn search(
        &self,
        title: Option<&str>,
        qid: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&WikidataTitleCandidate>), CatalogError> {
        if !(1..=200).contains(&limit)
            || title.is_some_and(|t| t.trim().is_empty())
            || qid.is_some_and(|id| {
                !id.strip_prefix('Q').is_some_and(|digits| {
                    !digits.is_empty() && !digits.starts_with('0')
                        && digits.bytes().all(|b| b.is_ascii_digit())
                })
            })
        {
            return Err(CatalogError::Invalid(
                "candidate filter invalid: require nonblank title, valid QID, limit 1..=200".into(),
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut total = 0;
        let mut results = Vec::new();
        for candidate in &self.matches {
            if qid.is_some_and(|id| candidate.wikidata_qid != id)
                || needle.as_ref().is_some_and(|n| {
                    !candidate.source_title.to_lowercase().contains(n)
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
    use super::{title_key, WikidataCandidateCatalog};
    use crate::original_dat::OriginalDatCatalog;
    use crate::wikidata_text::WikidataTextCatalog;
    use std::path::Path;

    #[test]
    fn strips_only_known_trailing_tags_and_preserves_significant_suffixes() {
        assert_eq!(title_key("  Adventure (USA) (Rev 1)  "), "adventure");
        assert_eq!(title_key("Game (USA) (En,Fr,De)"), "game");
        assert_eq!(title_key("Game (USA) (Hacked)"), "game (usa) (hacked)");
        assert_eq!(title_key("Pokémon (Japan)"), "pokémon");
        assert_eq!(title_key("  Mega   Man   2  "), "mega man 2");
        assert_eq!(title_key("Game (Super Deluxe)"), "game (super deluxe)");
    }

    #[test]
    fn direct_git_text_candidate_counts_match_published_evidence() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let base = OriginalDatCatalog::open(&root, "all").unwrap();
        let wikidata = WikidataTextCatalog::open(&root, "all").unwrap();
        let catalog = WikidataCandidateCatalog::reconcile(&base, &wikidata);
        let summary = catalog.summary();
        assert_eq!(summary.platforms_searched.len(), 16);
        assert_eq!(summary.total_candidate_links, 8_971);
        assert_eq!(summary.source_records_with_candidate, 8_908);
        assert_eq!(summary.ambiguous_candidate_links, 126);
        let (total, matches) = catalog.search(None, Some("Q379915"), 5).unwrap();
        assert!(total > 0);
        assert!(matches.iter().any(|hit| {
            hit.platform == "atari2600"
                && hit.status == "title_candidate"
                && hit.wikidata_label == "Adventure"
        }));
    }
}
