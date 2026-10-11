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
use ludographium::wikidata_authority_ids::WikidataAuthorityIdCatalog;
use ludographium::wikidata_candidates::WikidataCandidateCatalog;
use ludographium::wikidata_credits::WikidataCreditAudit;
use ludographium::wikidata_entity_labels::WikidataEntityLabelCatalog;
use ludographium::wikidata_gamefaqs_qualifiers::GameFaqsQualifierCatalog;
use ludographium::wikidata_items::WikidataItemProjection;
use ludographium::wikidata_localized_candidates::WikidataLocalizedCandidateCatalog;
use ludographium::wikidata_localized_titles::WikidataLocalizedTitleCatalog;
use ludographium::wikidata_platform_expansion::ExpandedWikidataCatalog;
use ludographium::wikidata_properties::WikidataPropertyCatalog;
use ludographium::wikidata_relations::WikidataRelationCatalog;
use ludographium::wikidata_text::WikidataTextCatalog;
use ludographium::wikidata_years::WikidataYearAudit;
use ludographium::{CatalogError, MediaMatch, PlatformCatalog};
use serde_json::{json, Value};
use std::env;
use std::error::Error;
use std::fs::File;
use std::io::BufReader;
use std::path::{Path, PathBuf};

fn usage() -> &'static str {
    "Usage: ludographium --verify-runtime [--root <catalog-directory>] | ludographium --wikidata-expanded --platform <atari7800|sonyplaystationportable|sonyplaystationvita|all> [--root <catalog-directory>] [--qid <QID> | --title <substring>] [--limit <1..200>] | ludographium --wikidata-localized-candidates --platform <wikidata-platform-id|all> [--qid <QID> | --title <substring>] [--limit <1..200>] | ludographium --wikidata-localized-titles --platform <wikidata-platform-id|all> [--qid <QID> | --title <substring>] [--language <language-prefix-or-tag>] [--limit <1..200>] | ludographium --wikidata-gamefaqs-qualifiers --platform <wikidata-platform-id|all> [--qid <QID>] [--external-id <exact-gamefaqs-id>] [--limit <1..200>] | ludographium --wikidata-authority-ids --platform <wikidata-platform-id|all> [--qid <QID>] [--property <P11688|P1933|P4769|P2816|P1712|P2864|P2606|P2451|P4857>] [--external-id <exact-provider-id> --property <one-of-above>] [--limit <1..200>] | ludographium --wikidata-relations [--with-entity-labels] --platform <wikidata-platform-id|all> [--external-id <exact-provider-id> --property <P1733|P2725>] [--qid <QID>] [--property <P179|P404|P407|P495|P437|P750|P1476|P1733|P2725>] [--limit <1..200>] | ludographium --wikidata-items --platform <wikidata-platform-id|all> [--qid <QID> | --title <substring>] [--limit <1..200>] | ludographium --wikidata-properties [--with-entity-labels] --platform <wikidata-platform-id|all> [--qid <QID>] [--property <P178|P123|P136>] [--limit <1..200>] | ludographium --wikidata-candidates [--compare-years] [--compare-credits] --platform <wikidata-platform-id|all> [--root <catalog-directory>] [--qid <QID> | --title <substring>] [--limit <1..200>] | ludographium --wikidata-text --platform <platform-id|all> [--root <catalog-directory>] [--qid <QID> | --title <substring>] [--limit <1..200>] | ludographium --source-dat --enriched --claims --platform <platform-id|all> [--root <catalog-directory>] [--title <substring>] [--limit <1..200>] | ludographium --platform <platform-id|all> [--root <catalog-directory>] [--source-dat] [--enriched] [--curated] (--sha1 <40-hex> | --crc32 <8-hex> --size <bytes> | --title <substring> [--limit <1..200>] | --file <path> | --zip <archive.zip>) [--media-format <nes-ines|snes-copier512|n64-v64|n64-n64>] [--zip-entry <exact-member-name>]"
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
    let mut claims_only = false;
    let mut wikidata_text = false;
    let mut wikidata_expanded = false;
    let mut wikidata_candidates = false;
    let mut wikidata_localized_candidates = false;
    let mut wikidata_properties = false;
    let mut wikidata_relations = false;
    let mut wikidata_authority_ids = false;
    let mut wikidata_gamefaqs_qualifiers = false;
    let mut wikidata_items = false;
    let mut wikidata_localized_titles = false;
    let mut language = None;
    let mut with_entity_labels = false;
    let mut property = None;
    let mut external_id = None;
    let mut compare_years = false;
    let mut compare_credits = false;
    let mut qid = None;

    while let Some(arg) = args.next() {
        if arg == "--source-dat" {
            source_dat = true;
            continue;
        }
        if arg == "--claims" {
            claims_only = true;
            continue;
        }
        if arg == "--wikidata-text" {
            wikidata_text = true;
            continue;
        }
        if arg == "--wikidata-expanded" {
            wikidata_expanded = true;
            continue;
        }
        if arg == "--wikidata-candidates" {
            wikidata_candidates = true;
            continue;
        }
        if arg == "--wikidata-localized-candidates" {
            wikidata_localized_candidates = true;
            continue;
        }
        if arg == "--wikidata-properties" {
            wikidata_properties = true;
            continue;
        }
        if arg == "--wikidata-relations" {
            wikidata_relations = true;
            continue;
        }
        if arg == "--wikidata-authority-ids" {
            wikidata_authority_ids = true;
            continue;
        }
        if arg == "--wikidata-gamefaqs-qualifiers" {
            wikidata_gamefaqs_qualifiers = true;
            continue;
        }
        if arg == "--wikidata-items" {
            wikidata_items = true;
            continue;
        }
        if arg == "--wikidata-localized-titles" {
            wikidata_localized_titles = true;
            continue;
        }
        if arg == "--with-entity-labels" {
            with_entity_labels = true;
            continue;
        }
        if arg == "--compare-years" {
            compare_years = true;
            continue;
        }
        if arg == "--compare-credits" {
            compare_credits = true;
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
            | "--file" | "--zip" | "--media-format" | "--zip-entry" | "--qid" | "--property"
            | "--external-id" | "--language" => args
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
            "--qid" => qid = Some(value),
            "--property" => property = Some(value),
            "--external-id" => external_id = Some(value),
            "--language" => language = Some(value),
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
            || claims_only
            || wikidata_text
            || wikidata_expanded
            || wikidata_candidates
            || wikidata_properties
            || wikidata_relations
            || wikidata_authority_ids
            || wikidata_gamefaqs_qualifiers
            || wikidata_items
            || wikidata_localized_titles
            || language.is_some()
            || with_entity_labels
            || property.is_some()
            || external_id.is_some()
            || compare_years
            || compare_credits
            || qid.is_some()
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

    if wikidata_expanded {
        if (qid.is_some() && title.is_some())
            || source_dat
            || claims_only
            || enriched
            || show_curated
            || wikidata_text
            || wikidata_candidates
            || wikidata_localized_candidates
            || wikidata_properties
            || wikidata_relations
            || wikidata_authority_ids
            || wikidata_gamefaqs_qualifiers
            || wikidata_items
            || wikidata_localized_titles
            || with_entity_labels
            || compare_years
            || compare_credits
            || sha1.is_some()
            || crc32.is_some()
            || size.is_some()
            || file.is_some()
            || zip.is_some()
            || zip_entry.is_some()
            || media_format.is_some()
            || property.is_some()
            || external_id.is_some()
            || language.is_some()
        {
            return Err(CatalogError::Invalid(
                "--wikidata-expanded accepts only --platform, --root, --qid or --title, and --limit".into()
            ).into());
        }
        let scope = platform.as_deref().ok_or_else(|| CatalogError::Invalid(
            "--wikidata-expanded requires --platform <atari7800|sonyplaystationportable|sonyplaystationvita|all>".into()
        ))?;
        let catalog = ExpandedWikidataCatalog::open(&root, scope)?;
        let (total, results) = catalog.search(qid.as_deref(), title.as_deref(), limit)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "pinned-wikidata-expanded-platform-source-text",
                "query_kind": if qid.is_some() {
                    "exact-source-item-qid"
                } else if title.is_some() {
                    "english-source-label-substring"
                } else {
                    "original-source-binding-list"
                },
                "platforms_searched": catalog.platforms(),
                "source_rows": catalog.total_rows(),
                "source_item_platform_observations": catalog.distinct_item_observations(),
                "english_label_rows": catalog.english_label_rows(),
                "literal_publication_date_bindings": catalog.literal_date_claims(),
                "nonliteral_publication_bindings": catalog.nonliteral_publication_bindings(),
                "source_platform_rows": catalog.platform_row_counts(),
                "total_filtered_source_rows": total,
                "returned_source_rows": results.len(),
                "source_rows_evidence": results,
                "interpretation": "original-independent-Wikidata-source-bindings-not-canonical-games-dates-or-Libretro-identities"
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
    if (query_modes != 1
        && !((claims_only
            || wikidata_text
            || wikidata_candidates
            || wikidata_localized_candidates
            || wikidata_properties
            || wikidata_relations
            || wikidata_authority_ids
            || wikidata_gamefaqs_qualifiers
            || wikidata_items
            || wikidata_localized_titles)
            && query_modes == 0))
        || (claims_only && (!source_dat || !enriched))
        || (wikidata_text
            && (source_dat
                || claims_only
                || enriched
                || show_curated
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()
                || (qid.is_some() && title.is_some())))
        || (wikidata_localized_candidates
            && (wikidata_text
                || wikidata_candidates
                || wikidata_properties
                || wikidata_relations
                || wikidata_localized_titles
                || wikidata_items
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || with_entity_labels
                || property.is_some()
                || language.is_some()
                || external_id.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()
                || (qid.is_some() && title.is_some())))
        || (wikidata_candidates
            && (wikidata_text
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()
                || (qid.is_some() && title.is_some())))
        || (wikidata_properties
            && (wikidata_text
                || wikidata_candidates
                || wikidata_localized_candidates
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || title.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()))
        || (wikidata_gamefaqs_qualifiers
            && (wikidata_text
                || wikidata_candidates
                || wikidata_localized_candidates
                || wikidata_properties
                || wikidata_relations
                || wikidata_authority_ids
                || wikidata_items
                || wikidata_localized_titles
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || with_entity_labels
                || language.is_some()
                || property.is_some()
                || title.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()))
        || (wikidata_authority_ids
            && (wikidata_text
                || wikidata_candidates
                || wikidata_localized_candidates
                || wikidata_properties
                || wikidata_relations
                || wikidata_items
                || wikidata_localized_titles
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || with_entity_labels
                || language.is_some()
                || title.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()))
        || (wikidata_relations
            && (wikidata_text
                || wikidata_candidates
                || wikidata_localized_candidates
                || wikidata_properties
                || wikidata_items
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || title.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()))
        || (wikidata_localized_titles
            && (wikidata_text
                || wikidata_candidates
                || wikidata_localized_candidates
                || wikidata_properties
                || wikidata_relations
                || wikidata_items
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || with_entity_labels
                || property.is_some()
                || external_id.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()
                || (qid.is_some() && title.is_some())))
        || (wikidata_items
            && (wikidata_text
                || wikidata_candidates
                || wikidata_localized_candidates
                || wikidata_properties
                || source_dat
                || claims_only
                || enriched
                || show_curated
                || compare_years
                || compare_credits
                || with_entity_labels
                || property.is_some()
                || sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()
                || media_format.is_some()
                || zip_entry.is_some()
                || (qid.is_some() && title.is_some())))
        || (external_id.is_some()
            && ((!wikidata_relations && !wikidata_authority_ids && !wikidata_gamefaqs_qualifiers)
                || (qid.is_some() && !wikidata_gamefaqs_qualifiers)
                || external_id.as_deref() == Some("")
                || (wikidata_relations && !matches!(property.as_deref(), Some("P1733" | "P2725")))))
        || (with_entity_labels && !wikidata_properties && !wikidata_relations)
        || (property.is_some()
            && !wikidata_properties
            && !wikidata_relations
            && !wikidata_authority_ids
            && !wikidata_gamefaqs_qualifiers)
        || (language.is_some() && !wikidata_localized_titles)
        || ((compare_years || compare_credits) && !wikidata_candidates)
        || (qid.is_some()
            && !wikidata_text
            && !wikidata_candidates
            && !wikidata_localized_candidates
            && !wikidata_properties
            && !wikidata_items
            && !wikidata_relations
            && !wikidata_authority_ids
            && !wikidata_gamefaqs_qualifiers
            && !wikidata_localized_titles)
        || (claims_only
            && (sha1.is_some()
                || crc32.is_some()
                || size.is_some()
                || file.is_some()
                || zip.is_some()))
        || (crc32.is_some() && size.is_none())
        || (title.is_some() && size.is_some())
        || (file.is_some() && (size.is_some() || limit_explicit))
        || (zip.is_some() && (size.is_some() || limit_explicit))
        || (title.is_none()
            && limit_explicit
            && !claims_only
            && !wikidata_text
            && !wikidata_candidates
            && !wikidata_localized_candidates
            && !wikidata_properties
            && !wikidata_items
            && !wikidata_relations
            && !wikidata_authority_ids
            && !wikidata_gamefaqs_qualifiers
            && !wikidata_localized_titles)
        || (qid.is_some()
            && limit_explicit
            && !wikidata_candidates
            && !wikidata_localized_candidates
            && !wikidata_properties
            && !wikidata_items
            && !wikidata_relations
            && !wikidata_authority_ids
            && !wikidata_gamefaqs_qualifiers
            && !wikidata_localized_titles)
        || ((title.is_some()
            || claims_only
            || wikidata_text
            || wikidata_candidates
            || wikidata_localized_candidates
            || wikidata_properties
            || wikidata_relations
            || wikidata_authority_ids
            || wikidata_gamefaqs_qualifiers
            || wikidata_items
            || wikidata_localized_titles)
            && (limit == 0 || limit > 200))
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
    if wikidata_localized_candidates {
        let original = OriginalDatCatalog::open(&root, "all")?;
        let localized = WikidataLocalizedTitleCatalog::open(&root, &platform)?;
        let old_source = WikidataTextCatalog::open(&root, &platform)?;
        let old_candidates = WikidataCandidateCatalog::reconcile(&original, &old_source);
        let candidates =
            WikidataLocalizedCandidateCatalog::reconcile(&original, &localized, &old_candidates);
        let (filtered, observations) =
            candidates.search(title.as_deref(), qid.as_deref(), limit)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "multilingual-wikidata-exact-title-review-candidates",
                "query_kind": if qid.is_some() {
                    "wikidata-qid"
                } else if title.is_some() {
                    "original-source-title-substring"
                } else {
                    "all-exact-localized-title-pairs"
                },
                "summary": candidates.summary(),
                "total_filtered_candidate_pairs": filtered,
                "returned_candidate_pairs": observations.len(),
                "candidate_pairs": observations,
                "interpretation": "language-tagged-name-equality-is-review-only-not-proof-of-regional-release-or-game-identity"
            }))?
        );
        return Ok(());
    }
    if wikidata_localized_titles {
        let catalog = WikidataLocalizedTitleCatalog::open(&root, &platform)?;
        let (total, results) =
            catalog.search(qid.as_deref(), title.as_deref(), language.as_deref(), limit)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "verified-wikidata-language-tagged-game-names",
                "query_kind": if qid.is_some() {
                    "exact-game-QID"
                } else if title.is_some() {
                    "original-localized-game-name-substring"
                } else {
                    "original-localized-game-name-list"
                },
                "platforms_searched": catalog.platform_ids(),
                "total_original_localized_names": catalog.total_claims(),
                "source_item_platform_observations": catalog.source_item_observations(),
                "original_language_tag_counts": catalog.languages(),
                "original_name_kind_counts": catalog.name_kinds(),
                "total_filtered_source_names": total,
                "returned_source_names": results.len(),
                "names": results,
                "interpretation": "original-language-tagged-wikidata-name-claims-not-verified-localized-release-identities"
            }))?
        );
        return Ok(());
    }
    if wikidata_gamefaqs_qualifiers {
        let catalog = GameFaqsQualifierCatalog::open(&root, &platform)?;
        let (total, rows) = catalog.search(qid.as_deref(), external_id.as_deref(), limit)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "wikidata-gamefaqs-statement-level-p400-qualifier-evidence",
                "query_kind": if external_id.is_some() {
                    "exact-gamefaqs-source-id"
                } else if qid.is_some() {
                    "source-game-qid"
                } else {
                    "source-statement-list"
                },
                "platforms_searched": catalog.source_partitions(),
                "source_statement_rows": catalog.total_rows(),
                "distinct_statement_uris_per_partition": catalog.distinct_source_statements_per_partition(),
                "qualifier_scope_counts": catalog.qualifier_counts(),
                "total_filtered_statement_rows": total,
                "returned_statement_rows": rows.len(),
                "statements": rows,
                "interpretation": "Original Wikidata P4769 statement P400 qualifiers, not evidence of provider-verified or canonical platform-specific game releases"
            }))?
        );
        return Ok(());
    }
    if wikidata_authority_ids {
        let catalog = WikidataAuthorityIdCatalog::open(&root, &platform)?;
        let (total, qids, platforms, hits) = if let Some(ref identifier) = external_id {
            let (count, qids, platforms, entries) =
                catalog.search_external_id(property.as_deref().unwrap_or(""), identifier, limit)?;
            (count, Some(qids), Some(platforms), entries)
        } else {
            let (count, entries) = catalog.search(qid.as_deref(), property.as_deref(), limit)?;
            (count, None, None, entries)
        };
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "pinned-wikidata-third-party-game-authority-id-claims",
                "query_kind": if external_id.is_some() {
                    "exact-property-scoped-identifier"
                } else if qid.is_some() {
                    "source-wikidata-game-qid"
                } else {
                    "raw-authority-identifier-list"
                },
                "platforms_searched": catalog.platforms(),
                "source_claims": catalog.total_claims(),
                "source_item_platform_observations": catalog.item_observations(),
                "source_property_counts": catalog.property_counts(),
                "total_filtered_claims": total,
                "distinct_wikidata_game_qids_for_identifier": qids,
                "distinct_source_platforms_for_identifier": platforms,
                "returned_claims": hits.len(),
                "claims": hits,
                "interpretation": "pinned-Wikidata-CC0-identifier-claims-not-verified-against-external-providers-or-canonical-game-identities"
            }))?
        );
        return Ok(());
    }
    if wikidata_relations {
        let catalog = WikidataRelationCatalog::open(&root, &platform)?;
        let (total, distinct_qids, distinct_platforms, results) = if let Some(ref identifier) =
            external_id
        {
            let (count, qids, platforms, entries) =
                catalog.search_external_id(property.as_deref().unwrap(), identifier, limit)?;
            (count, Some(qids), Some(platforms), entries)
        } else {
            let (count, entries) = catalog.search(qid.as_deref(), property.as_deref(), limit)?;
            (count, None, None, entries)
        };
        let labels = if with_entity_labels {
            let source = WikidataEntityLabelCatalog::open_relations(&root)?;
            let all = WikidataRelationCatalog::open(&root, "all")?;
            source.verify_relation_qids(&all)?;
            Some(source)
        } else {
            None
        };
        let claims: Vec<Value> = results
            .iter()
            .map(|claim| {
                let mut original = serde_json::to_value(claim)?;
                if let Some(ref source) = labels {
                    original["value_english_label_evidence"] = json!(claim
                        .value_entity_qid
                        .as_deref()
                        .and_then(|qid| source.lookup(qid)));
                }
                Ok::<Value, serde_json::Error>(original)
            })
            .collect::<Result<_, _>>()?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "verified-wikidata-game-relations-and-external-ids",
                "query_kind": if external_id.is_some() {
                    "exact-provider-identifier-source-claim"
                } else if qid.is_some() {
                    "exact-game-item-qid"
                } else if property.is_some() {
                    "property-source-list"
                } else {
                    "source-statement-list"
                },
                "platforms_searched": catalog.platforms(),
                "source_statements": catalog.total_claims(),
                "exact_provider_id_query": external_id.as_deref(),
                "distinct_game_qids_for_exact_id": distinct_qids,
                "distinct_platforms_for_exact_id": distinct_platforms,
                "has_multi_qid_assignments": distinct_qids.map(|count| count > 1),
                "source_item_platform_observations": catalog.item_observations(),
                "source_entity_value_bindings": catalog.entity_values(),
                "source_property_counts": catalog.property_counts(),
                "entity_label_source": labels.as_ref().map(|source| json!({
                    "entity_qids": source.total_qids(),
                    "english_labels": source.english_label_count(),
                    "unlabeled_qids": source.total_qids() - source.english_label_count(),
                    "source": "independently-pinned-Wikidata-relation-QID-labels"
                })),
                "total_filtered_claims": total,
                "returned_claims": results.len(),
                "claims": claims,
                "interpretation": "attributed-source-statements-not-verified-game-or-provider-identities"
            }))?
        );
        return Ok(());
    }
    if wikidata_items {
        let text = WikidataTextCatalog::open(&root, &platform)?;
        let properties = WikidataPropertyCatalog::open(&root, &platform)?;
        let relations = WikidataRelationCatalog::open(&root, &platform)?;
        let localized = WikidataLocalizedTitleCatalog::open(&root, &platform)?;
        let authority = WikidataAuthorityIdCatalog::open(&root, &platform)?;
        let relation_labels = WikidataEntityLabelCatalog::open_relations(&root)?;
        let full_relations = if platform == "all" {
            None
        } else {
            Some(WikidataRelationCatalog::open(&root, "all")?)
        };
        relation_labels.verify_relation_qids(full_relations.as_ref().unwrap_or(&relations))?;
        let labels = WikidataEntityLabelCatalog::open(&root)?;
        let all_properties = if platform == "all" {
            None
        } else {
            Some(WikidataPropertyCatalog::open(&root, "all")?)
        };
        labels.verify_referenced_qids(all_properties.as_ref().unwrap_or(&properties))?;
        let index = WikidataItemProjection::build(
            &text,
            &properties,
            &labels,
            &relations,
            &relation_labels,
            &localized,
            &authority,
        )?;
        let (total, observations) = index.search(qid.as_deref(), title.as_deref(), limit)?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "multi-snapshot-wikidata-qid-source-observations",
                "platform_scope": platform,
                "title_date_source_items": index.title_date_source_items(),
                "property_source_items": index.property_source_items(),
                "relation_source_items": index.relation_source_items(),
                "localized_source_items": index.localized_source_items(),
                "authority_source_items": index.authority_source_items(),
                "authority_only_source_items": index.authority_only(),
                "localized_source_only_items": index.localized_only(),
                "relation_and_localized_only_items": index.relation_and_localized_only(),
                "relation_label_source_qids": relation_labels.total_qids(),
                "relation_labels_in_english": relation_labels.english_label_count(),
                "relation_source_only_items": index.relation_only(),
                "combined_distinct_platform_qids": index.total_items(),
                "source_membership_counts": index.source_membership_counts(),
                "title_date_source_only_items": index.title_date_only(),
                "property_source_only_items": index.property_only(),
                "total_filtered_source_items": total,
                "returned_source_items": observations.len(),
                "source_items": observations,
                "interpretation": "exact-QID-source-projection-not-verified-game-media-company-or-release-identities"
            }))?
        );
        return Ok(());
    }
    if wikidata_properties {
        let catalog = WikidataPropertyCatalog::open(&root, &platform)?;
        let (total, records) = catalog.search(qid.as_deref(), property.as_deref(), limit)?;
        let labels = if with_entity_labels {
            let source = WikidataEntityLabelCatalog::open(&root)?;
            let all = WikidataPropertyCatalog::open(&root, "all")?;
            source.verify_referenced_qids(&all)?;
            Some(source)
        } else {
            None
        };
        let claims: Vec<Value> = records
            .iter()
            .map(|record| {
                let mut original = serde_json::to_value(record)?;
                if let Some(ref label_source) = labels {
                    original["value_label_evidence"] = json!(record
                        .value_qid
                        .as_deref()
                        .and_then(|id| label_source.lookup(id)));
                }
                Ok::<Value, serde_json::Error>(original)
            })
            .collect::<Result<_, _>>()?;
        println!(
            "{}",
            serde_json::to_string_pretty(&json!({
                "source_mode": "verified-wikidata-property-bindings",
                "query_kind": if qid.is_some() {"exact-game-item-qid"} else {"source-statement-list"},
                "platforms_searched": catalog.platforms(),
                "source_statements": catalog.total_claims(),
                "source_item_platform_observations": catalog.source_item_observations(),
                "non_entity_value_bindings": catalog.non_entity_bindings(),
                "source_property_counts": catalog.property_counts(),
                "total_filtered_claims": total,
                "returned_claims": records.len(),
                "claims": claims,
                "entity_label_source": labels.as_ref().map(|source| json!({
                    "entity_qids": source.total_qids(),
                    "english_labels": source.english_label_count(),
                    "unlabeled_qids": source.total_qids() - source.english_label_count(),
                    "source": "independent-pinned-Wikidata-CC0-English-label-observations"
                })),
                "interpretation": "Wikidata CC0 source claims not canonical games companies or genres"
            }))?
        );
        return Ok(());
    }
    if wikidata_candidates {
        let wikidata = WikidataTextCatalog::open(&root, &platform)?;
        let base = if compare_years || compare_credits {
            OriginalDatCatalog::open(&root, &platform)?.with_enrichment(&root)?
        } else {
            OriginalDatCatalog::open(&root, &platform)?
        };
        let catalog = WikidataCandidateCatalog::reconcile(&base, &wikidata);
        let summary = catalog.summary();
        let (total, matches) = catalog.search(title.as_deref(), qid.as_deref(), limit)?;
        let output = json!({
            "source_mode": "wikidata-libretro-title-candidates",
            "query_kind": if qid.is_some() {
                "candidate-wikidata-qid"
            } else if title.is_some() {
                "candidate-source-title-substring"
            } else {
                "candidate-list"
            },
            "platforms_searched": summary.platforms_searched,
            "total_candidate_links": summary.total_candidate_links,
            "source_records_with_candidate": summary.source_records_with_candidate,
            "ambiguous_candidate_links": summary.ambiguous_candidate_links,
            "total_filtered_candidates": total,
            "returned_candidates": matches.len(),
            "candidates": matches,
            "interpretation": "review-candidates-only-no-verified-work-or-media-identities"
        });
        let mut output = output;
        if compare_credits {
            let properties = WikidataPropertyCatalog::open(&root, "all")?;
            let labels = WikidataEntityLabelCatalog::open(&root)?;
            labels.verify_referenced_qids(&properties)?;
            let audit = WikidataCreditAudit::build(&base, &properties, &labels, &catalog);
            let (credit_total, credit_results) =
                audit.search(title.as_deref(), qid.as_deref(), limit)?;
            output["credit_evidence_counts"] = json!(audit.counts());
            output["total_filtered_credit_comparisons"] = json!(credit_total);
            output["credit_evidence"] = json!(credit_results);
            output["credit_interpretation"] =
                json!("same-name-evidence-is-not-an-accepted-game-company-or-release-identity");
        }
        if compare_years {
            let audit = WikidataYearAudit::build(&base, &wikidata, &catalog);
            let (year_count, year_rows) =
                audit.search(title.as_deref(), qid.as_deref(), None, limit)?;
            output["year_comparison_counts"] = json!(audit.status_counts());
            output["total_filtered_year_comparisons"] = json!(year_count);
            output["year_evidence"] = json!(year_rows);
            output["year_interpretation"] = json!(
                "year-overlap-or-difference-is-review-evidence-not-game-or-regional-date-proof"
            );
        }
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
    }
    if wikidata_text {
        let catalog = WikidataTextCatalog::open(&root, &platform)?;
        let (total, matches) = if let Some(ref id) = qid {
            let values = catalog.lookup_qid(id)?;
            (values.len(), values)
        } else {
            catalog.search_titles(title.as_deref(), limit)?
        };
        let output = json!({
            "source_mode": "verified-wikidata-jsonl",
            "query_kind": if qid.is_some() {"exact-wikidata-qid"} else if title.is_some() {
                "wikidata-english-label-substring"
            } else {"wikidata-source-list"},
            "platforms_searched": catalog.platform_ids().collect::<Vec<_>>(),
            "source_item_count": catalog.item_count(),
            "source_date_claim_count": catalog.date_count(),
            "snapshot_sha256": catalog.snapshot_sha256(),
            "total_source_matches": total,
            "returned_matches": matches.len(),
            "matches": matches,
            "interpretation": "independent-wikidata-observations-not-verified-game-identities"
        });
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
    }
    if source_dat {
        if show_curated || zip.is_some() || media_format.is_some() || zip_entry.is_some() {
            return Err(CatalogError::Invalid(
                "--source-dat does not support --curated, --zip or --media-format".into(),
            )
            .into());
        }
        let catalog = if enriched {
            OriginalDatCatalog::open(&root, &platform)?.with_enrichment(&root)?
        } else {
            OriginalDatCatalog::open(&root, &platform)?
        };
        let all = catalog.platform_ids().collect::<Vec<_>>();
        if claims_only {
            let (total, matches) = catalog.search_field_claims(title.as_deref(), limit)?;
            let output = json!({
                "source_mode": "original-field-dat-text",
                "query_kind": if title.is_some() {
                    "bibliographic-source-comment-substring"
                } else {
                    "bibliographic-source-claim-list"
                },
                "platforms_searched": all,
                "total_source_claims": total,
                "returned_claims": matches.len(),
                "claims": matches,
                "field_claim_resolution_counts": catalog.claim_resolution_counts(),
                "interpretation": "original-bibliographic-claims-not-canonical-game-identities"
            });
            println!("{}", serde_json::to_string_pretty(&output)?);
            return Ok(());
        }
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
