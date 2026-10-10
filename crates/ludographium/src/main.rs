//! Offline fingerprint and raw-file lookup CLI. Local input is streamed, not retained.
use ludographium::collection::{
    fingerprint_zip, fingerprint_zip_normalized, fingerprint_zip_normalized_selected,
    CatalogCollection, EnrichedCatalogCollection,
};
use ludographium::curated::CuratedCatalog;
use ludographium::enrichment::{EnrichedMediaMatch, EnrichedPlatformCatalog};
use ludographium::media::{fingerprint_normalized, MediaFormat};
use ludographium::original_dat::OriginalDatCatalog;
use ludographium::runtime::verify_runtime_root;
use ludographium::{CatalogError, MediaMatch, PlatformCatalog};
use serde_json::{json, Value};
use std::env;
use std::error::Error;
use std::fs::File;
use std::io::BufReader;
use std::path::{Path, PathBuf};

fn usage() -> &'static str {
    "Usage: ludographium --verify-runtime [--root <catalog-directory>] | ludographium --platform <platform-id|all> [--root <catalog-directory>] [--source-dat] [--enriched] [--curated] (--sha1 <40-hex> | --crc32 <8-hex> --size <bytes> | --title <substring> [--limit <1..200>] | --file <path> | --zip <archive.zip>) [--media-format <nes-ines|snes-copier512|n64-v64|n64-n64>] [--zip-entry <exact-member-name>]"
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
            (
                collection.lookup_reader(BufReader::new(File::open(path)?))?,
                None,
            )
        } else if let Some(hash) = sha1 {
            (collection.lookup_sha1(hash)?, None)
        } else {
            (
                collection.lookup_crc32(crc32.unwrap(), size.unwrap())?,
                None,
            )
        };
        if title.is_none() && file.is_none() {
            if let Some(expected) = size {
                found.retain(|hit| hit.base.media.size == expected);
            }
        }
        let matches: Vec<Value> = found
            .iter()
            .map(|hit| with_curated(format_enriched_match(hit), &hit.base, curated))
            .collect();
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
            (
                collection.lookup_reader(BufReader::new(File::open(path)?))?,
                None,
            )
        } else if let Some(hash) = sha1 {
            (collection.lookup_sha1(hash)?, None)
        } else {
            (
                collection.lookup_crc32(crc32.unwrap(), size.unwrap())?,
                None,
            )
        };
        if title.is_none() && file.is_none() {
            if let Some(expected) = size {
                found.retain(|hit| hit.media.size == expected);
            }
        }
        let matches: Vec<Value> = found
            .iter()
            .map(|hit| with_curated(format_match(hit), hit, curated))
            .collect();
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

fn zip_entry(name: &str, hash: &str, bytes: u64, matches: Vec<Value>) -> Value {
    json!({
        "entry_name": name,
        "sha1": hash,
        "size": bytes,
        "match_count": matches.len(),
        "matches": matches,
    })
}

/// All members must satisfy the explicitly selected transformation.
/// Their original decoded lengths remain visible; reported SHA-1 digests and
/// match sizes are for the converted bytes, not the ZIP entry's raw bytes.
fn lookup_zip_normalized_mode(
    root: &Path,
    platform: &str,
    path: &str,
    format: MediaFormat,
    selected_entry: Option<&str>,
    enriched: bool,
    curated: Option<&CuratedCatalog>,
) -> Result<Value, Box<dyn Error>> {
    let fingerprints = if let Some(entry) = selected_entry {
        fingerprint_zip_normalized_selected(BufReader::new(File::open(path)?), format, entry)?
    } else {
        fingerprint_zip_normalized(BufReader::new(File::open(path)?), format)?
    };
    let mut members = Vec::new();
    let mut source = None;
    if enriched {
        let catalog = EnrichedPlatformCatalog::open(root, platform)?;
        source = Some(json!({
            "id": catalog.source_id(),
            "revision": catalog.source_revision(),
        }));
        for member in fingerprints {
            let matches: Vec<Value> = catalog
                .lookup_sha1(&member.normalized.sha1)?
                .into_iter()
                .filter(|hit| hit.base.media.size == member.normalized.size)
                .map(|hit| with_curated(format_enriched_match(&hit), &hit.base, curated))
                .collect();
            members.push(json!({
                "entry_name": member.entry_name,
                "original_size": member.original_size,
                "normalized_sha1": member.normalized.sha1,
                "normalized_size": member.normalized.size,
                "match_count": matches.len(),
                "matches": matches,
            }));
        }
    } else {
        let catalog = PlatformCatalog::open(root, platform)?;
        for member in fingerprints {
            let matches: Vec<Value> = catalog
                .lookup_sha1(&member.normalized.sha1)?
                .into_iter()
                .filter(|hit| hit.media.size == member.normalized.size)
                .map(|hit| with_curated(format_match(&hit), &hit, curated))
                .collect();
            members.push(json!({
                "entry_name": member.entry_name,
                "original_size": member.original_size,
                "normalized_sha1": member.normalized.sha1,
                "normalized_size": member.normalized.size,
                "match_count": matches.len(),
                "matches": matches,
            }));
        }
    }
    let match_count: usize = members
        .iter()
        .map(|member: &Value| member["match_count"].as_u64().unwrap_or(0) as usize)
        .sum();
    let mut result = json!({
        "input_kind": "explicit-normalized-zip-members",
        "media_format": format.name(),
        "platform_scope": "selected",
        "platforms_searched": [platform],
        "member_count": members.len(),
        "match_count": match_count,
        "members": members,
    });
    if let Some(source) = source {
        result["enrichment_source"] = source;
    }
    Ok(result)
}

/// Fingerprint ZIP members in memory-bounded streams; never extract to disk.
/// Each member remains a separate candidate with its own original archive name.
fn lookup_zip_mode(
    root: &Path,
    platform: &str,
    path: &str,
    enriched: bool,
    curated: Option<&CuratedCatalog>,
) -> Result<Value, Box<dyn Error>> {
    let mut members = Vec::new();
    let mut platforms = Vec::new();
    let mut enrichment_sources = Vec::new();
    if platform == "all" {
        if enriched {
            let all = EnrichedCatalogCollection::open(root)?;
            platforms = all.platform_ids().map(ToOwned::to_owned).collect();
            enrichment_sources = all
                .enrichment_sources()
                .map(|(p, id, revision)| json!({"platform":p, "id":id, "revision":revision}))
                .collect();
            for found in all.lookup_zip(BufReader::new(File::open(path)?))? {
                let matches = found
                    .matches
                    .iter()
                    .map(|hit| with_curated(format_enriched_match(hit), &hit.base, curated))
                    .collect();
                members.push(zip_entry(
                    &found.member.entry_name,
                    &found.member.sha1,
                    found.member.size,
                    matches,
                ));
            }
        } else {
            let all = CatalogCollection::open(root)?;
            platforms = all.platform_ids().map(ToOwned::to_owned).collect();
            for found in all.lookup_zip(BufReader::new(File::open(path)?))? {
                let matches = found
                    .matches
                    .iter()
                    .map(|hit| with_curated(format_match(hit), hit, curated))
                    .collect();
                members.push(zip_entry(
                    &found.member.entry_name,
                    &found.member.sha1,
                    found.member.size,
                    matches,
                ));
            }
        }
    } else if enriched {
        let catalog = EnrichedPlatformCatalog::open(root, platform)?;
        platforms.push(platform.to_owned());
        enrichment_sources.push(json!({
            "platform": platform,
            "id": catalog.source_id(),
            "revision": catalog.source_revision()
        }));
        for member in fingerprint_zip(BufReader::new(File::open(path)?))? {
            let matches = catalog
                .lookup_sha1(&member.sha1)?
                .iter()
                .filter(|hit| hit.base.media.size == member.size)
                .map(|hit| with_curated(format_enriched_match(hit), &hit.base, curated))
                .collect();
            members.push(zip_entry(
                &member.entry_name,
                &member.sha1,
                member.size,
                matches,
            ));
        }
    } else {
        let catalog = PlatformCatalog::open(root, platform)?;
        platforms.push(platform.to_owned());
        for member in fingerprint_zip(BufReader::new(File::open(path)?))? {
            let matches = catalog
                .lookup_sha1(&member.sha1)?
                .iter()
                .filter(|hit| hit.media.size == member.size)
                .map(|hit| with_curated(format_match(hit), hit, curated))
                .collect();
            members.push(zip_entry(
                &member.entry_name,
                &member.sha1,
                member.size,
                matches,
            ));
        }
    }
    let match_count: usize = members
        .iter()
        .map(|entry: &Value| entry["match_count"].as_u64().unwrap_or(0) as usize)
        .sum();
    let mut result = json!({
        "input_kind": "read-only-zip-members",
        "platform_scope": if platform == "all" { "all-registered" } else { "selected" },
        "platforms_searched": platforms,
        "member_count": members.len(),
        "match_count": match_count,
        "members": members,
    });
    if enriched {
        result["enrichment_sources"] = json!(enrichment_sources);
    }
    Ok(result)
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
    let mut zip = None;
    let mut zip_entry = None;
    let mut media_format = None;
    let mut limit: usize = 50;
    let mut limit_explicit = false;
    let mut enriched = false;
    let mut show_curated = false;
    let mut verify_runtime = false;
    let mut source_dat = false;

    while let Some(arg) = args.next() {
        if arg == "--source-dat" {
            source_dat = true;
            continue;
        }
        if arg == "--verify-runtime" {
            verify_runtime = true;
            continue;
        }
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
            | "--file" | "--zip" | "--media-format" | "--zip-entry" => args
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
            "--zip" => zip = Some(value),
            "--zip-entry" => zip_entry = Some(value),
            "--media-format" => media_format = Some(MediaFormat::parse(&value)?),
            "--limit" => {
                limit = value.parse::<usize>()?;
                limit_explicit = true;
            }
            _ => unreachable!(),
        }
    }

    if verify_runtime {
        if platform.is_some()
            || sha1.is_some()
            || crc32.is_some()
            || size.is_some()
            || title.is_some()
            || file.is_some()
            || zip.is_some()
            || zip_entry.is_some()
            || media_format.is_some()
            || limit_explicit
            || enriched
            || show_curated
            || source_dat
        {
            return Err(CatalogError::Invalid(
                "--verify-runtime accepts only the optional --root directory".into(),
            )
            .into());
        }
        let checked = verify_runtime_root(&root)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "verified": true,
                "input_kind": "runtime-root",
                "artifact_count": checked.artifact_count,
                "total_artifact_bytes": checked.total_artifact_bytes,
                "source_id": checked.source_id,
                "source_revision": checked.source_revision,
            }))?
        );
        return Ok(());
    }

    let platform = platform.ok_or_else(|| CatalogError::Invalid(usage().into()))?;
    let query_modes = usize::from(sha1.is_some())
        + usize::from(crc32.is_some())
        + usize::from(title.is_some())
        + usize::from(file.is_some())
        + usize::from(zip.is_some());
    if query_modes != 1
        || (crc32.is_some() && size.is_none())
        || (title.is_some() && size.is_some())
        || (file.is_some() && (size.is_some() || limit_explicit))
        || (zip.is_some() && (size.is_some() || limit_explicit))
        || (title.is_none() && limit_explicit)
        || (title.is_some() && (limit == 0 || limit > 200))
        || (zip_entry.is_some()
            && (zip.is_none() || media_format.is_none() || zip_entry.as_deref() == Some("")))
    {
        return Err(CatalogError::Invalid(usage().into()).into());
    }
    if let Some(format) = media_format {
        if (file.is_none() && zip.is_none()) || platform != format.platform() {
            return Err(CatalogError::Invalid(format!(
                "--media-format {} requires --platform {} and --file or --zip",
                format.name(),
                format.platform()
            ))
            .into());
        }
    }
    if source_dat {
        if show_curated
            || zip.is_some()
            || media_format.is_some()
            || zip_entry.is_some()
        {
            return Err(CatalogError::Invalid(
                "--source-dat does not support --curated, --zip or --media-format".into(),
            ).into());
        }
        let catalog = if enriched {
            OriginalDatCatalog::open(&root, &platform)?.with_enrichment(&root)?
        } else {
            OriginalDatCatalog::open(&root, &platform)?
        };
        let all = catalog.platform_ids().collect::<Vec<_>>();
        let (count, matches) = if let Some(ref name) = title {
            let (total, values) = catalog.search_titles(name, limit)?;
            (Some(total), values)
        } else if let Some(ref hash) = sha1 {
            (None, catalog.lookup_sha1(hash, size)?)
        } else if let Some(ref path) = file {
            (
                None,
                catalog.lookup_reader(BufReader::new(File::open(path)?))?,
            )
        } else {
            (
                None,
                catalog.lookup_crc32(crc32.as_deref().unwrap(), size.unwrap())?,
            )
        };
        let mut output = json!({
            "source_mode": "original-dat-text",
            "platforms_searched": all,
            "match_count": matches.len(),
            "matches": matches,
            "interpretation": "original-source-observations-not-canonical-identities"
        });
        if enriched {
            output["field_claim_resolution_counts"] = json!(catalog.claim_resolution_counts());
            output["bibliographic_mode"] = json!("verified-original-field-dat-text");
        }
        if let Some(total) = count {
            output["query_kind"] = json!("source-title-substring");
            output["total_source_records"] = json!(total);
        } else {
            output["input_kind"] = json!(if file.is_some() {
                "exact-local-file-bytes"
            } else {
                "fingerprint"
            });
        }
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
    }
    let curated = if show_curated {
        Some(CuratedCatalog::open(&root)?)
    } else {
        None
    };
    if let Some(format) = media_format {
        if let Some(ref archive_path) = zip {
            let output = lookup_zip_normalized_mode(
                &root,
                &platform,
                archive_path,
                format,
                zip_entry.as_deref(),
                enriched,
                curated.as_ref(),
            )?;
            println!("{}", serde_json::to_string_pretty(&output)?);
            return Ok(());
        }
        let input_path = file.as_ref().unwrap();
        let fingerprint = fingerprint_normalized(BufReader::new(File::open(input_path)?), format)?;
        let output = if enriched {
            let catalog = EnrichedPlatformCatalog::open(&root, &platform)?;
            let matches: Vec<Value> = catalog
                .lookup_sha1(&fingerprint.sha1)?
                .into_iter()
                .filter(|hit| hit.base.media.size == fingerprint.size)
                .map(|hit| with_curated(format_enriched_match(&hit), &hit.base, curated.as_ref()))
                .collect();
            json!({
                "input_kind": "explicit-normalized-local-file-bytes",
                "media_format": fingerprint.media_format,
                "normalized_sha1": fingerprint.sha1,
                "normalized_size": fingerprint.size,
                "enrichment_source": {
                    "id": catalog.source_id(),
                    "revision": catalog.source_revision(),
                },
                "match_count": matches.len(),
                "matches": matches,
            })
        } else {
            let catalog = PlatformCatalog::open(&root, &platform)?;
            let matches: Vec<Value> = catalog
                .lookup_sha1(&fingerprint.sha1)?
                .into_iter()
                .filter(|hit| hit.media.size == fingerprint.size)
                .map(|hit| with_curated(format_match(&hit), &hit, curated.as_ref()))
                .collect();
            json!({
                "input_kind": "explicit-normalized-local-file-bytes",
                "media_format": fingerprint.media_format,
                "normalized_sha1": fingerprint.sha1,
                "normalized_size": fingerprint.size,
                "match_count": matches.len(),
                "matches": matches,
            })
        };
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
    }
    if let Some(ref archive_path) = zip {
        let output = lookup_zip_mode(&root, &platform, archive_path, enriched, curated.as_ref())?;
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
    }
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
