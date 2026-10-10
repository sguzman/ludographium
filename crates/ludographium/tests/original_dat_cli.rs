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
