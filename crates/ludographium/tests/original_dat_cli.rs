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
    assert_eq!(qid["matches"][0]["dates"][0]["value"], "1980-01-01T00:00:00Z");

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

    let list = query(&[
        "--wikidata-text",
        "--platform",
        "atari2600",
        "--limit",
        "1",
    ]);
    assert_eq!(list["query_kind"], "wikidata-source-list");
    assert_eq!(list["returned_matches"], 1);
}
