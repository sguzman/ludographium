# Curated game identities

Ludographium's curated ledger links source observations to stable identities for a game, its platform-specific publication, and an identifiable media build. This is a bibliographic identity system, not a gameplay ontology.

The ledger currently includes four deliberately selected source-grounded identities, each with one platform release and an exact media build. These initial records demonstrate the curation contract; they are **not** an automatic grouping of similar regional titles. Most source observations remain uncurated.

## Identity levels

- **Work** (`ldg:w:<uuid-v4>`): an identified game across its observed editions.
- **Release** (`ldg:r:<uuid-v4>`): a labeled publication on a known console or handheld platform, linked to a work.
- **Build** (`ldg:b:<uuid-v4>`): a particular media or revision identity linked to a release. Each build records its exact SHA-1 and byte length, verified against the cited source occurrence.

Identifiers are opaque UUIDv4 values. They are not hashes, normalized names, titles, serials, upstream ordinal numbers, or inferred joins. An identifier is never recycled for a different entity.

## Each curated record carries its evidence

Every work, release, and build requires a clear human-readable rationale and one or more **source occurrence locators**:

```json
{
  "source_id": "libretro-no-intro",
  "source_revision": "<pinned-git-revision>",
  "source_path": "metadat/no-intro/Nintendo - Game Boy.dat",
  "source_blob_sha": "<original-file-git-blob-sha>",
  "source_ordinal": 1
}
```

The placeholder strings above illustrate the fields, not a real ledger entry. Locators are checked against the archived base and bibliographic source observations. For enrichment, the locator points to the original field DAT occurrence, not the merged consumer view.

A cited observation supports the fact that a source made a claim. Evidence alone is not proof that two similarly named regional or revision variants constitute the same canonical identity; the decision rationale must record the basis of that interpretation.

## Reviewing disputed source claims

The [reconciliation queue](../reports/reconciliation-queue-v1.json) groups unresolved bibliographic source claims, with upstream source-occurrence locators and possible base-record candidates. The [review tool](../tools/triage_enrichment.py) supports platform, resolution-status, and CRC32 filters.

A shared CRC32 or similar title is only **a lead for investigation**. It is not enough by itself to create an accepted release/build link. The curated seed deliberately establishes only one documented regional media representation per work. Further releases require independent correspondence review.

## Curation and validation

```sh
python3 tools/validate_curated.py
python3 tools/validate_curated.py --mint-id work
python3 tools/validate_curated.py --mint-id release
python3 tools/validate_curated.py --mint-id build
```

The validator checks UUID formatting, uniqueness, release-to-work and build-to-release references, registered platforms, required rationales, same-platform evidence, exact source citations, and build SHA-1/byte-size equality against the cited source records. It does **not** automate identity reconciliation or test an emulator. A source conflict may remain unmerged indefinitely.

The editable ledger is [`curated/v1/identities.json`](../curated/v1/identities.json). Curated identities will be distributed to consumers only after a separate versioned export and referential-validation contract is established.
