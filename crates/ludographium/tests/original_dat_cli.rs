//! Exercise the real Rust CLI against cloned original DAT text, without
//! generating a database or downloading an upstream source.
use serde_json::Value;
use std::path::Path;
use std::process::Command;

fn query(args: &[&str]) -> Value {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let output = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(root)
        .args(args)
        .output()
        .expect("Rust CLI executable");
    assert!(
        output.status.success(),
        "source DAT CLI failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).expect("CLI must return structured JSON")
}

#[test]
fn atari_source_text_is_searchable_from_existing_cli() {
    let result = query(&[
        "--source-dat",
        "--platform",
        "atari2600",
        "--title",
        "Adventure",
        "--limit",
        "5",
    ]);
    assert_eq!(result["source_mode"], "original-dat-text");
    assert_eq!(result["platforms_searched"][0], "atari2600");
    assert!(result["total_source_records"].as_u64().unwrap() > 0);
    assert!(result["match_count"].as_u64().unwrap() > 0);
    let first = &result["matches"][0];
    assert_eq!(first["platform"], "atari2600");
    assert!(first["source"]["path"]
        .as_str()
        .unwrap()
        .contains("Atari - 2600.dat"));
    assert!(first["source"]["blob_sha"].as_str().unwrap().len() == 40);
}

#[test]
fn all_original_platforms_are_searchable_offline_including_empty_sources() {
    let result = query(&[
        "--source-dat",
        "--platform",
        "all",
        "--title",
        "Adventure",
        "--limit",
        "1",
    ]);
    assert_eq!(result["source_mode"], "original-dat-text");
    assert_eq!(result["platforms_searched"].as_array().unwrap().len(), 75);
    assert!(result["total_source_records"].as_u64().unwrap() > 0);
    assert_eq!(result["match_count"], 1);

    let empty = query(&[
        "--source-dat",
        "--platform",
        "microsoftxbox360gamesondemand",
        "--title",
        "anything",
    ]);
    assert_eq!(empty["match_count"], 0);
    assert_eq!(empty["total_source_records"], 0);
}

#[test]
fn optional_bibliographic_dat_enrichment_uses_original_attributed_claims() {
    let plain = query(&[
        "--source-dat",
        "--platform",
        "atari2600",
        "--title",
        "3-D Tic-Tac-Toe",
    ]);
    assert!(plain["matches"][0].get("metadata_claims").is_none());

    let enriched = query(&[
        "--source-dat",
        "--enriched",
        "--platform",
        "atari2600",
        "--title",
        "3-D Tic-Tac-Toe",
    ]);
    assert_eq!(
        enriched["bibliographic_mode"],
        "verified-original-field-dat-text"
    );
    assert!(
        enriched["field_claim_resolution_counts"]["matched"]
            .as_u64()
            .unwrap()
            > 0
    );
    assert!(enriched["matches"]
        .as_array()
        .unwrap()
        .iter()
        .any(|record| {
            record["metadata_claims"].as_array().is_some_and(|claims| {
                claims.iter().any(|claim| {
                    claim["field"] == "releaseyear"
                        && claim["resolution"]["status"] == "matched"
                        && claim["source_path"]
                            .as_str()
                            .is_some_and(|path| path.ends_with("Atari - 2600.dat"))
                        && claim["source_blob_sha"].as_str().is_some()
                })
            })
        }));
}

/// Identification title lookup must not hide separately preserved
/// bibliographic observations containing serials but no CRC32.
#[test]
fn serial_only_claims_are_searchable_without_identification_records() {
    let plain = query(&[
        "--source-dat",
        "--platform",
        "sonyplaystationportable",
        "--title",
        "007 - From Russia with Love",
    ]);
    assert_eq!(plain["source_mode"], "original-dat-text");

    let claims = query(&[
        "--source-dat",
        "--enriched",
        "--claims",
        "--platform",
        "sonyplaystationportable",
        "--title",
        "007 - From Russia with Love",
        "--limit",
        "10",
    ]);
    assert_eq!(claims["source_mode"], "original-field-dat-text");
    assert!(claims["total_source_claims"].as_u64().unwrap() >= 4);
    assert!(claims["claims"].as_array().unwrap().iter().any(|claim| {
        claim["resolution"]["status"] == "missing_crc"
            && claim["crc32"].is_null()
            && claim["source_fields"]["rom_serial"]
                .as_str()
                .is_some_and(|serial| serial.starts_with("UL"))
            && claim["source_blob_sha"]
                .as_str()
                .is_some_and(|sha| sha.len() == 40)
            && claim["source_ordinal"].as_u64().unwrap() > 0
    }));

    let unfiltered = query(&[
        "--source-dat",
        "--enriched",
        "--claims",
        "--platform",
        "sonyplaystationportable",
        "--limit",
        "1",
    ]);
    assert!(unfiltered["total_source_claims"].as_u64().unwrap() > 100);
    assert_eq!(unfiltered["returned_claims"], 1);
}

/// Claim discovery is opt-in and must not accept fingerprint modes.
#[test]
fn bibliographic_claim_mode_rejects_unsafe_argument_combinations() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec!["--source-dat", "--claims", "--platform", "atari2600"],
        vec!["--enriched", "--claims", "--platform", "atari2600"],
        vec![
            "--source-dat",
            "--enriched",
            "--claims",
            "--platform",
            "atari2600",
            "--sha1",
            "0000000000000000000000000000000000000000",
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(
            !output.status.success(),
            "invalid arguments unexpectedly accepted: {args:?}"
        );
    }
}

#[test]
fn wikidata_text_source_cli_preserves_item_ids_dates_and_provenance() {
    let qid = query(&[
        "--wikidata-text",
        "--platform",
        "atari2600",
        "--qid",
        "Q379915",
    ]);
    assert_eq!(qid["source_mode"], "verified-wikidata-jsonl");
    assert_eq!(qid["returned_matches"], 1);
    assert_eq!(qid["matches"][0]["english_label"], "Adventure");
    assert_eq!(qid["matches"][0]["source"]["license"], "CC0-1.0");
    assert_eq!(
        qid["matches"][0]["dates"][0]["value"],
        "1980-01-01T00:00:00Z"
    );

    let titles = query(&[
        "--wikidata-text",
        "--platform",
        "all",
        "--title",
        "Adventure",
        "--limit",
        "5",
    ]);
    assert_eq!(titles["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(titles["source_item_count"], 15868);
    assert_eq!(titles["source_date_claim_count"], 29333);
    assert!(titles["total_source_matches"].as_u64().unwrap() > 0);
    assert_eq!(titles["returned_matches"], 5);

    let list = query(&["--wikidata-text", "--platform", "atari2600", "--limit", "1"]);
    assert_eq!(list["query_kind"], "wikidata-source-list");
    assert_eq!(list["returned_matches"], 1);
}

#[test]
fn conservative_cross_source_title_candidates_preserve_ambiguity() {
    let all = query(&["--wikidata-candidates", "--platform", "all", "--limit", "2"]);
    assert_eq!(all["source_mode"], "wikidata-libretro-title-candidates");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(all["total_candidate_links"], 8971);
    assert_eq!(all["source_records_with_candidate"], 8908);
    assert_eq!(all["ambiguous_candidate_links"], 126);
    assert_eq!(all["returned_candidates"], 2);
    assert!(all["candidates"][0]["source_blob_sha"].as_str().is_some());
    assert!(all["candidates"][0]["wikidata_source_sha256"]
        .as_str()
        .is_some());

    let atari = query(&[
        "--wikidata-candidates",
        "--platform",
        "atari2600",
        "--qid",
        "Q379915",
        "--limit",
        "5",
    ]);
    assert!(atari["total_filtered_candidates"].as_u64().unwrap() > 0);
    assert!(atari["candidates"].as_array().unwrap().iter().any(|item| {
        item["status"] == "title_candidate"
            && item["source_title"]
                .as_str()
                .is_some_and(|name| name.contains("Adventure"))
            && item["wikidata_qid"] == "Q379915"
            && item["interpretation"] == "noncanonical-title-evidence-not-verified-game-identity"
    }));

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec!["--wikidata-candidates", "--platform", "all", "--source-dat"],
        vec![
            "--wikidata-candidates",
            "--platform",
            "all",
            "--sha1",
            "0000000000000000000000000000000000000000",
        ],
        vec![
            "--wikidata-candidates",
            "--platform",
            "all",
            "--qid",
            "invalid",
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(!output.status.success());
    }
}

#[test]
fn cross_source_year_audit_retains_both_sets_of_source_evidence() {
    let result = query(&[
        "--wikidata-candidates",
        "--compare-years",
        "--platform",
        "all",
        "--limit",
        "3",
    ]);
    assert_eq!(result["total_candidate_links"], 8971);
    let counts = result["year_comparison_counts"].as_object().unwrap();
    let total: u64 = counts.values().map(|n| n.as_u64().unwrap()).sum();
    assert_eq!(total, 8971);
    assert!(counts["overlapping_observed_years"].as_u64().unwrap() > 0);
    assert_eq!(result["year_evidence"].as_array().unwrap().len(), 3);
    assert_eq!(result["total_filtered_year_comparisons"], 8971);
    assert_eq!(
        result["candidates"][0]["source_ordinal"],
        result["year_evidence"][0]["source_ordinal"]
    );
    assert_eq!(
        result["candidates"][0]["wikidata_qid"],
        result["year_evidence"][0]["wikidata_qid"]
    );
    assert!(result["year_evidence"][0]["interpretation"]
        .as_str()
        .unwrap()
        .contains("review-only"));

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let invalid = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(root)
        .args([
            "--compare-years",
            "--platform",
            "atari2600",
            "--title",
            "Adventure",
        ])
        .output()
        .unwrap();
    assert!(!invalid.status.success());
}

#[test]
fn wikidata_property_sources_are_available_in_rust_with_qid_provenance() {
    let all = query(&["--wikidata-properties", "--platform", "all", "--limit", "2"]);
    assert_eq!(all["source_mode"], "verified-wikidata-property-bindings");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(all["source_statements"], 47144);
    assert_eq!(all["source_item_platform_observations"], 14759);
    assert_eq!(all["non_entity_value_bindings"], 3);
    assert_eq!(all["returned_claims"], 2);
    assert!(all["claims"][0]["source_sha256"].as_str().unwrap().len() == 64);
    assert!(all["claims"][0]["source_ordinal"].as_u64().unwrap() > 0);
    assert!(all["claims"][0]["raw_binding"]["value"].is_object());

    let adventure = query(&[
        "--wikidata-properties",
        "--platform",
        "atari2600",
        "--qid",
        "Q379915",
        "--property",
        "P178",
        "--limit",
        "10",
    ]);
    assert!(adventure["total_filtered_claims"].as_u64().unwrap() > 0);
    assert!(adventure["claims"].as_array().unwrap().iter().all(|entry| {
        entry["platform"] == "atari2600"
            && entry["item_qid"] == "Q379915"
            && entry["property"] == "P178"
            && entry["interpretation"]
                == "original-attributed-wikidata-property-not-verified-game-identity"
    }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-properties",
            "--platform",
            "all",
            "--title",
            "Mario",
        ],
        vec![
            "--wikidata-properties",
            "--platform",
            "all",
            "--property",
            "P577",
        ],
        vec!["--wikidata-properties", "--platform", "all", "--qid", "Q0"],
        vec![
            "--property",
            "P178",
            "--platform",
            "atari2600",
            "--title",
            "Adventure",
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(
            !output.status.success(),
            "invalid arguments accepted: {args:?}"
        );
    }
}

#[test]
fn wikidata_entity_labels_are_optional_verified_evidence_in_property_queries() {
    let all = query(&[
        "--wikidata-properties",
        "--with-entity-labels",
        "--platform",
        "all",
        "--limit",
        "5",
    ]);
    assert_eq!(all["source_statements"], 47144);
    assert_eq!(all["entity_label_source"]["entity_qids"], 2768);
    assert_eq!(all["entity_label_source"]["english_labels"], 2614);
    assert_eq!(all["entity_label_source"]["unlabeled_qids"], 154);
    for original in all["claims"].as_array().unwrap() {
        if let Some(qid) = original["value_qid"].as_str() {
            assert_eq!(original["value_label_evidence"]["qid"], qid);
            assert_eq!(
                original["value_label_evidence"]["source_query_sha256"]
                    .as_str()
                    .unwrap()
                    .len(),
                64
            );
            assert!(original["value_label_evidence"]["source_path"]
                .as_str()
                .unwrap()
                .contains("property-labels-v1"));
        }
    }

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let invalid = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(&root)
        .args([
            "--with-entity-labels",
            "--platform",
            "atari2600",
            "--title",
            "Adventure",
        ])
        .output()
        .unwrap();
    assert!(!invalid.status.success());
}

#[test]
fn cross_source_company_credit_audit_preserves_unresolved_names_and_provenance() {
    let result = query(&[
        "--wikidata-candidates",
        "--compare-credits",
        "--platform",
        "all",
        "--limit",
        "4",
    ]);
    assert_eq!(result["total_candidate_links"], 8971);
    assert_eq!(result["total_filtered_credit_comparisons"], 17942);
    let counts = result["credit_evidence_counts"].as_object().unwrap();
    for credit in ["developer", "publisher"] {
        let total: u64 = counts[credit]
            .as_object()
            .unwrap()
            .values()
            .map(|value| value.as_u64().unwrap())
            .sum();
        assert_eq!(total, 8971);
    }
    assert_eq!(result["credit_evidence"].as_array().unwrap().len(), 4);
    assert!(result["credit_evidence"]
        .as_array()
        .unwrap()
        .iter()
        .all(|entry| {
            entry["source_blob_sha"].as_str().is_some()
                && entry["title_candidate_status"].as_str().is_some()
                && entry["interpretation"]
                    .as_str()
                    .unwrap()
                    .contains("review-only")
        }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let invalid = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(&root)
        .args(["--compare-credits", "--platform", "all", "--limit", "4"])
        .output()
        .unwrap();
    assert!(!invalid.status.success());
}

#[test]
fn independent_wikidata_game_observations_preserve_both_snapshot_sources() {
    let all = query(&["--wikidata-items", "--platform", "all", "--limit", "2"]);
    assert_eq!(all["source_mode"], "multi-snapshot-wikidata-qid-source-observations");
    assert_eq!(all["title_date_source_items"], 15868);
    assert_eq!(all["property_source_items"], 14759);
    assert!(all["combined_distinct_platform_qids"].as_u64().unwrap() >= 15868);
    assert_eq!(all["returned_source_items"], 2);
    let atari = query(&[
        "--wikidata-items", "--platform", "atari2600", "--qid", "Q379915",
    ]);
    assert!(atari["total_filtered_source_items"].as_u64().unwrap() > 0);
    let item = &atari["source_items"][0];
    assert_eq!(item["qid"], "Q379915");
    assert_eq!(item["platform"], "atari2600");
    assert_eq!(item["english_label"], "Adventure");
    assert_eq!(item["source_presence"], "both_independent_snapshots");
    assert!(item["original_title_date_observation"]["source"]["sha256"].as_str().is_some());
    assert!(item["property_claims"]["P178"].is_array());
    assert!(item["interpretation"].as_str().unwrap().contains("not-verified"));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let invalid = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(&root)
        .args(["--wikidata-items", "--platform", "all", "--property", "P178"])
        .output().unwrap();
    assert!(!invalid.status.success());
}
