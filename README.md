# Ludographium

**A provenance-first catalog of console and handheld video games.**

Ludographium collects the *metadata* that makes console games identifiable: official and alternate titles, platforms, regions, revisions, product codes, known media fingerprints, publication information, and source references. It is intended to become a dependable, emulator-independent catalog that Starbyte and other programs can read locally.

It is **not** a ROM collection, a cheat archive, a game ontology, or an emulator. Ludographium never distributes game binaries, firmware, or executable cheats.

## Explore

- [Design and boundaries](docs/SCOPE.md)
- [Data model](docs/MODEL.md)
- [Provenance and licensing](docs/PROVENANCE.md)
- [Read-only consumer contract](docs/CONSUMERS.md)
- [Source register](sources/README.md)
- [Platforms](platforms/platforms.json)
- [Importing source metadata](docs/IMPORTING.md)
- [Roadmap](docs/ROADMAP.md)

## Organizing principle

**Original sources are evidence, not truth by decree.** Each source snapshot stays attributable and intact. Imported rows retain a link to the exact upstream repository revision and source record; later curated identities never silently overwrite them.

A release title is not necessarily a distinct game. A ROM fingerprint is not the identity of an abstract work. A product code may apply to several builds. Regional names and revisions must not be collapsed because their filenames look similar.

## Consumers

Ludographium will publish reproducible, versioned, offline-readable indexes. A consumer should be able to match a media file by a supported checksum, inspect its exact source evidence, and display an appropriately qualified title/region without inferring unknown facts. No consumer needs to contact Ludographium at runtime.

This repository owns the metadata and its formats. It does **not** modify Starbyte or Cheatarium.

## Status

New repository; initial dataset and tooling are being bootstrapped. See [roadmap](docs/ROADMAP.md) for the difference between implemented data, provisional source imports, and future curation.
