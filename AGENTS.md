# Ludographium maintainer guide

This file describes working conventions for contributors and automated development agents. Project purpose and public usage belong in the [README](README.md); technical contracts belong in [docs/](docs/SCOPE.md).

## Repository responsibilities

Ludographium maintains the console/handheld game metadata archive, source register, import tooling, curated identity records (as they become available), and published data artifacts. Downstream integrations are developed against its published interfaces.

The dataset is metadata only. Source archives contain attribution-eligible DATs and other metadata sources, not ROMs, disc images, firmware, cheats, or game-media assets without documented redistribution rights.

## Accession workflow

1. Register each source's author, location, immutable revision, original path, content identity, retrieval date, and known license or rights constraints.
2. Keep source bytes intact when redistribution is permitted. Changes and interpretations belong in generated or curated data.
3. Retain source ordinal or equivalent source-native record identity, with a reliable route back to the exact snapshot.
4. Treat imported fields as source claims. Distinguish work, regional/platform release, and media build; document unresolved joins rather than deriving canonical identities from names.
5. Produce deterministic exports, record import exceptions, and validate source and distribution integrity metadata.
6. Run `python3 -m unittest discover -s tests -v`, `python3 tools/verify_catalog.py`, `python3 tools/build_distribution.py --check`, `python3 tools/audit_catalog.py --check`, `python3 tools/import_enrichment.py --check`, `python3 tools/audit_enrichment.py --check`, `python3 tools/validate_curated.py`, `python3 tools/triage_enrichment.py --check`, and `cargo test --workspace --all-targets --locked` before shipping index or consumer changes.
7. Review current `main` before modifying files and commit coherent changes directly when authorized.

## Documentation conventions

- **README:** purpose, current coverage, repository layout, usage, and key documentation links.
- **docs/SCOPE.md:** boundaries and relationships between kinds of records.
- **docs/MODEL.md:** field-level data contracts and identity distinctions.
- **docs/PROVENANCE.md:** sourcing, attribution, licensing, and evidence preservation.
- **docs/CONSUMERS.md:** published read-only data interfaces and compatibility.
- **docs/IMPORTING.md:** reproducible build and validation procedures.
- **docs/ROADMAP.md:** future milestones; detailed change history belongs in Git commits.

Prefer technical descriptions over contributor policy in public documentation. Keep examples and status synchronized with the committed code and data.

## Data layout

`archive/` preserves original sources, `sources/` records provenance, `generated/` publishes repeatable outputs, and `curated/` contains the evidence-validated (currently empty) identity ledger. Platform identifiers are stable within each published schema; changing a consumer-facing contract requires an explicit migration.
