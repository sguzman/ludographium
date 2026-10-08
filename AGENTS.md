# Ludographium contribution and agent rules

This is the **Ludographium repository only**. Its purpose is a provenance-first, reusable collection of **console/handheld game metadata**. Maintain it as a domain-specific catalog, not a catch-all game theory project.

## Hard boundaries

- **Do not edit Starbyte, Cheatarium, Gameaerium, Sourcearium, Observatorium, or other repositories.** Ludographium only supplies data for those projects to consume later.
- No ROMs, game binaries, disc images, firmware, executable patches or cheats. Fingerprint metadata is fine; copyrighted artwork needs explicit independent rights review.
- No speculative canonical game joins based on slug, filename, checksum or serial alone. Preserve work vs release vs build distinctions.
- Do not claim that an imported field is independently verified. Imported DAT values are source assertions.
- Never put personal chat language, internal venting, or AI interaction notes into public-facing project documents.

## Data accession checklist

1. Pin upstream organization, repo, immutable revision, original source path, Git blob SHA, DAT/data version and license/rights caveats.
2. Preserve the source bytes unmodified when redistribution is permitted. Source records are not to be patched to make the import look cleaner.
3. Generate the per-platform index without data loss, and retain each source record's original ordinal plus its exact snapshot information.
4. Record exceptions and unmatched content rather than inventing values.
5. Run `python3 -m unittest discover -s tests -v` and `python3 tools/verify_catalog.py`.
6. Keep source attribution in all redistributed data. Carefully review terms before adding new providers.
7. Commit a coherent change directly to Ludographium's `main` when authorized and report what was done and what remains.

## Maintaining project shape

- README: a clear introduction, boundaries, navigation and short current status; **not** a running list of every coding task.
- `docs/ROADMAP.md`: outstanding work and completed milestones; `docs/`: contracts and rationale.
- `archive/`: pristine source evidence; `sources/`: manifests and attribution; `generated/`: reproducible export; future `curated/`: independently resolved identities.
- Consumers are read-only and offline. Respect source evidence and published contract versions; never silently change source semantics.

Before altering or replacing an existing file, inspect current repository state to avoid overwriting concurrent work.
