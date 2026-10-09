#!/usr/bin/env python3
"""Stage a reproducible, versioned Ludographium metadata release.

Release tags version a frozen dataset, not the Rust crate or the v1 JSON schema.
No GitHub credentials or network access are needed to prepare a release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from build_distribution import canonical_bytes
from package_runtime import build_archive

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"data-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")


def validate_tag(tag: str) -> None:
    if not TAG.fullmatch(tag):
        raise ValueError("data release tag must be data-vMAJOR.MINOR.PATCH with no leading zeroes")


def prepare_release(root: Path, tag: str, output: Path) -> tuple[Path, Path, Path]:
    validate_tag(tag)
    manifest_path = root / "generated/v1/distribution.json"
    original = manifest_path.read_bytes()
    if original != canonical_bytes(root):
        raise ValueError("distribution manifest is out of date; refuse to release")
    manifest = json.loads(original)
    if manifest["schema_version"] != 1:
        raise ValueError("unsupported distribution schema")

    # Enumerate source-backed identities in the immutable portable projection.
    # The projection itself is covered by the distribution manifest.
    identity_path = root / "generated/curated-v1/identities.json"
    curated_summary = ""
    if identity_path.exists():
        curated = json.loads(identity_path.read_bytes())
        if curated.get("schema_version") != 1 or curated.get("kind") != "curated-identity-ledger":
            raise ValueError("unsupported curated identity projection")
        curated_summary = (
            f"- Curated identities: {len(curated['works'])} works, "
            f"{len(curated['releases'])} releases, "
            f"{len(curated['builds'])} exact media builds\n"
        )

    # A full-corpus SQLite companion is built and checked by the publication
    # workflow from the same pinned indexes. Do not conflate source observations
    # with reviewed canonical game identities.
    corpus_summary = ""
    coverage_path = root / "reports/enrichment-coverage-v1.json"
    if coverage_path.exists() and all("source_records" in p for p in
                                       json.loads((root / "generated/v1/catalog.json").read_bytes())["platforms"]):
        catalog = json.loads((root / "generated/v1/catalog.json").read_bytes())
        enrichment = json.loads(coverage_path.read_bytes())
        source_records = sum(p["source_records"] for p in catalog["platforms"])
        corpus_summary = (
            f"- Full SQLite corpus: {source_records:,} source observations, "
            f"{enrichment['total_claims']:,} attributed field claims "
            "(source observations are not distinct canonical works)\n"
        )

    archive = build_archive(root)
    digest = hashlib.sha256(archive).hexdigest()
    name = f"ludographium-runtime-{tag}.tar.gz"
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / name
    checksum_path = output / f"{name}.sha256"
    notes_path = output / "RELEASE_NOTES.md"
    archive_path.write_bytes(archive)
    checksum_path.write_text(f"{digest}  {name}\n", encoding="utf-8")
    notes_path.write_text(
        f"## Ludographium metadata {tag}\n\n"
        "This is a pinned, offline-readable metadata release. It contains no game ROMs, "
        "firmware, or game executables. The archive includes its source registers and "
        "metadata attribution notice.\n\n"
        f"- Distribution schema: `{manifest['schema_version']}`\n"
        f"- Upstream collection: `{manifest['source_id']}`\n"
        f"- Pinned source revision: `{manifest['source_revision']}`\n"
        f"- Manifest-verified artifacts: {len(manifest['artifacts'])}\n"
        f"{curated_summary}"
        f"{corpus_summary}"
        f"- Archive SHA-256: `{digest}`\n\n"
        "Verify the downloaded archive and its `.sha256` file together using "
        f"`sha256sum -c {name}.sha256`. The extracted archive contains "
        "`generated/v1/distribution.json` for per-file SHA-256 verification.\n\n"
        "The release workflow also publishes a separately SHA-256-verified "
        f"ludographium-corpus-{tag}.sqlite companion with all source records, "
        "media fingerprints and resolved/unresolved metadata claims for offline SQL queries. "
        "The database does not automatically assert work/release identities.\n\n"
        "Original Ludographium code is MIT-licensed; upstream metadata retains "
        "its own source-specific rights and attribution. Consult `METADATA-NOTICE.md` "
        "inside the archive. The archive checksum verifies bytes but is not a digital signature.\n",
        encoding="utf-8",
    )
    return archive_path, checksum_path, notes_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    archive, checksum, notes = prepare_release(args.root, args.tag, args.output)
    print(f"STAGED {archive.name}, {checksum.name}, {notes.name}")


if __name__ == "__main__":
    main()
