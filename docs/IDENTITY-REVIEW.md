# Reviewing exact-edition revisions

Ludographium's immutable source observations provide the evidence from which a deliberately small curated work/release/build ledger can be built. A **review candidate** is not an accepted game identity or a claim that two byte representations are interchangeable.

The command `tools/triage_identities.py` makes a conservative, deterministic revision review queue over the registered source catalogs. It does not write to `curated/`, invent UUIDs, alter `generated/`, or match titles from unrelated sources. A later review may accept, split, or reject any suggestion. [Bibliographic field-claim review](CROSS-SOURCE-REVIEW.md) can surface missing or divergent claims for these exact candidate media images, without automatically promoting them.

## CLI

```sh
python3 tools/triage_identities.py --summary
python3 tools/triage_identities.py --review --platform gb --title "Super Mario Land" --limit 10
python3 tools/triage_identities.py --review --platform sms --title "Phantasy Star" --limit 10
python3 tools/triage_identities.py --verify
python3 tools/triage_identities.py --export /tmp/ludographium-identity-review-v1.json
```

`--review` prints matching groups as JSON with `edition_label`, the **pinned source revision**, original source record titles, `(Rev X)` qualifiers, one SHA-1 and byte length for each observation, and the complete `source_id/source_revision/source_path/source_blob_sha/source_ordinal` locator. `--summary` shows counts per registered platform; `--verify` checks all inputs and known revision fixtures as part of CI. A review is bounded to 1-100 displayed groups, with a default of 25. `--export` writes the complete review-only data in deterministic, compact JSON for offline examination. Successful main-branch CI runs also upload `ludographium-identity-review-v1` as a short-lived (14-day) review artifact; this is **not** a permanently released or curated dataset.

## What the tool considers

Only two or more source observations **on the same platform**, where one has a title ending with `(Rev X)` and another has the *exact title without that trailing revision qualifier*, are presented. Exact means every other character and region or edition qualifier remains unchanged. All members must cite a single identifiable media file with a SHA-1 and positive byte length, **exactly one observation per revision qualifier** (including the unmarked base), and the **same byte length** across all candidates. The recorded SHA-1 values must differ. These conservative guards explicitly exclude headered/headerless duplicate representations often present in NES source catalogs; format-specific normalization and identity review are separate questions.

For example, `Super Mario Land (World)` and `Super Mario Land (World) (Rev 1)` can appear together. `Super Mario Land (World)` and `Super Mario Land (Japan) (Rev 1)` **cannot** appear in the same review group, because the territory strings are not identical. Beta, prototype, hack, pirate, aftermarket, Virtual Console, and other explicitly excluded classifications are not processed in this narrow queue.

An upstream title alone does **not** establish that records belong to one work, one release, or even an authorized publication. "Rev" is a source qualifier, not an independently authenticated build history. The queue does not try to reconcile alternate titles, re-releases, ports, publishers, serial numbers, CRC collisions, or regional naming.

## Review and curation

A curator must inspect source evidence, distinguish work identity from publication/edition and media build, write a concrete rationale, and explicitly mint opaque UUIDv4 identities. Distinct hashes remain distinct builds even when a narrowly scoped release relationship is supported. Uncertain or disputed correspondences remain unmerged.

The [curation validator](../tools/validate_curated.py) enforces that each release cites only observations already attributed to its work, each build cites only observations already attributed to its release, and no source occurrence belongs to competing curated works or competing releases. Build SHA-1 and length must match the original cited record. Review candidate generation never bypasses those constraints.

The existing [bibliographic claim reconciliation queue](../reports/reconciliation-queue-v1.json) serves a different purpose: it reports provider field claims whose comments and CRC32 do not reconcile cleanly with source observations. Consult both before concluding that a revision, localization, or reissue is the same publication.

The immutable original source archives and already-published data tags remain unchanged. An accepted curated-identity change requires regenerating `generated/curated-v1/identities.json`, then `generated/v1/distribution.json`, and publishing a **new** dataset tag if downstream users need the changed graph.
