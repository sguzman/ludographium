//! Evidence-only comparison of source year assertions on title candidates.
//! A different year may denote another region, edition, port or prototype.
//! These statuses never authenticate a work or call one source incorrect.
use crate::original_dat::{OriginalDatCatalog, OriginalYearEvidence};
use crate::wikidata_candidates::WikidataCandidateCatalog;
use crate::wikidata_text::{WikidataDate, WikidataTextCatalog};
use crate::CatalogError;
use serde::Serialize;
use std::collections::{BTreeMap, HashMap, HashSet};

#[derive(Debug, Serialize)]
pub struct WikidataDateEvidence {
    pub raw_value: String,
    pub rdf_kind: String,
    pub datatype: Option<String>,
    pub parsed_year: Option<u16>,
}

#[derive(Debug, Serialize)]
pub struct YearComparison {
    pub platform: String,
    pub source_ordinal: usize,
    pub source_title: String,
    pub source_blob_sha: String,
    pub wikidata_qid: String,
    pub wikidata_source_sha256: String,
    pub title_candidate_status: &'static str,
    pub year_status: &'static str,
    pub original_year_claims: Vec<OriginalYearEvidence>,
    pub wikidata_date_claims: Vec<WikidataDateEvidence>,
    pub interpretation: &'static str,
}

pub struct WikidataYearAudit {
    comparisons: Vec<YearComparison>,
    counts: BTreeMap<String, usize>,
}

/// Parse a single four-digit year, or the leading year of an ISO-like date.
/// No day or territory inference; never accept partial numeric prefixes.
fn parse_year(value: &str) -> Option<u16> {
    let digits = value.get(..4)?;
    if !digits.bytes().all(|digit| digit.is_ascii_digit()) {
        return None;
    }
    if !matches!(value.as_bytes().get(4), None | Some(b'-')) {
        return None;
    }
    let year = digits.parse::<u16>().ok()?;
    (1000..=2999).contains(&year).then_some(year)
}

fn date_year(date: &WikidataDate) -> Option<u16> {
    if matches!(date.kind.as_str(), "literal" | "typed-literal") {
        parse_year(&date.value)
    } else {
        None
    }
}

fn compare_year_sets(
    original: &[OriginalYearEvidence],
    wikidata: &[WikidataDateEvidence],
) -> &'static str {
    let left: HashSet<u16> = original
        .iter()
        .filter_map(|x| parse_year(&x.raw_value))
        .collect();
    let right: HashSet<u16> = wikidata.iter().filter_map(|x| x.parsed_year).collect();
    if left.is_empty() && right.is_empty() {
        "both_years_missing"
    } else if left.is_empty() {
        "libretro_year_missing"
    } else if right.is_empty() {
        "wikidata_literal_year_missing"
    } else if left.is_disjoint(&right) {
        "different_observed_years"
    } else {
        "overlapping_observed_years"
    }
}

impl WikidataYearAudit {
    pub fn build(
        original: &OriginalDatCatalog,
        wikidata: &WikidataTextCatalog,
        candidates: &WikidataCandidateCatalog,
    ) -> Self {
        let years = original.reconciliation_years();
        let mut dates: HashMap<(String, String), Vec<WikidataDateEvidence>> = HashMap::new();
        for (platform, qid, assertions) in wikidata.reconciliation_dates() {
            dates.insert(
                (platform.to_owned(), qid.to_owned()),
                assertions
                    .iter()
                    .map(|entry| WikidataDateEvidence {
                        raw_value: entry.value.clone(),
                        rdf_kind: entry.kind.clone(),
                        datatype: entry.datatype.clone(),
                        parsed_year: date_year(entry),
                    })
                    .collect(),
            );
        }

        let mut comparisons = Vec::new();
        let mut counts = BTreeMap::new();
        for candidate in candidates.candidates() {
            let originals = years
                .get(&(candidate.platform.clone(), candidate.source_ordinal))
                .cloned()
                .unwrap_or_default();
            let wiki: Vec<WikidataDateEvidence> = dates
                .get(&(candidate.platform.clone(), candidate.wikidata_qid.clone()))
                .map(|values| {
                    values
                        .iter()
                        .map(|entry| WikidataDateEvidence {
                            raw_value: entry.raw_value.clone(),
                            rdf_kind: entry.rdf_kind.clone(),
                            datatype: entry.datatype.clone(),
                            parsed_year: entry.parsed_year,
                        })
                        .collect()
                })
                .unwrap_or_default();
            let status = compare_year_sets(&originals, &wiki);
            *counts.entry(status.to_owned()).or_insert(0) += 1;
            comparisons.push(YearComparison {
                platform: candidate.platform.clone(),
                source_ordinal: candidate.source_ordinal,
                source_title: candidate.source_title.clone(),
                source_blob_sha: candidate.source_blob_sha.clone(),
                wikidata_qid: candidate.wikidata_qid.clone(),
                wikidata_source_sha256: candidate.wikidata_source_sha256.clone(),
                title_candidate_status: candidate.status,
                year_status: status,
                original_year_claims: originals,
                wikidata_date_claims: wiki,
                interpretation: "review-only-year-evidence-not-release-date-verification",
            });
        }
        Self {
            comparisons,
            counts,
        }
    }

    pub fn status_counts(&self) -> &BTreeMap<String, usize> {
        &self.counts
    }

    /// Filter for review after whole-corpus counts are computed.
    pub fn search(
        &self,
        title: Option<&str>,
        qid: Option<&str>,
        status: Option<&str>,
        limit: usize,
    ) -> Result<(usize, Vec<&YearComparison>), CatalogError> {
        if !(1..=200).contains(&limit)
            || title.is_some_and(|value| value.trim().is_empty())
            || status.is_some_and(|value| !self.counts.contains_key(value))
        {
            return Err(CatalogError::Invalid(
                "year evidence search requires nonblank title, known status and limit 1..=200"
                    .into(),
            ));
        }
        let needle = title.map(str::to_lowercase);
        let mut count = 0;
        let mut results = Vec::new();
        for row in &self.comparisons {
            if qid.is_some_and(|value| row.wikidata_qid != value)
                || status.is_some_and(|value| row.year_status != value)
                || needle
                    .as_ref()
                    .is_some_and(|value| !row.source_title.to_lowercase().contains(value))
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
    use super::{
        compare_year_sets, date_year, parse_year, WikidataDateEvidence, WikidataYearAudit,
    };
    use crate::original_dat::{OriginalDatCatalog, OriginalYearEvidence};
    use crate::wikidata_candidates::WikidataCandidateCatalog;
    use crate::wikidata_text::{WikidataDate, WikidataTextCatalog};
    use std::path::Path;

    #[test]
    fn missing_differing_and_overlapping_years_remain_distinct() {
        let originals = vec![OriginalYearEvidence {
            raw_value: "1980".to_owned(),
            source_kind: "identification_dat_scalar",
            source_path: "sample.dat".to_owned(),
            source_blob_sha: "fixture".to_owned(),
            source_ordinal: 1,
        }];
        let date = WikidataDateEvidence {
            raw_value: "1980-01-01T00:00:00Z".to_owned(),
            rdf_kind: "literal".to_owned(),
            datatype: None,
            parsed_year: Some(1980),
        };
        assert_eq!(parse_year("1980"), Some(1980));
        assert_eq!(parse_year("1980-01-01T00:00:00Z"), Some(1980));
        assert_eq!(parse_year("1980ish"), None);
        assert_eq!(parse_year("01980"), None);
        assert_eq!(
            compare_year_sets(&originals, &[date]),
            "overlapping_observed_years"
        );
        let different = WikidataDateEvidence {
            raw_value: "1981-01-01T00:00:00Z".to_owned(),
            rdf_kind: "literal".to_owned(),
            datatype: None,
            parsed_year: Some(1981),
        };
        assert_eq!(
            compare_year_sets(&originals, &[different]),
            "different_observed_years"
        );
        assert_eq!(
            compare_year_sets(&originals, &[]),
            "wikidata_literal_year_missing"
        );
        assert_eq!(compare_year_sets(&[], &[]), "both_years_missing");
        let rdf_uri = WikidataDate {
            kind: "uri".to_owned(),
            value: "http://www.wikidata.org/.well-known/genid/example".to_owned(),
            datatype: None,
            language: None,
        };
        assert_eq!(date_year(&rdf_uri), None);
    }

    #[test]
    fn real_corpus_date_evidence_does_not_mutate_title_correspondences() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let original = OriginalDatCatalog::open(&root, "all")
            .unwrap()
            .with_enrichment(&root)
            .unwrap();
        let wikidata = WikidataTextCatalog::open(&root, "all").unwrap();
        let candidates = WikidataCandidateCatalog::reconcile(&original, &wikidata);
        let audit = WikidataYearAudit::build(&original, &wikidata, &candidates);
        assert_eq!(candidates.summary().total_candidate_links, 8_971);
        assert_eq!(audit.status_counts().values().sum::<usize>(), 8_971);
        assert!(
            audit
                .status_counts()
                .get("overlapping_observed_years")
                .copied()
                .unwrap_or(0)
                > 0
        );
        let (_, samples) = audit.search(None, None, None, 5).unwrap();
        assert!(samples
            .iter()
            .all(|sample| sample.interpretation.contains("review-only")));
    }
}
