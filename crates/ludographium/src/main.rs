//! Offline fingerprint lookup CLI. Accepts hashes only; does not open game files.
use ludographium::enrichment::{EnrichedMediaMatch, EnrichedPlatformCatalog};
use ludographium::{CatalogError, MediaMatch, PlatformCatalog};
use serde_json::{json, Value};
use std::env;
use std::error::Error;
use std::path::PathBuf;

fn usage() -> &'static str {
    "Usage: ludographium --platform <snes|gb|gbc|gba|nes|nds> [--root <catalog-directory>] [--enriched] (--sha1 <40-hex> | --crc32 <8-hex> --size <bytes> | --title <substring> [--limit <1..200>])"
}

fn format_match(found: &MediaMatch<'_>) -> Value {
    json!({
        "platform": found.platform,
        "title": found.record.name,
        "region_claim": found.record.region,
        "serial_claim": found.record.serial,
        "rom": {
            "name": found.media.name,
            "size": found.media.size,
            "sha1": found.media.sha1,
            "md5": found.media.md5,
            "crc32": found.media.crc32,
            "serial": found.media.serial,
        },
        "source": {
            "id": found.source.source_id,
            "revision": found.source.revision,
            "path": found.source.path,
            "ordinal": found.record.source_ordinal,
            "blob_sha": found.source.git_blob_sha,
        },
        "interpretation": "source-fingerprint-association-not-verified-game-identity",
    })
}

fn format_enriched_match(found: &EnrichedMediaMatch<'_>) -> Value {
    let mut result = format_match(&found.base);
    if let Value::Object(ref mut map) = result {
        map.insert("metadata_claims".to_owned(), json!(found.metadata_claims));
        map.insert(
            "unresolved_source_claims".to_owned(),
            json!(found.unresolved_source_claims),
        );
    }
    result
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = env::args().skip(1);
    let mut platform = None;
    let mut root = PathBuf::from(".");
    let mut sha1 = None;
    let mut crc32 = None;
    let mut size = None;
    let mut title = None;
    let mut limit: usize = 50;
    let mut limit_explicit = false;
    let mut enriched = false;

    while let Some(arg) = args.next() {
        if arg == "--enriched" {
            enriched = true;
            continue;
        }
        let value = match arg.as_str() {
            "--help" | "-h" => {
                println!("{}", usage());
                return Ok(());
            }
            "--root" | "--platform" | "--sha1" | "--crc32" | "--size" | "--title" | "--limit" => {
                args.next()
                    .ok_or_else(|| CatalogError::Invalid(format!("missing value for {arg}")))?
            }
            _ => {
                return Err(
                    CatalogError::Invalid(format!("unknown option: {arg}\n{}", usage())).into(),
                )
            }
        };
        match arg.as_str() {
            "--root" => root = PathBuf::from(value),
            "--platform" => platform = Some(value),
            "--sha1" => sha1 = Some(value),
            "--crc32" => crc32 = Some(value),
            "--size" => size = Some(value.parse::<u64>()?),
            "--title" => title = Some(value),
            "--limit" => {
                limit = value.parse::<usize>()?;
                limit_explicit = true;
            }
            _ => unreachable!(),
        }
    }

    let platform = platform.ok_or_else(|| CatalogError::Invalid(usage().into()))?;
    let query_modes =
        usize::from(sha1.is_some()) + usize::from(crc32.is_some()) + usize::from(title.is_some());
    if query_modes != 1
        || (crc32.is_some() && size.is_none())
        || (title.is_some() && size.is_some())
        || (title.is_none() && limit_explicit)
        || (title.is_some() && (limit == 0 || limit > 200))
    {
        return Err(CatalogError::Invalid(usage().into()).into());
    }
    let output = if let Some(ref query) = title {
        if enriched {
            let catalog = EnrichedPlatformCatalog::open(&root, &platform)?;
            let results = catalog.search_titles(query, limit)?;
            json!({
                "query_kind": "source-title-substring",
                "total_source_records": results.total_records,
                "enrichment_source": {
                    "id": catalog.source_id(),
                    "revision": catalog.source_revision(),
                },
                "match_count": results.matches.len(),
                "matches": results.matches.iter().map(format_enriched_match).collect::<Vec<_>>(),
            })
        } else {
            let catalog = PlatformCatalog::open(&root, &platform)?;
            let results = catalog.search_titles(query, limit)?;
            let mut matches: Vec<Value> = Vec::new();
            for record in results.records {
                for media in &record.roms {
                    matches.push(format_match(&MediaMatch {
                        platform: catalog.platform(),
                        record,
                        media,
                        source: catalog.source(),
                    }));
                }
            }
            json!({
                "query_kind": "source-title-substring",
                "total_source_records": results.total,
                "match_count": matches.len(),
                "matches": matches,
            })
        }
    } else if enriched {
        let catalog = EnrichedPlatformCatalog::open(&root, &platform)?;
        let found = if let Some(hash) = sha1 {
            let mut matches = catalog.lookup_sha1(&hash)?;
            if let Some(byte_len) = size {
                matches.retain(|m| m.base.media.size == byte_len);
            }
            matches
        } else {
            catalog.lookup_crc32(crc32.as_deref().unwrap(), size.unwrap())?
        };
        json!({
            "enrichment_source": {
                "id": catalog.source_id(),
                "revision": catalog.source_revision(),
            },
            "match_count": found.len(),
            "matches": found.iter().map(format_enriched_match).collect::<Vec<_>>()
        })
    } else {
        let catalog = PlatformCatalog::open(root, &platform)?;
        let found = if let Some(hash) = sha1 {
            let mut matches = catalog.lookup_sha1(&hash)?;
            if let Some(byte_len) = size {
                matches.retain(|m| m.media.size == byte_len);
            }
            matches
        } else {
            catalog.lookup_crc32(crc32.as_deref().unwrap(), size.unwrap())?
        };
        json!({
            "match_count": found.len(),
            "matches": found.iter().map(format_match).collect::<Vec<_>>()
        })
    };
    println!("{}", serde_json::to_string_pretty(&output)?);
    Ok(())
}

fn main() {
    if let Err(err) = run() {
        eprintln!("{err}");
        std::process::exit(1);
    }
}
