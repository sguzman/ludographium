# Source quality reports

The reports in this directory describe how much metadata is available in each imported source collection. They are generated from pinned source observations, not from inferred game identities.

The current [field-coverage report](source-coverage-v1.json) summarizes the SNES, Game Boy, Game Boy Color, and Game Boy Advance imports. It records the number of source records and media entries, the presence of individual release and media fields, and repeated values that may need later reconciliation.

The report deliberately distinguishes:

- **Identical titles:** exact source-title strings occurring more than once within one platform.
- **Repeated SHA-1 values:** fingerprint strings shared by more than one media entry.
- **Multiple CRC32-and-size matches:** source entries with the same CRC32 and byte length, which may refer to the same data or represent ambiguous weaker fingerprints.

None of these is a count of unique games, distinct releases, verified identities, or cryptographic collisions. A missing region or release date means that field is absent in the upstream observation; information may still be implicit in the title or available from another provider.

## Rebuild

```sh
python3 tools/audit_catalog.py --write
python3 tools/audit_catalog.py --check
```

The report is deterministic for a given collection snapshot. It is a diagnostic research aid, separate from the versioned consumer distribution manifest.
