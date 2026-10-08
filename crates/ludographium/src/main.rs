//! Offline fingerprint and raw-file lookup CLI. Local input is streamed, not retained.
use ludographium::collection::{CatalogCollection, EnrichedCatalogCollection};
use ludographium::curated::CuratedCatalog;
use ludographium::enrichment::{EnrichedMediaMatch, EnrichedPlatformCatalog};
use ludographium::{CatalogError, MediaMatch, PlatformCatalog};
use serde_json::{json, Value};
use std::env;
use std::error::Error;
use std::fs::File;
use std::io::BufReader;
use std::path::{Path, PathBuf};

fn usage() -> &'static str {
    "Usage: ludographium --platform <platform-id|all> [--root <catalog-directory>] [--enriched] [--curated] (--sha1 <40-hex> | --crc32 <8-hex> --size <bytes> | --title <substring> [--limit <1..200>] | --file <path>)"
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

/// Add manually curated work/release/build identities only when exact source
/// provenance and fingerprint both match a validated curated build.
fn with_curated(
    mut output: Value,
    found: &MediaMatch<'_>,
    curated: Option<&CuratedCatalog>,
) -> Value {
    if let Some(catalog) = curated {
        let identities: Vec<Value> = catalog
            .for_media(found)
            .iter()
            .map(|identity| {
                json!({
                    "work": identity.work,
                    "release": identity.release,
                    "build": identity.build,
                })
            })
            .collect();
        if let Value::Object(ref mut map) = output {
            map.insert("curated_identities".into(), json!(identities));
        }
    }
    output
}

/// The CLI uses the same collection APIs available to emulator frontends.
/// Local media is hashed once; no title-based or platform-based identity merging occurs.
#[allow(clippy::too_many_arguments)]
fn lookup_all_platforms(
    root: &Path,
    sha1: Option<&str>,
    crc32: Option<&str>,
    size: Option<u64>,
    title: Option<&str>,
    file: Option<&str>,
    limit: usize,
    enriched: bool,
    curated: Option<&CuratedCatalog>,
) -> Result<Value, Box<dyn Error>> {
    if enriched {
        let collection = EnrichedCatalogCollection::open(root)?;
        let platforms: Vec<&str> = collection.platform_ids().collect();
        let source_info: Vec<Value> = collection.enrichment_sources().map(|(platform, id, revision)| {
            json!({ "platform": platform, "id": id, "revision": revision })
        }).collect();
        let (mut found, total) = if let Some(query) = title {
            let result = collection.search_titles(query, limit)?;
            (result.matches, Some(result.total_source_records))
        } else if let Some(path) = file {
            (collection.lookup_reader(BufReader::new(File::open(path)?))?, None)
        } else if let Some(hash) = sha1 {
            (collection.lookup_sha1(hash)?, None)
        } else {
            (collection.lookup_crc32(crc32.unwrap(), size.unwrap())?, None)
        };
        if title.is_none() && file.is_none() {
            if let Some(expected) = size {
                found.retain(|hit| hit.base.media.size == expected);
            }
        }
        let matches: Vec<Value> = found.iter().map(|hit| {
            with_curated(format_enriched_match(hit), &hit.base, curated)
        }).collect();
        let mut output = json!({
            "platform_scope": "all-registered",
            "platforms_searched": platforms,
            "enrichment_sources": source_info,
            "match_count": matches.len(),
            "matches": matches
        });
        if let Some(total) = total {
            output["query_kind"] = json!("source-title-substring");
            output["total_source_records"] = json!(total);
        } else {
            output["input_kind"] = json!(if file.is_some() {
                "exact-local-file-bytes"
            } else {
                "fingerprint"
            });
        }
        Ok(output)
    } else {
        let collection = CatalogCollection::open(root)?;
        let platforms: Vec<&str> = collection.platform_ids().collect();
        let (mut found, total) = if let Some(query) = title {
            let result = collection.search_titles(query, limit)?;
            (result.matches, Some(result.total_source_records))
        } else if let Some(path) = file {
            (collection.lookup_reader(BufReader::new(File::open(path)?))?, None)
        } else if let Some(hash) = sha1 {
            (collection.lookup_sha1(hash)?, None)
        } else {
            (collection.lookup_crc32(crc32.unwrap(), size.unwrap())?, None)
        };
        if title.is_none() && file.is_none() {
            if let Some(expected) = size {
                found.retain(|hit| hit.media.size == expected);
            }
        }
        let matches: Vec<Value> = found.iter().map(|hit| {
            with_curated(format_match(hit), hit, curated)
        }).collect();
        let mut output = json!({
            "platform_scope": "all-registered",
            "platforms_searched": platforms,
            "match_count": matches.len(),
            "matches": matches
        });
        if let Some(total) = total {
            output["query_kind"] = json!("source-title-substring");
            output["total_source_records"] = json!(total);
        } else {
            output["input_kind"] = json!(if file.is_some() {
                "exact-local-file-bytes"
            } else {
                "fingerprint"
            });
        }
        Ok(output)
    }
}

fn run() -> Result<(), Box<dyn Error>> {
    let mut args = env::args().skip(1);
    let mut platform = None;
    let mut root = PathBuf::from(".");
    let mut sha1 = None;
    let mut crc32 = None;
    let mut size = None;
    let mut title = None;
    let mut file = None;
    let mut limit: usize = 50;
    let mut limit_explicit = false;
    let mut enriched = false;
    let mut show_curated = false;

    while let Some(arg) = args.next() {
        if arg == "--enriched" {
            enriched = true;
            continue;
        }
        if arg == "--curated" {
            show_curated = true;
            continue;
        }
        let value = match arg.as_str() {
            "--help" | "-h" => {
                println!("{}", usage());
                return Ok(());
            }
            "--root" | "--platform" | "--sha1" | "--crc32" | "--size" | "--title" | "--limit"
            | "--file" => args
                .next()
                .ok_or_else(|| CatalogError::Invalid(format!("missing value for {arg}")))?,
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
            "--file" => file = Some(value),
            "--limit" => {
                limit = value.parse::<usize>()?;
                limit_explicit = true;
            }
            _ => unreachable!(),
        }
    }

    let platform = platform.ok_or_else(|| CatalogError::Invalid(usage().into()))?;
    let query_modes = usize::from(sha1.is_some())
        + usize::from(crc32.is_some())
        + usize::from(title.is_some())
        + usize::from(file.is_some());
    if query_modes != 1
        || (crc32.is_some() && size.is_none())
        || (title.is_some() && size.is_some())
        || (file.is_some() && (size.is_some() || limit_explicit))
        || (title.is_none() && limit_explicit)
        || (title.is_some() && (limit == 0 || limit > 200))
    {
        return Err(CatalogError::Invalid(usage().into()).into());
    }
    let curated = if show_curated {
        Some(CuratedCatalog::open(&root)?)
    } else {
        None
    };
    if platform == "all" {
        let output = lookup_all_platforms(
            &root,
            sha1.as_deref(),
            crc32.as_deref(),
            size,
            title.as_deref(),
            file.as_deref(),
            limit,
            enriched,
            curated.as_ref(),
        )?;
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
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
                "matches": results.matches.iter().map(|hit| {
                    with_curated(format_enriched_match(hit), &hit.base, curated.as_ref())
                }).collect::<Vec<_>>(),
            })
        } else {
            let catalog = PlatformCatalog::open(&root, &platform)?;
            let results = catalog.search_titles(query, limit)?;
            let mut matches: Vec<Value> = Vec::new();
            for record in results.records {
                for media in &record.roms {
                    let hit = MediaMatch {
                        platform: catalog.platform(),
                        record,
                        media,
                        source: catalog.source(),
                    };
                    matches.push(with_curated(format_match(&hit), &hit, curated.as_ref()));
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
        } else if let Some(ref path) = file {
            catalog.lookup_reader(BufReader::new(File::open(path)?))?
        } else {
            catalog.lookup_crc32(crc32.as_deref().unwrap(), size.unwrap())?
        };
        json!({
            "input_kind": if file.is_some() { "exact-local-file-bytes" } else { "fingerprint" },
            "enrichment_source": {
                "id": catalog.source_id(),
                "revision": catalog.source_revision(),
            },
            "match_count": found.len(),
            "matches": found.iter().map(|hit| {
                with_curated(format_enriched_match(hit), &hit.base, curated.as_ref())
            }).collect::<Vec<_>>()
        })
    } else {
        let catalog = PlatformCatalog::open(root, &platform)?;
        let found = if let Some(hash) = sha1 {
            let mut matches = catalog.lookup_sha1(&hash)?;
            if let Some(byte_len) = size {
                matches.retain(|m| m.media.size == byte_len);
            }
            matches
        } else if let Some(ref path) = file {
            catalog.lookup_reader(BufReader::new(File::open(path)?))?
        } else {
            catalog.lookup_crc32(crc32.as_deref().unwrap(), size.unwrap())?
        };
        json!({
            "input_kind": if file.is_some() { "exact-local-file-bytes" } else { "fingerprint" },
            "match_count": found.len(),
            "matches": found.iter().map(|hit| {
                with_curated(format_match(hit), hit, curated.as_ref())
            }).collect::<Vec<_>>()
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
