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
    let labeled = query(&[
        "--wikidata-relations",
        "--with-entity-labels",
        "--platform",
        "atari2600",
        "--qid",
        "Q100701966",
        "--limit",
        "10",
    ]);
    assert_eq!(labeled["entity_label_source"]["entity_qids"], 1837);
    assert_eq!(labeled["entity_label_source"]["english_labels"], 1639);
    assert_eq!(labeled["entity_label_source"]["unlabeled_qids"], 198);
    assert!(labeled["claims"].as_array().unwrap().iter().any(|entry| {
        entry["value_entity_qid"] == "Q208850"
            && entry["value_english_label_evidence"]["source_sha256"]
                .as_str()
                .is_some()
    }));

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
    assert_eq!(
        all["source_mode"],
        "multi-snapshot-wikidata-qid-source-observations"
    );
    assert_eq!(all["title_date_source_items"], 15868);
    assert_eq!(all["property_source_items"], 14759);
    assert_eq!(all["relation_source_items"], 14772);
    assert_eq!(all["localized_source_items"], 15731);
    assert_eq!(all["authority_source_items"], 13609);
    assert!(all["combined_distinct_platform_qids"].as_u64().unwrap() >= 15868);
    assert_eq!(all["returned_source_items"], 2);
    let atari = query(&[
        "--wikidata-items",
        "--platform",
        "atari2600",
        "--qid",
        "Q379915",
    ]);
    assert!(atari["total_filtered_source_items"].as_u64().unwrap() > 0);
    let item = &atari["source_items"][0];
    assert_eq!(item["qid"], "Q379915");
    assert_eq!(item["platform"], "atari2600");
    assert_eq!(item["english_label"], "Adventure");
    assert_eq!(item["source_presence"], "multiple_independent_snapshots");
    assert_eq!(
        item["source_membership"],
        serde_json::json!([
            "title_date",
            "company_genre",
            "relations",
            "localized_titles",
            "authority_ids"
        ])
    );
    assert!(item["original_title_date_observation"]["source"]["sha256"]
        .as_str()
        .is_some());
    assert!(item["property_claims"]["P178"].is_array());
    assert_eq!(item["localized_source_present"], true);
    assert!(item["localized_names"].as_object().is_some());
    assert_eq!(item["relation_source_present"], true);
    assert!(item["relation_claims"].as_object().is_some());
    assert!(item["interpretation"]
        .as_str()
        .unwrap()
        .contains("not-verified"));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let invalid = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(&root)
        .args([
            "--wikidata-items",
            "--platform",
            "all",
            "--property",
            "P178",
        ])
        .output()
        .unwrap();
    assert!(!invalid.status.success());
}

#[test]
fn original_wikidata_relations_and_external_ids_are_offline_and_attributed() {
    let all = query(&["--wikidata-relations", "--platform", "all", "--limit", "2"]);
    assert_eq!(
        all["source_mode"],
        "verified-wikidata-game-relations-and-external-ids"
    );
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(all["source_statements"], 92621);
    assert_eq!(all["source_item_platform_observations"], 14772);
    assert_eq!(all["source_entity_value_bindings"], 83806);
    assert_eq!(all["source_property_counts"]["P1476"], 5532);
    assert_eq!(all["returned_claims"], 2);
    assert_eq!(all["source_property_counts"]["P1476"], 5532);
    assert_eq!(all["source_property_counts"]["P1733"], 2624);
    assert_eq!(all["source_property_counts"]["P2725"], 658);
    assert_eq!(
        all["claims"][0]["source_sha256"].as_str().unwrap().len(),
        64
    );
    assert!(all["claims"][0]["raw_binding"]["value"].is_object());

    let atari = query(&[
        "--wikidata-relations",
        "--platform",
        "atari2600",
        "--qid",
        "Q100701966",
        "--property",
        "P404",
        "--limit",
        "5",
    ]);
    assert!(atari["total_filtered_claims"].as_u64().unwrap() > 0);
    assert!(atari["claims"].as_array().unwrap().iter().all(|entry| {
        entry["item_qid"] == "Q100701966"
            && entry["platform"] == "atari2600"
            && entry["property"] == "P404"
    }));

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--title",
            "Mario",
        ],
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--property",
            "P178",
        ],
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--qid",
            "invalid",
        ],
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--wikidata-properties",
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
fn reverse_lookup_retains_shared_steam_id_and_multi_qid_ambiguity() {
    let result = query(&[
        "--wikidata-relations",
        "--platform",
        "all",
        "--external-id",
        "15750",
        "--property",
        "P1733",
        "--limit",
        "20",
    ]);
    assert_eq!(
        result["query_kind"],
        "exact-provider-identifier-source-claim"
    );
    assert_eq!(result["exact_provider_id_query"], "15750");
    assert!(result["total_filtered_claims"].as_u64().unwrap() >= 2);
    assert_eq!(result["distinct_game_qids_for_exact_id"], 2);
    assert_eq!(result["has_multi_qid_assignments"], true);
    assert!(result["claims"].as_array().unwrap().iter().all(|entry| {
        entry["property"] == "P1733"
            && entry["raw_binding"]["value"]["value"] == "15750"
            && entry["source_sha256"].as_str().is_some()
    }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--external-id",
            "15750",
        ],
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--external-id",
            "15750",
            "--property",
            "P1476",
        ],
        vec![
            "--wikidata-relations",
            "--platform",
            "all",
            "--external-id",
            "15750",
            "--property",
            "P1733",
            "--qid",
            "Q2256398",
        ],
        vec![
            "--wikidata-properties",
            "--platform",
            "all",
            "--external-id",
            "15750",
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
fn localized_source_names_preserve_original_languages_and_alternate_titles() {
    let all = query(&[
        "--wikidata-localized-titles",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(
        all["source_mode"],
        "verified-wikidata-language-tagged-game-names"
    );
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(all["total_original_localized_names"], 124690);
    assert_eq!(all["source_item_platform_observations"], 15731);
    assert_eq!(all["original_name_kind_counts"]["label"], 81593);
    assert_eq!(all["original_name_kind_counts"]["altLabel"], 43097);
    assert_eq!(all["returned_source_names"], 2);
    assert!(all["names"][0]["original_binding"]["label"]["xml:lang"]
        .as_str()
        .is_some());
    assert_eq!(all["names"][0]["source_sha256"].as_str().unwrap().len(), 64);
    let spanish = query(&[
        "--wikidata-localized-titles",
        "--platform",
        "all",
        "--language",
        "es",
        "--limit",
        "3",
    ]);
    assert!(spanish["total_filtered_source_names"].as_u64().unwrap() > 10000);
    assert!(spanish["names"].as_array().unwrap().iter().all(|entry| {
        let lang = entry["language_tag"].as_str().unwrap();
        lang == "es" || lang.starts_with("es-")
    }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-localized-titles",
            "--platform",
            "all",
            "--language",
            "xx",
        ],
        vec![
            "--wikidata-localized-titles",
            "--platform",
            "all",
            "--qid",
            "Q0",
        ],
        vec![
            "--wikidata-localized-titles",
            "--platform",
            "all",
            "--qid",
            "Q379915",
            "--title",
            "Adventure",
        ],
        vec![
            "--wikidata-properties",
            "--platform",
            "all",
            "--language",
            "es",
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
fn expanded_localized_source_cohorts_preserve_raw_languages_and_scoped_noncoverage() {
    let first = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "expanded-v1",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(first["metadata_cohort"], "expanded-v1");
    assert_eq!(first["platforms_searched"].as_array().unwrap().len(), 19);
    assert!(first["total_original_localized_names"].as_u64().unwrap() > 0);
    assert!(first["names"][0]["source_path"]
        .as_str()
        .unwrap()
        .starts_with("data/wikidata/expanded-localized-v1/"));
    let japanese = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "expanded-v1",
        "--platform",
        "atari7800",
        "--language",
        "ja",
        "--limit",
        "2",
    ]);
    assert!(japanese["total_filtered_source_names"].as_u64().unwrap() > 0);
    assert!(japanese["names"]
        .as_array()
        .unwrap()
        .iter()
        .all(|row| row["language_tag"].as_str().unwrap().starts_with("ja")));
    let second = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "expanded-v2",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(second["metadata_cohort"], "expanded-v2");
    assert_eq!(second["platforms_searched"].as_array().unwrap().len(), 18);
    assert_eq!(second["source_platform_row_counts"]["gameparkgp32"], 0);
    assert_eq!(second["source_platform_row_counts"]["tigergamecom"], 0);
    assert_eq!(second["source_platform_row_counts"]["gg"], 1444);
    let zero = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "expanded-v2",
        "--platform",
        "gameparkgp32",
        "--limit",
        "2",
    ]);
    assert_eq!(zero["total_original_localized_names"], 0);
    assert_eq!(zero["returned_source_names"], 0);
    assert_eq!(zero["platforms_searched"].as_array().unwrap().len(), 1);
    let combined = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "combined",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(combined["platforms_searched"].as_array().unwrap().len(), 65);
    assert_eq!(combined["total_original_localized_names"], 154198);
    assert_eq!(combined["metadata_cohort"], "combined");
    assert_eq!(combined["source_platform_row_counts"]["gameparkgp32"], 0);
    let selected = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "combined",
        "--platform",
        "gg",
        "--language",
        "ja",
        "--limit",
        "2",
    ]);
    assert_eq!(selected["platforms_searched"].as_array().unwrap().len(), 1);
    assert_eq!(selected["total_original_localized_names"], 1444);
    assert!(selected["total_filtered_source_names"].as_u64().unwrap() > 0);
    let third = query(&[
        "--wikidata-localized-titles",
        "--metadata-cohort",
        "expanded-v3",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(third["total_original_localized_names"], 247);
    assert_eq!(third["platforms_searched"].as_array().unwrap().len(), 12);
    assert_eq!(third["source_platform_row_counts"]["mobilezeebo"], 184);
    assert_eq!(third["source_platform_row_counts"]["nintendosufamiturbo"], 0);
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-localized-titles",
            "--platform",
            "all",
            "--metadata-cohort",
            "not-a-cohort",
        ],
        vec![
            "--wikidata-localized-candidates",
            "--platform",
            "all",
            "--metadata-cohort",
            "expanded-v1",
        ],
        vec![
            "--wikidata-properties",
            "--platform",
            "all",
            "--metadata-cohort",
            "combined",
        ],
        vec![
            "--wikidata-localized-titles",
            "--platform",
            "unknown",
            "--metadata-cohort",
            "combined",
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
fn localized_exact_title_correspondence_is_separate_from_english_baseline() {
    let result = query(&[
        "--wikidata-localized-candidates",
        "--platform",
        "all",
        "--limit",
        "3",
    ]);
    assert_eq!(
        result["source_mode"],
        "multilingual-wikidata-exact-title-review-candidates"
    );
    assert_eq!(
        result["summary"]["platforms_searched"]
            .as_array()
            .unwrap()
            .len(),
        16
    );
    assert!(result["summary"]["total_candidate_pairs"].as_u64().unwrap() > 0);
    assert!(
        result["summary"]["candidate_pairs_absent_from_english_title_match"]
            .as_u64()
            .unwrap()
            > 0
    );
    assert_eq!(result["returned_candidate_pairs"], 3);
    assert!(result["candidate_pairs"]
        .as_array()
        .unwrap()
        .iter()
        .all(|row| {
            row["original_source_blob_sha"].as_str().unwrap().len() == 40
                && row["localized_name_evidence"][0]["source_sha256"]
                    .as_str()
                    .unwrap()
                    .len()
                    == 64
                && row["interpretation"]
                    .as_str()
                    .unwrap()
                    .contains("review-only")
        }));
    let selected = query(&[
        "--wikidata-localized-candidates",
        "--platform",
        "atari2600",
        "--qid",
        "Q379915",
        "--limit",
        "5",
    ]);
    assert!(selected["total_filtered_candidate_pairs"].as_u64().unwrap() > 0);
    assert!(selected["candidate_pairs"]
        .as_array()
        .unwrap()
        .iter()
        .all(|row| { row["platform"] == "atari2600" && row["wikidata_item_qid"] == "Q379915" }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let bad = Command::new(env!("CARGO_BIN_EXE_ludographium"))
        .current_dir(&root)
        .args([
            "--wikidata-localized-candidates",
            "--platform",
            "all",
            "--language",
            "ja",
        ])
        .output()
        .unwrap();
    assert!(!bad.status.success());
}

#[test]
fn source_pinned_game_authority_ids_are_exactly_searchable_without_provider_joins() {
    let all = query(&[
        "--wikidata-authority-ids",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(
        all["source_mode"],
        "pinned-wikidata-third-party-game-authority-id-claims"
    );
    assert_eq!(all["source_claims"], 65182);
    assert_eq!(all["source_item_platform_observations"], 13609);
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(all["source_property_counts"]["P4769"], 23606);
    assert_eq!(all["source_property_counts"]["P11688"], 16800);
    assert_eq!(all["source_property_counts"]["P1933"], 15725);
    assert_eq!(all["returned_claims"], 2);
    assert_eq!(
        all["claims"][0]["source_sha256"].as_str().unwrap().len(),
        64
    );
    assert!(all["claims"][0]["source_ordinal"].as_u64().unwrap() >= 1);
    let atari = query(&[
        "--wikidata-authority-ids",
        "--platform",
        "atari2600",
        "--qid",
        "Q100701966",
        "--property",
        "P11688",
        "--limit",
        "5",
    ]);
    assert!(atari["total_filtered_claims"].as_u64().unwrap() > 0);
    assert!(atari["claims"]
        .as_array()
        .unwrap()
        .iter()
        .all(|claim| { claim["item_qid"] == "Q100701966" && claim["identifier"] == "39536" }));
    let reverse = query(&[
        "--wikidata-authority-ids",
        "--platform",
        "all",
        "--property",
        "P11688",
        "--external-id",
        "39536",
        "--limit",
        "5",
    ]);
    assert!(reverse["total_filtered_claims"].as_u64().unwrap() >= 1);
    assert!(
        reverse["distinct_wikidata_game_qids_for_identifier"]
            .as_u64()
            .unwrap()
            >= 1
    );
    assert!(reverse["claims"]
        .as_array()
        .unwrap()
        .iter()
        .all(|claim| { claim["property"] == "P11688" && claim["identifier"] == "39536" }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-authority-ids",
            "--platform",
            "all",
            "--title",
            "Mario",
        ],
        vec![
            "--wikidata-authority-ids",
            "--platform",
            "all",
            "--property",
            "P1733",
        ],
        vec![
            "--wikidata-authority-ids",
            "--platform",
            "all",
            "--qid",
            "Q0",
        ],
        vec![
            "--wikidata-authority-ids",
            "--platform",
            "all",
            "--external-id",
            "39536",
        ],
        vec![
            "--wikidata-authority-ids",
            "--platform",
            "all",
            "--wikidata-relations",
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(
            !output.status.success(),
            "invalid combination accepted: {args:?}"
        );
    }
}

#[test]
fn original_gamefaqs_statement_qualifiers_remain_distinct_from_selected_item_platform() {
    let all = query(&[
        "--wikidata-gamefaqs-qualifiers",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(
        all["source_mode"],
        "wikidata-gamefaqs-statement-level-p400-qualifier-evidence"
    );
    assert_eq!(all["source_statement_rows"], 23623);
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 16);
    assert_eq!(
        all["qualifier_scope_counts"]["no_explicit_platform_qualifier"],
        497
    );
    assert_eq!(
        all["qualifier_scope_counts"]["qualifier_equals_selected_item_platform"],
        9042
    );
    assert_eq!(
        all["qualifier_scope_counts"]["qualifier_names_other_platform"],
        14084
    );
    assert_eq!(all["returned_statement_rows"], 2);
    assert!(
        all["statements"][0]["source_sha256"]
            .as_str()
            .unwrap()
            .len()
            == 64
    );

    let atari = query(&[
        "--wikidata-gamefaqs-qualifiers",
        "--platform",
        "atari2600",
        "--qid",
        "Q1014915",
        "--external-id",
        "579332",
        "--limit",
        "5",
    ]);
    assert!(atari["total_filtered_statement_rows"].as_u64().unwrap() >= 1);
    assert!(atari["statements"].as_array().unwrap().iter().all(|entry| {
        entry["item_qid"] == "Q1014915"
            && entry["identifier"] == "579332"
            && entry["qualifier_platform_qid"] == "Q172742"
            && entry["qualifier_scope"] == "qualifier_names_other_platform"
    }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-gamefaqs-qualifiers",
            "--platform",
            "all",
            "--property",
            "P4769",
        ],
        vec![
            "--wikidata-gamefaqs-qualifiers",
            "--platform",
            "all",
            "--title",
            "Mario",
        ],
        vec![
            "--wikidata-gamefaqs-qualifiers",
            "--platform",
            "all",
            "--qid",
            "Q0",
        ],
        vec![
            "--wikidata-gamefaqs-qualifiers",
            "--platform",
            "all",
            "--wikidata-authority-ids",
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
fn independently_pinned_atari_psp_vita_source_responses_are_searchable_offline() {
    let all = query(&["--wikidata-expanded", "--platform", "all", "--limit", "2"]);
    assert_eq!(
        all["source_mode"],
        "pinned-wikidata-expanded-platform-source-text"
    );
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 3);
    assert_eq!(all["source_rows"], 3888);
    assert_eq!(all["source_item_platform_observations"], 2254);
    assert_eq!(all["literal_publication_date_bindings"], 3699);
    assert_eq!(all["nonliteral_publication_bindings"], 5);
    assert_eq!(all["returned_source_rows"], 2);
    assert_eq!(
        all["source_rows_evidence"][0]["source_sha256"]
            .as_str()
            .unwrap()
            .len(),
        64
    );

    let atari = query(&[
        "--wikidata-expanded",
        "--platform",
        "atari7800",
        "--qid",
        "Q1014915",
        "--limit",
        "10",
    ]);
    assert!(atari["total_filtered_source_rows"].as_u64().unwrap() > 0);
    assert!(atari["source_rows_evidence"]
        .as_array()
        .unwrap()
        .iter()
        .all(|row| {
            row["platform"] == "atari7800"
                && row["item_qid"] == "Q1014915"
                && row["english_label"] == "BurgerTime"
                && row["interpretation"]
                    .as_str()
                    .unwrap()
                    .contains("not-canonical")
        }));

    let vita = query(&[
        "--wikidata-expanded",
        "--platform",
        "sonyplaystationvita",
        "--title",
        "King Oddball",
        "--limit",
        "3",
    ]);
    assert!(vita["total_filtered_source_rows"].as_u64().unwrap() > 0);
    assert_eq!(vita["nonliteral_publication_bindings"], 5);

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec!["--wikidata-expanded", "--platform", "all", "--source-dat"],
        vec!["--wikidata-expanded", "--platform", "all", "--qid", "Q0"],
        vec!["--wikidata-expanded", "--platform", "all", "--limit", "0"],
        vec![
            "--wikidata-expanded",
            "--platform",
            "all",
            "--wikidata-text",
        ],
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(
            !result.status.success(),
            "invalid CLI arguments accepted: {args:?}"
        );
    }
}

#[test]
fn eighth_platform_cohort_retains_provisional_scope_and_original_source_provenance() {
    let all = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v8",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(all["expansion_source"], "v8");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 12);
    assert_eq!(all["source_platform_rows"].as_object().unwrap().len(), 12);
    assert_eq!(
        all["source_rows"].as_u64().unwrap(),
        all["source_platform_rows"]
            .as_object()
            .unwrap()
            .values()
            .map(|value| value.as_u64().unwrap())
            .sum::<u64>()
    );
    let zero_or_some = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v8",
        "--platform",
        "nintendoereader",
        "--limit",
        "2",
    ]);
    assert_eq!(
        zero_or_some["platforms_searched"].as_array().unwrap().len(),
        1
    );
    assert_eq!(zero_or_some["expansion_source"], "v8");
}

#[test]
fn newly_expanded_platform_title_candidates_are_evidence_only() {
    let all = query(&[
        "--wikidata-expanded-candidates",
        "--platform",
        "all",
        "--limit",
        "3",
    ]);
    assert_eq!(
        all["source_mode"],
        "noncanonical-expanded-platform-title-candidates"
    );
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 3);
    assert!(all["total_candidate_links"].as_u64().unwrap() > 0);
    assert!(all["source_records_with_candidate"].as_u64().unwrap() > 0);
    assert_eq!(all["returned_candidate_links"], 3);
    assert_eq!(
        all["total_filtered_candidate_links"],
        all["total_candidate_links"]
    );
    assert!(all["candidates"].as_array().unwrap().iter().all(|row| {
        row["libretro_source_blob_sha"].as_str().unwrap().len() == 40
            && row["wikidata_source_sha256"].as_str().unwrap().len() == 64
            && !row["wikidata_title_row_ordinals"]
                .as_array()
                .unwrap()
                .is_empty()
            && row["interpretation"]
                .as_str()
                .unwrap()
                .contains("not-verified")
    }));

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-expanded-candidates",
            "--platform",
            "all",
            "--wikidata-expanded",
        ],
        vec![
            "--wikidata-expanded-candidates",
            "--platform",
            "all",
            "--qid",
            "Q0",
        ],
        vec![
            "--wikidata-expanded-candidates",
            "--platform",
            "all",
            "--limit",
            "0",
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
fn second_wikidata_console_expansion_is_searchable_and_noncanonical() {
    let source = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v2",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(
        source["source_mode"],
        "pinned-wikidata-expanded-platform-source-text"
    );
    assert_eq!(source["expansion_source"], "v2");
    assert_eq!(source["platforms_searched"].as_array().unwrap().len(), 4);
    assert_eq!(source["source_rows"], 305);
    assert_eq!(source["source_item_platform_observations"], 206);
    assert_eq!(source["literal_publication_date_bindings"], 282);
    assert_eq!(source["nonliteral_publication_bindings"], 0);
    let candidates = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v2",
        "--platform",
        "all",
        "--limit",
        "3",
    ]);
    assert_eq!(candidates["expansion_source"], "v2");
    assert!(candidates["total_candidate_links"].as_u64().unwrap() > 0);
    assert_eq!(candidates["returned_candidate_links"], 3);
    assert!(candidates["candidates"]
        .as_array()
        .unwrap()
        .iter()
        .all(|item| {
            item["interpretation"]
                .as_str()
                .unwrap()
                .contains("not-verified")
                && item["wikidata_source_path"]
                    .as_str()
                    .unwrap()
                    .contains("platform-expansion-v2")
        }));
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-expanded",
            "--expansion-source",
            "v8",
            "--platform",
            "all",
        ],
        vec![
            "--expansion-source",
            "v2",
            "--platform",
            "all",
            "--title",
            "Tetris",
        ],
        vec![
            "--wikidata-expanded",
            "--expansion-source",
            "v2",
            "--platform",
            "atari7800",
        ],
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(
            !result.status.success(),
            "invalid CLI arguments accepted: {args:?}"
        );
    }
}

#[test]
fn third_wikidata_console_expansion_retains_all_original_game_observations() {
    let all = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v3",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(all["expansion_source"], "v3");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 6);
    assert_eq!(all["source_rows"], 1148);
    assert_eq!(all["source_item_platform_observations"], 655);
    assert_eq!(all["literal_publication_date_bindings"], 1114);
    assert_eq!(all["nonliteral_publication_bindings"], 0);
    assert_eq!(all["returned_source_rows"], 2);
    assert!(all["source_rows_evidence"]
        .as_array()
        .unwrap()
        .iter()
        .all(|row| {
            row["source_path"]
                .as_str()
                .unwrap()
                .contains("platform-expansion-v3")
                && row["source_sha256"].as_str().unwrap().len() == 64
                && row["interpretation"]
                    .as_str()
                    .unwrap()
                    .contains("not-canonical")
        }));
    let candidates = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v3",
        "--platform",
        "all",
        "--limit",
        "3",
    ]);
    assert_eq!(candidates["expansion_source"], "v3");
    assert_eq!(
        candidates["platforms_searched"].as_array().unwrap().len(),
        6
    );
    let n = candidates["total_candidate_links"].as_u64().unwrap();
    assert!(n < 100_000);
    assert_eq!(
        candidates["returned_candidate_links"].as_u64().unwrap(),
        n.min(3),
    );
}

#[test]
fn fourth_wikidata_console_expansion_preserves_original_source_text_and_candidates() {
    let all = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v4",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(all["expansion_source"], "v4");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 6);
    assert_eq!(all["source_rows"], 482);
    assert_eq!(all["source_item_platform_observations"], 356);
    assert_eq!(all["literal_publication_date_bindings"], 425);
    assert_eq!(all["nonliteral_publication_bindings"], 0);
    assert_eq!(all["returned_source_rows"], 2);
    let rows = all["source_rows_evidence"].as_array().unwrap();
    assert!(rows.iter().all(|row| {
        row["source_path"]
            .as_str()
            .unwrap()
            .contains("platform-expansion-v4")
            && row["source_sha256"].as_str().unwrap().len() == 64
    }));
    let review = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v4",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(review["expansion_source"], "v4");
    assert_eq!(review["platforms_searched"].as_array().unwrap().len(), 6);
    assert!(review["total_candidate_links"].as_u64().is_some());
    let n = review["total_candidate_links"].as_u64().unwrap();
    assert_eq!(
        review["returned_candidate_links"].as_u64().unwrap(),
        n.min(2)
    );
}

#[test]
fn fifth_expansion_preserves_an_explicit_empty_wikidata_scope() {
    let all = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v5",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(all["expansion_source"], "v5");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 6);
    assert_eq!(all["source_rows"], 35);
    assert_eq!(all["source_item_platform_observations"], 22);
    assert_eq!(all["literal_publication_date_bindings"], 34);
    assert_eq!(all["returned_source_rows"], 2);

    let absent = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v5",
        "--platform",
        "casioloopy",
        "--limit",
        "5",
    ]);
    assert_eq!(absent["source_rows"], 0);
    assert_eq!(absent["source_item_platform_observations"], 0);
    assert_eq!(absent["returned_source_rows"], 0);
    assert_eq!(absent["source_rows_evidence"].as_array().unwrap().len(), 0);

    let candidates = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v5",
        "--platform",
        "all",
        "--limit",
        "3",
    ]);
    assert_eq!(candidates["expansion_source"], "v5");
    assert_eq!(
        candidates["platforms_searched"].as_array().unwrap().len(),
        6
    );
    let n = candidates["total_candidate_links"].as_u64().unwrap();
    assert_eq!(
        candidates["returned_candidate_links"].as_u64().unwrap(),
        n.min(3)
    );
}

#[test]
fn sixth_wikidata_console_source_is_accessible_through_both_cli_modes() {
    let all = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v6",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(all["expansion_source"], "v6");
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 6);
    assert_eq!(all["source_rows"], 662);
    assert_eq!(all["source_item_platform_observations"], 309);
    assert_eq!(all["literal_publication_date_bindings"], 642);
    assert_eq!(all["nonliteral_publication_bindings"], 2);
    assert_eq!(all["returned_source_rows"], 2);
    assert!(all["source_rows_evidence"]
        .as_array()
        .unwrap()
        .iter()
        .all(|item| {
            item["source_path"]
                .as_str()
                .unwrap()
                .contains("platform-expansion-v6")
                && item["source_sha256"].as_str().unwrap().len() == 64
        }));

    let empty = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v6",
        "--platform",
        "tigergamecom",
        "--limit",
        "3",
    ]);
    assert_eq!(empty["source_rows"], 0);
    assert_eq!(empty["returned_source_rows"], 0);
    assert_eq!(empty["source_item_platform_observations"], 0);

    let links = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v6",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(links["expansion_source"], "v6");
    assert_eq!(links["platforms_searched"].as_array().unwrap().len(), 6);
    let total = links["total_candidate_links"].as_u64().unwrap();
    assert_eq!(links["returned_candidate_links"], total.min(2));

    let empty_links = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v6",
        "--platform",
        "tigergamecom",
        "--limit",
        "2",
    ]);
    assert_eq!(empty_links["total_candidate_links"], 0);
    assert_eq!(empty_links["returned_candidate_links"], 0);
}

#[test]
fn seventh_expansion_retains_empty_console_query_scopes() {
    let source = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v7",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(source["expansion_source"], "v7");
    assert_eq!(source["platforms_searched"].as_array().unwrap().len(), 6);
    assert_eq!(source["source_rows"], 20);
    assert_eq!(source["source_item_platform_observations"], 14);
    assert_eq!(source["literal_publication_date_bindings"], 20);
    assert_eq!(source["nonliteral_publication_bindings"], 0);
    assert_eq!(source["returned_source_rows"], 2);

    let empty = query(&[
        "--wikidata-expanded",
        "--expansion-source",
        "v7",
        "--platform",
        "intertonvc4000",
        "--limit",
        "2",
    ]);
    assert_eq!(empty["source_rows"], 0);
    assert_eq!(empty["returned_source_rows"], 0);

    let review = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v7",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(review["expansion_source"], "v7");
    assert_eq!(review["platforms_searched"].as_array().unwrap().len(), 6);
    let total = review["total_candidate_links"].as_u64().unwrap();
    assert_eq!(review["returned_candidate_links"], total.min(2));

    let no_review = query(&[
        "--wikidata-expanded-candidates",
        "--expansion-source",
        "v7",
        "--platform",
        "gameparkgp32",
        "--limit",
        "2",
    ]);
    assert_eq!(no_review["total_candidate_links"], 0);
    assert_eq!(no_review["returned_candidate_links"], 0);
}

#[test]
fn expanded_property_claims_are_verified_offline() {
    let all = query(&[
        "--wikidata-properties",
        "--expanded-credits",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(
        all["source_mode"],
        "verified-wikidata-expanded-property-bindings"
    );
    assert_eq!(all["platforms_searched"].as_array().unwrap().len(), 19);
    assert_eq!(all["source_statements"], 10_269);
    assert_eq!(all["source_item_platform_observations"], 3_150);
    assert_eq!(all["returned_claims"], 2);
    assert!(all["claims"].as_array().unwrap().iter().all(|claim| {
        claim["source_path"]
            .as_str()
            .unwrap()
            .contains("expanded-credits-v1")
            && claim["source_sha256"].as_str().unwrap().len() == 64
    }));
    let psp = query(&[
        "--wikidata-properties",
        "--expanded-credits",
        "--platform",
        "sonyplaystationportable",
        "--property",
        "P178",
        "--limit",
        "1",
    ]);
    assert_eq!(psp["source_statements"], 3_811);
    assert_eq!(psp["source_property_counts"]["P178"], 1063);
    assert_eq!(psp["returned_claims"], 1);
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec!["--expanded-credits", "--platform", "all"],
        vec![
            "--wikidata-properties",
            "--expanded-credits",
            "--with-entity-labels",
            "--platform",
            "all",
        ],
        vec![
            "--wikidata-properties",
            "--expanded-credits",
            "--platform",
            "unknown",
        ],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(!output.status.success(), "accepted invalid args: {args:?}");
    }
}

#[test]
fn expanded_wikidata_metadata_cohorts_are_queryable() {
    let first_credits = query(&[
        "--wikidata-properties",
        "--metadata-cohort",
        "expanded-v1",
        "--platform",
        "all",
        "--limit",
        "1",
    ]);
    assert_eq!(first_credits["metadata_cohort"], "expanded-v1");
    assert_eq!(first_credits["source_statements"], 10_269);
    assert_eq!(first_credits["source_item_platform_observations"], 3_150);

    let second_credits = query(&[
        "--wikidata-properties",
        "--metadata-cohort",
        "expanded-v2",
        "--platform",
        "all",
        "--limit",
        "2",
    ]);
    assert_eq!(
        second_credits["source_mode"],
        "verified-wikidata-expanded-property-bindings"
    );
    assert_eq!(second_credits["metadata_cohort"], "expanded-v2");
    assert_eq!(
        second_credits["platforms_searched"]
            .as_array()
            .unwrap()
            .len(),
        18
    );
    assert_eq!(second_credits["source_statements"], 962);
    assert_eq!(second_credits["source_item_platform_observations"], 312);
    assert_eq!(second_credits["returned_claims"], 2);
    assert!(second_credits["claims"]
        .as_array()
        .unwrap()
        .iter()
        .all(|row| {
            row["source_path"]
                .as_str()
                .unwrap()
                .contains("expanded-credits-v2")
        }));

    for (cohort, statements, observations, count) in [
        ("expanded-v1", 18_999, 3_108, 19),
        ("expanded-v2", 1_461, 303, 18),
    ] {
        let output = query(&[
            "--wikidata-relations",
            "--metadata-cohort",
            cohort,
            "--platform",
            "all",
            "--limit",
            "2",
        ]);
        assert_eq!(output["metadata_cohort"], cohort);
        assert_eq!(output["source_statements"], statements);
        assert_eq!(output["source_item_platform_observations"], observations);
        assert_eq!(
            output["platforms_searched"].as_array().unwrap().len(),
            count
        );
        assert_eq!(output["returned_claims"], 2);
        let expected_path = if cohort == "expanded-v1" {
            "expanded-relations-v1"
        } else {
            "expanded-relations-v2"
        };
        assert!(output["claims"].as_array().unwrap().iter().all(|claim| {
            claim["source_path"]
                .as_str()
                .unwrap()
                .contains(expected_path)
                && claim["source_sha256"].as_str().unwrap().len() == 64
        }));
    }

    let empty = query(&[
        "--wikidata-relations",
        "--metadata-cohort",
        "expanded-v2",
        "--platform",
        "tigergamecom",
        "--limit",
        "2",
    ]);
    assert_eq!(empty["source_statements"], 0);
    assert_eq!(empty["returned_claims"], 0);

    let properties_with_labels = query(&[
        "--wikidata-properties",
        "--metadata-cohort",
        "expanded-v2",
        "--with-entity-labels",
        "--platform",
        "all",
        "--limit",
        "1",
    ]);
    assert_eq!(
        properties_with_labels["entity_label_source"]["entity_qids"],
        2_255
    );
    assert_eq!(
        properties_with_labels["entity_label_source"]["english_labels"],
        2_079
    );
    assert!(
        properties_with_labels["claims"][0]["value_label_evidence"].is_object()
            || properties_with_labels["claims"][0]["value_label_evidence"].is_null()
    );

    let relations_with_labels = query(&[
        "--wikidata-relations",
        "--metadata-cohort",
        "expanded-v1",
        "--with-entity-labels",
        "--platform",
        "all",
        "--limit",
        "1",
    ]);
    assert_eq!(
        relations_with_labels["entity_label_source"]["entity_qids"],
        2_255
    );
    assert_eq!(
        relations_with_labels["entity_label_source"]["english_labels"],
        2_079
    );

    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    for args in [
        vec![
            "--wikidata-properties",
            "--metadata-cohort",
            "expanded-v3",
            "--platform",
            "all",
        ],
        vec!["--metadata-cohort", "expanded-v2", "--platform", "all"],
    ] {
        let result = Command::new(env!("CARGO_BIN_EXE_ludographium"))
            .current_dir(&root)
            .args(&args)
            .output()
            .unwrap();
        assert!(
            !result.status.success(),
            "invalid metadata cohort request accepted: {args:?}"
        );
    }
}
