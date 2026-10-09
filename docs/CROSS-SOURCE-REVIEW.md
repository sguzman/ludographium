# Source-linked bibliographic evidence review

Ludographium preserves two distinct kinds of source observations:

- **Identification DATs** name a game-like record and one or more exact media representations (size, SHA-1 and CRC32 when available).
- **Bibliographic field DATs** assert individual fields, such as publisher, developer or year, with original source title comments and CRC32 values.

These DAT series are registered independently and every observation retains its original path, source revision, blob SHA and ordinal. However, they come from related pinned Libretro material. **A field DAT is not necessarily an independently researched authority**, and a matching assertion does not authenticate a game title, publication, or revision. A checksum association is evidence for review, not a canonical identity decision.

## Two complementary audits

The curated build audit:

```sh
python3 tools/audit_curated_claims.py --summary
python3 tools/audit_curated_claims.py --verify
python3 tools/audit_curated_claims.py --export /tmp/ludographium-curated-claims-v1.json
```

For each *already accepted* curated media build, the audit verifies its original source occurrence and exact SHA-1/length, retrieves only bibliographic claims previously resolved to that same source ordinal and CRC32, and outputs each claim's actual value, field, and complete originating field-DAT locator. Unresolved, ambiguous and mismatched field claims are not attached. A build without matched claims is still a valid source-backed build, not an unsupported or disproved game.

The candidate review prioritizer:

```sh
python3 tools/prioritize_identity_review.py --summary
python3 tools/prioritize_identity_review.py --review --status uncurated --limit 20
python3 tools/prioritize_identity_review.py --review --platform n64 --limit 10
python3 tools/prioritize_identity_review.py --verify
python3 tools/prioritize_identity_review.py --export /tmp/ludographium-prioritized-revisions-v1.json
```

This combines the deliberately conservative [exact-edition revision candidates](IDENTITY-REVIEW.md) with **source-attributed field coverage for each exact media image**. It also records whether each member is already represented in the curated release ledger. Candidate statuses are `uncurated`, `partially-curated`, `already-curated`, and `conflicting-curation`. The last status is a review signal, not a verdict of data corruption: distinct regional/edition release interpretations may be deliberately modeled separately.

The reviewer lists fields available for **every member** and fields whose recorded values vary between members. Its default sort prioritizes shared field coverage, then number of available field assertions, followed by stable platform/title order. This is an **evidence availability sort**, not a probability of common identity, identity quality score, or a license to join data. No score is copied into the curated ledger.

## Explicit rules

1. A field claim counts only when the source importer already marked it as matched, with the exact base source ordinal, title and CRC32 still agreeing. A CRC32 collision, title mismatch, missing comment, or unresolved status never supplies an accepted field attachment.
2. Every presented claim carries `source_id`, `source_revision`, `source_path`, `source_blob_sha`, and `source_ordinal`. The candidate media's base source locator is retained separately. Publisher strings, dates and genres are observations, not independently validated facts.
3. Work, release and build IDs are never minted, approved, or merged by these auditors. Curation still requires a decision rationale and direct evidence from the pinned source observations.
4. The Rust offline reader independently checks unique curated source ownership and that release evidence belongs to its work and build evidence belongs to its release, mirroring the Python authoring validator.
5. Audits are derived, read-only reports. Both are validated in GitHub Actions, and main-branch runs attach two 14-day artifacts: `ludographium-curated-claims-v1` and `ludographium-prioritized-revisions-v1`. They are deliberately **excluded** from permanent metadata release archives.

These reports make it easier to choose what deserves further research and to identify field discrepancies without silently laundering uncertain evidence into verified canonical identities. The original archival DATs, generated catalog schema, and published dataset tags are unaffected.
