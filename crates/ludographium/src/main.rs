//! Offline fingerprint and raw-file lookup CLI. Local input is streamed, not retained.
use ludographium::curated::CuratedCatalog;
use ludographium::enrichment::{EnrichedMediaMatch, EnrichedPlatformCatalog};
use ludographium::{CatalogError, MediaMatch, PlatformCatalog};
use serde_json::{json, Value};
use sha1::{Digest, Sha1};
use std::collections::HashSet;
use std::env;
use std::error::Error;
use std::fs::File;
use std::io::{BufReader, Read};
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

/// Obtain the platform order from the published manifest, never from a
/// hardcoded list that can become stale when a new system is accessioned.
fn registered_platforms(root: &Path) -> Result<Vec<String>, Box<dyn Error>> {
    let raw = std::fs::read(root.join("generated/v1/catalog.json"))?;
    let manifest: Value = serde_json::from_slice(&raw)?;
    if manifest["schema_version"] != 1 || manifest["kind"] != "source-catalog" {
        return Err(CatalogError::Invalid("unsupported platform catalog".into()).into());
    }
    let entries = manifest["platforms"]
        .as_array()
        .ok_or_else(|| CatalogError::Invalid("catalog platform list is missing".into()))?;
    if entries.is_empty() {
        return Err(CatalogError::Invalid("catalog has no platforms".into()).into());
    }
    let mut ids = Vec::new();
    let mut seen = HashSet::new();
    for entry in entries {
        let id = entry["platform"]
            .as_str()
            .ok_or_else(|| CatalogError::Invalid("invalid registered platform".into()))?;
        if id.is_empty()
            || !id
                .bytes()
                .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
            || !seen.insert(id.to_owned())
            || entry["artifact_path"] != format!("generated/v1/{id}.json")
        {
            return Err(
                CatalogError::Invalid("duplicate or unsafe registered platform".into()).into(),
            );
        }
        ids.push(id.to_owned());
    }
    Ok(ids)
}

/// Compute a local input fingerprint *once* for all-platform search.
/// No game file is retained, normalized, or copied to the metadata catalog.
fn exact_file_hash(path: &str) -> Result<(String, u64), Box<dyn Error>> {
    let mut input = BufReader::new(File::open(path)?);
    let mut digest = Sha1::new();
    let mut bytes = 0u64;
    let mut buffer = [0u8; 65536];
    loop {
        let n = input.read(&mut buffer)?;
        if n == 0 {
            break;
        }
        bytes = bytes
            .checked_add(n as u64)
            .ok_or_else(|| CatalogError::Invalid("local input byte length overflows u64".into()))?;
        digest.update(&buffer[..n]);
    }
    Ok((format!("{:X}", digest.finalize()), bytes))
}

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
    let platforms = registered_platforms(root)?;
    let file_hash = if let Some(path) = file {
        Some(exact_file_hash(path)?)
    } else {
        None
    };
    let effective_hash = sha1.or_else(|| file_hash.as_ref().map(|(hash, _)| hash.as_str()));
    let effective_size = size.or_else(|| file_hash.as_ref().map(|(_, bytes)| *bytes));
    let mut matches = Vec::new();
    let mut title_record_total = 0usize;
    let mut enrichment_sources = Vec::new();

    for platform in &platforms {
        if enriched {
            let catalog = EnrichedPlatformCatalog::open(root, platform)?;
            enrichment_sources.push(json!({
                "platform": platform,
                "id": catalog.source_id(),
                "revision": catalog.source_revision()
            }));
            if let Some(query) = title {
                let remaining = limit.saturating_sub(title_record_total.min(limit));
                let result = catalog.search_titles(query, remaining.max(1))?;
                title_record_total += result.total_records;
                if remaining != 0 {
                    matches.extend(
                        result.matches.iter().map(|hit| {
                            with_curated(format_enriched_match(hit), &hit.base, curated)
                        }),
                    );
                }
            } else {
                let found = if let Some(hash) = effective_hash {
                    catalog.lookup_sha1(hash)?
                } else {
                    catalog.lookup_crc32(crc32.unwrap(), effective_size.unwrap())?
                };
                matches.extend(
                    found
                        .iter()
                        .filter(|hit| effective_size.is_none_or(|n| hit.base.media.size == n))
                        .map(|hit| with_curated(format_enriched_match(hit), &hit.base, curated)),
                );
            }
        } else {
            let catalog = PlatformCatalog::open(root, platform)?;
            if let Some(query) = title {
                let remaining = limit.saturating_sub(title_record_total.min(limit));
                let result = catalog.search_titles(query, remaining.max(1))?;
                title_record_total += result.total;
                if remaining != 0 {
                    for record in result.records {
                        for media in &record.roms {
                            let hit = MediaMatch {
                                platform: catalog.platform(),
                                record,
                                media,
                                source: catalog.source(),
                            };
                            matches.push(with_curated(format_match(&hit), &hit, curated));
                        }
                    }
                }
            } else {
                let found = if let Some(hash) = effective_hash {
                    catalog.lookup_sha1(hash)?
                } else {
                    catalog.lookup_crc32(crc32.unwrap(), effective_size.unwrap())?
                };
                matches.extend(
                    found
                        .iter()
                        .filter(|hit| effective_size.is_none_or(|n| hit.media.size == n))
                        .map(|hit| with_curated(format_match(hit), hit, curated)),
                );
            }
        }
    }
    let mut output = json!({
        "platform_scope": "all-registered",
        "platforms_searched": platforms,
        "match_count": matches.len(),
        "matches": matches
    });
    if let Some(obj) = output.as_object_mut() {
        if title.is_some() {
            obj.insert("query_kind".into(), json!("source-title-substring"));
            obj.insert("total_source_records".into(), json!(title_record_total));
        } else {
            obj.insert(
                "input_kind".into(),
                json!(if file.is_some() {
                    "exact-local-file-bytes"
                } else {
                    "fingerprint"
                }),
            );
        }
        if enriched {
            obj.insert("enrichment_sources".into(), json!(enrichment_sources));
        }
    }
    Ok(output)
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
