//! Search original, Git-committed console DAT text directly; no Python or SQLite.
//!
//! Each result is a source observation, not a validated game/work identity.
//! Raw original fields (including unknown fields) are retained unchanged.
use crate::CatalogError;
use serde::Deserialize;
use serde_json::{json, Value};
use sha1::{Digest, Sha1};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io::Read;
use std::path::Path;

const PINNED_REVISION: &str = "fbeefcb46c2e1b20a7e2945f34a694a41b2d6f90";

#[derive(Debug, Deserialize)]
struct Register {
    schema_version: u32,
    source_id: String,
    repository_revision: String,
    declared_repository_license: String,
    #[serde(default)]
    files: Vec<PinnedFile>,
    #[serde(default)]
    platforms: Vec<PinnedFile>,
}

#[derive(Debug, Deserialize)]
struct PinnedFile {
    platform: String,
    source_path: String,
    git_blob_sha: String,
    #[serde(default)]
    bytes: Option<usize>,
}

#[derive(Debug)]
struct Game {
    ordinal: usize,
    fields: BTreeMap<String, String>,
    media: Vec<BTreeMap<String, String>>,
}

#[derive(Debug)]
struct Source {
    id: String,
    revision: String,
    path: String,
    blob: String,
}

#[derive(Debug)]
struct Platform {
    id: String,
    source: Source,
    games: Vec<Game>,
}

/// Full source-text collection. Parsing and hash-checking are read-only, local operations.
pub struct OriginalDatCatalog {
    platforms: Vec<Platform>,
}

fn invalid(msg: impl Into<String>) -> CatalogError {
    CatalogError::Invalid(msg.into())
}

fn blob_sha(bytes: &[u8]) -> String {
    let mut digest = Sha1::new();
    digest.update(format!("blob {}\0", bytes.len()).as_bytes());
    digest.update(bytes);
    format!("{:x}", digest.finalize())
}

fn load_register(root: &Path, name: &str, expected: usize) -> Result<Register, CatalogError> {
    let source: Register = serde_json::from_slice(&fs::read(root.join("sources").join(name))?)?;
    let entries = if name == "libretro-no-intro.json" {
        &source.files
    } else {
        &source.platforms
    };
    if source.schema_version != 1
        || source.source_id != "libretro-no-intro"
        || source.repository_revision != PINNED_REVISION
        || source.declared_repository_license != "CC-BY-SA-4.0"
        || entries.len() != expected
    {
        return Err(invalid(format!("source register mismatch: {name}")));
    }
    Ok(source)
}

/// Parse clrmamepro DAT key/value attributes. Every original value survives.
/// Quotes may contain literal UTF-8 and escaped quote/backslash characters.
fn pairs(line: &str) -> Result<BTreeMap<String, String>, CatalogError> {
    let bytes = line.as_bytes();
    let mut pos = 0;
    let mut fields = BTreeMap::new();
    while pos < bytes.len() {
        while pos < bytes.len() && bytes[pos].is_ascii_whitespace() {
            pos += 1;
        }
        if pos == bytes.len() {
            break;
        }
        let begin = pos;
        while pos < bytes.len() && (bytes[pos].is_ascii_alphanumeric() || bytes[pos] == b'_') {
            pos += 1;
        }
        if begin == pos || pos == bytes.len() || !bytes[pos].is_ascii_whitespace() {
            return Err(invalid("invalid DAT attribute key or delimiter"));
        }
        let key = line[begin..pos].to_ascii_lowercase();
        while pos < bytes.len() && bytes[pos].is_ascii_whitespace() {
            pos += 1;
        }
        if pos == bytes.len() {
            return Err(invalid("DAT attribute missing value"));
        }
        let value = if bytes[pos] == b'"' {
            pos += 1;
            let mut output = String::new();
            let mut start = pos;
            let mut terminated = false;
            while pos < bytes.len() {
                match bytes[pos] {
                    b'"' => {
                        output.push_str(&line[start..pos]);
                        pos += 1;
                        terminated = true;
                        break;
                    }
                    b'\\' if pos + 1 < bytes.len()
                        && (bytes[pos + 1] == b'\\' || bytes[pos + 1] == b'"') =>
                    {
                        output.push_str(&line[start..pos]);
                        output.push(bytes[pos + 1] as char);
                        pos += 2;
                        start = pos;
                    }
                    _ => pos += 1,
                }
            }
            if !terminated {
                return Err(invalid("unterminated quoted DAT value"));
            }
            output
        } else {
            let start = pos;
            while pos < bytes.len() && !bytes[pos].is_ascii_whitespace() {
                pos += 1;
            }
            line[start..pos].to_owned()
        };
        if fields.insert(key.clone(), value).is_some() {
            return Err(invalid(format!("duplicate DAT attribute: {key}")));
        }
    }
    Ok(fields)
}

fn parse_dat(bytes: &[u8]) -> Result<Vec<Game>, CatalogError> {
    let text = std::str::from_utf8(bytes).map_err(|_| invalid("DAT must be UTF-8 text"))?;
    let mut in_game = false;
    let mut game = Game {
        ordinal: 0,
        fields: BTreeMap::new(),
        media: Vec::new(),
    };
    let mut records = Vec::new();
    for (index, raw) in text.lines().enumerate() {
        let line = raw.trim();
        if line == "game (" {
            if in_game {
                return Err(invalid(format!("nested DAT game at line {}", index + 1)));
            }
            in_game = true;
            game = Game {
                ordinal: records.len() + 1,
                fields: BTreeMap::new(),
                media: Vec::new(),
            };
        } else if in_game && line == ")" {
            if !game.fields.get("name").is_some_and(|name| !name.is_empty())
                || game.media.is_empty()
            {
                return Err(invalid(format!("incomplete DAT game at line {}", index + 1)));
            }
            records.push(game);
            in_game = false;
            game = Game {
                ordinal: 0,
                fields: BTreeMap::new(),
                media: Vec::new(),
            };
        } else if in_game {
            if line.is_empty() {
                continue;
            }
            if let Some(raw_rom) = line.strip_prefix("rom (").and_then(|s| s.strip_suffix(')')) {
                let rom = pairs(raw_rom)?;
                if rom.is_empty() {
                    return Err(invalid("DAT ROM entry is empty"));
                }
                if let Some(size) = rom.get("size") {
                    size.parse::<u64>().map_err(|_| invalid("invalid DAT ROM size"))?;
                }
                for (key, len) in [("crc", 8), ("md5", 32), ("sha1", 40)] {
                    if let Some(hash) = rom.get(key) {
                        if hash.len() != len || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
                            return Err(invalid(format!("invalid DAT ROM {key}")));
                        }
                    }
                }
                game.media.push(rom);
            } else {
                let mut field = pairs(line)?;
                if field.len() != 1 {
                    return Err(invalid(format!("malformed DAT scalar at line {}", index + 1)));
                }
                let (key, value) = field.pop_first().expect("one field");
                if game.fields.insert(key.clone(), value).is_some() {
                    return Err(invalid(format!("duplicate DAT game field {key}")));
                }
            }
        }
    }
    if in_game {
        return Err(invalid("unclosed DAT game block"));
    }
    if records.is_empty() {
        return Err(invalid("DAT contains no source records"));
    }
    Ok(records)
}

fn safe_entry(item: &PinnedFile) -> bool {
    let platform = &item.platform;
    let path = &item.source_path;
    !platform.is_empty()
        && platform.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit())
        && path.starts_with("metadat/no-intro/")
        && path.ends_with(".dat")
        && !path["metadat/no-intro/".len()..].contains('/')
        && item.git_blob_sha.len() == 40
        && item.git_blob_sha.bytes().all(|b| b.is_ascii_hexdigit())
}

fn load_one(root: &Path, register: &Register, entry: &PinnedFile, expanded: bool) -> Result<Platform, CatalogError> {
    if !safe_entry(entry) {
        return Err(invalid("unsafe source manifest path, platform or digest"));
    }
    let relative = if expanded {
        root.join("archive/libretro-bulk").join(&entry.source_path)
    } else {
        root.join("archive/libretro-no-intro").join(format!("{}.dat", entry.platform))
    };
    let bytes = fs::read(&relative)?;
    if entry.bytes.is_some_and(|expected| expected != bytes.len())
        || blob_sha(&bytes) != entry.git_blob_sha
    {
        return Err(invalid(format!("DAT source hash/size mismatch: {}", entry.platform)));
    }
    Ok(Platform {
        id: entry.platform.clone(),
        source: Source {
            id: register.source_id.clone(),
            revision: register.repository_revision.clone(),
            path: entry.source_path.clone(),
            blob: entry.git_blob_sha.clone(),
        },
        games: parse_dat(&bytes)?,
    })
}

fn format_match(platform: &Platform, game: &Game, media: Option<&BTreeMap<String, String>>) -> Value {
    json!({
        "platform": platform.id,
        "title": game.fields["name"],
        "source_fields": game.fields,
        "source_media": media,
        "source_ordinal": game.ordinal,
        "source": {
            "id": platform.source.id,
            "revision": platform.source.revision,
            "path": platform.source.path,
            "blob_sha": platform.source.blob
        },
        "interpretation": "original-source-observation-not-canonical-game-identity"
    })
}

impl OriginalDatCatalog {
    /// Open the complete pinned source corpus (75 platforms) or one named source.
    /// Every accessed original DAT must pass its Git blob SHA check.
    pub fn open(root: impl AsRef<Path>, selection: &str) -> Result<Self, CatalogError> {
        let root = root.as_ref();
        let base = load_register(root, "libretro-no-intro.json", 10)?;
        let expanded = load_register(root, "bulk-expansion-v1.json", 65)?;
        let mut seen = HashSet::new();
        let mut platforms = Vec::new();
        for (register, entries, extra) in [
            (&base, &base.files, false),
            (&expanded, &expanded.platforms, true),
        ] {
            for entry in entries {
                if !seen.insert(entry.platform.as_str()) {
                    return Err(invalid("duplicate platform in DAT source registers"));
                }
                if selection == "all" || selection == entry.platform {
                    platforms.push(load_one(root, register, entry, extra)?);
                }
            }
        }
        if platforms.is_empty() {
            return Err(invalid(format!("unknown original DAT source platform: {selection}")));
        }
        Ok(Self { platforms })
    }

    pub fn platform_ids(&self) -> impl Iterator<Item = &str> {
        self.platforms.iter().map(|platform| platform.id.as_str())
    }

    pub fn source_record_count(&self) -> usize {
        self.platforms.iter().map(|platform| platform.games.len()).sum()
    }

    /// Direct text-source title search, one result per original source observation.
    pub fn search_titles(&self, value: &str, limit: usize) -> Result<(usize, Vec<Value>), CatalogError> {
        let needle = value.trim().to_lowercase();
        if needle.is_empty() || !(1..=200).contains(&limit) {
            return Err(invalid("title search requires nonempty text and limit 1..=200"));
        }
        let mut total = 0;
        let mut matches = Vec::new();
        for platform in &self.platforms {
            for record in &platform.games {
                if record.fields["name"].to_lowercase().contains(&needle) {
                    total += 1;
                    if matches.len() < limit {
                        matches.push(format_match(platform, record, None));
                    }
                }
            }
        }
        Ok((total, matches))
    }

    /// Exact original media hashes only; no guessed equivalences.
    pub fn lookup_sha1(&self, value: &str, size: Option<u64>) -> Result<Vec<Value>, CatalogError> {
        if value.len() != 40 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(invalid("SHA-1 must be 40 hexadecimal characters"));
        }
        Ok(self.lookup_media("sha1", value, size))
    }

    pub fn lookup_crc32(&self, value: &str, size: u64) -> Result<Vec<Value>, CatalogError> {
        if value.len() != 8 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(invalid("CRC32 must be 8 hexadecimal characters"));
        }
        Ok(self.lookup_media("crc", value, Some(size)))
    }

    fn lookup_media(&self, kind: &str, value: &str, size: Option<u64>) -> Vec<Value> {
        let mut matches = Vec::new();
        for platform in &self.platforms {
            for record in &platform.games {
                for media in &record.media {
                    if !media.get(kind).is_some_and(|digest| digest.eq_ignore_ascii_case(value)) {
                        continue;
                    }
                    // Never treat missing source sizes as if they were a verified
                    // length. Queries with a size require an original size claim.
                    if let Some(expected) = size {
                        if media.get("size").and_then(|s| s.parse::<u64>().ok()) != Some(expected) {
                            continue;
                        }
                    }
                    matches.push(format_match(platform, record, Some(media)));
                }
            }
        }
        matches
    }

    /// Fingerprint local bytes without storing or modifying game data.
    pub fn lookup_reader<R: Read>(&self, mut reader: R) -> Result<Vec<Value>, CatalogError> {
        let mut digest = Sha1::new();
        let mut buf = [0u8; 65536];
        let mut size = 0u64;
        loop {
            let got = reader.read(&mut buf)?;
            if got == 0 {
                break;
            }
            digest.update(&buf[..got]);
            size = size.checked_add(got as u64).ok_or_else(|| invalid("input too large"))?;
        }
        self.lookup_sha1(&format!("{:x}", digest.finalize()), Some(size))
    }
}

#[cfg(test)]
mod tests {
    use super::{pairs, parse_dat};
    #[test]
    fn strict_parsing_preserves_utf8_and_unknown_attributes() {
        let raw = b"clrmamepro (\n name \"Test\"\n)\ngame (\n name \"Demo (USA)\"\n developer \"Example\"\n rom ( name \"File\" size 4 crc DEADBEEF sha1 0000000000000000000000000000000000000000 custom \"X\" )\n)\n";
        let parsed = parse_dat(raw).unwrap();
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed[0].fields["developer"], "Example");
        assert_eq!(parsed[0].media[0]["custom"], "X");
        assert_eq!(parsed[0].media[0]["crc"], "DEADBEEF");
        assert_eq!(pairs(r#"name "Pokémon \"Blue\"""#).unwrap()["name"], "Pokémon \"Blue\"");
    }
    #[test]
    fn malformed_input_is_rejected() {
        assert!(parse_dat(b"game (\n name \"X\"\n)").is_err());
        assert!(parse_dat(b"game (\n name \"X\"\n rom ( crc NOT_HEX )\n)").is_err());
        assert!(parse_dat(b"game (\n name \"X\"\n rom ( name \"A\" )").is_err());
        assert!(pairs(r#"name "missing"#).is_err());
    }
}
