# Source quality reports

The reports in this directory describe how much metadata is available in each imported source collection. They are generated from pinned source observations, not from inferred game identities.

The [identification report](source-coverage-v1.json) and [enrichment report](enrichment-coverage-v1.json) summarize the six-platform SNES, Game Boy, Game Boy Color, Game Boy Advance, NES, and Nintendo DS source collections. It records the number of source records and media entries, the presence of individual release and media fields, and repeated values that may need later reconciliation.

The report deliberately distinguishes:

- **Identical titles:** exact source-title strings occurring more than once within one platform.
- **Repeated SHA-1 values:** fingerprint strings shared by more than one media entry.
- **Multiple CRC32-and-size matches:** source entries with the same CRC32 and byte length, which may refer to the same data or represent ambiguous weaker fingerprints.

None of these is a count of unique games, distinct releases, verified identities, or cryptographic collisions. A missing region or release date means that field is absent in the upstream observation; information may still be implicit in the title or available from another provider.

The enrichment report measures accepted and unresolved source claims, base records enriched with at least one field, and any divergent accepted values for the same field of one source record.

The [reconciliation review queue](reconciliation-queue-v1.json) groups unmatched and disputed claims by platform, CRC32, status and upstream title comment. It retains original field-source locators and shows candidate identification records when a matching CRC exists. **These are review candidates, not accepted game identities or approved metadata joins.**

## Rebuild

```sh
python3 tools/audit_catalog.py --write
python3 tools/audit_catalog.py --check
python3 tools/audit_enrichment.py --write
python3 tools/audit_enrichment.py --check
python3 tools/triage_enrichment.py --write
python3 tools/triage_enrichment.py --check
```

For focused research, `python3 tools/triage_enrichment.py --review --platform nds --status comment_mismatch --limit 25` prints unresolved groups and their original evidence without changing the catalog.

The reports are deterministic for a given collection snapshot. It is a diagnostic research aid, separate from the versioned consumer distribution manifest.
