#!/usr/bin/env python3
"""Review exact-title revision candidates without asserting game identities.

The report suggests *source-observation pairs*, not work/release/build merges.
Only a final "(Rev X)" suffix and an otherwise byte-for-byte equal source
title (including region and other qualifiers) are considered. This intentionally
does not infer cross-region, cross-platform or cross-provider equivalence.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REVISION = re.compile(r"^(?P<base>.+) \(Rev (?P<rev>[A-Z0-9]{1,4})\)$")
# These flags often signal independently classified media. They are excluded
# from this *narrow* queue rather than being silently treated as normal releases.
EXCLUDED = re.compile(
    r"\((?:Beta(?: [^)]*)?|Proto(?: [^)]*)?|Demo(?: [^)]*)?"
    r"|Pirate|Hack|Aftermarket|Unl|Virtual Console|Switch)\)",
    re.IGNORECASE,
)


def source_locator(bundle, record):
    return {
        "source_id": bundle["source_id"],
        "source_revision": bundle["source_revision"],
        "source_path": bundle["source_path"],
        "source_blob_sha": bundle["source_blob_sha"],
        "source_ordinal": record["source_ordinal"],
    }


def revisions_for_platform(bundle):
    """Return only exact-qualifier base+revision candidates; no merged IDs."""
    groups = defaultdict(list)
    if bundle.get("schema_version") != 1 or bundle.get("kind") != "source-observations":
        raise ValueError("unsupported source observation bundle")
    for record in bundle["records"]:
        name = record["name"]
        m = REVISION.fullmatch(name)
        base = m.group("base") if m else name
        if EXCLUDED.search(base):
            continue
        # A candidate requires a region/edition qualifier; this avoids
        # mistaking parenthetical phrases in the actual title for a release.
        if not re.search(r"\([^()]+\)$", base):
            continue
        media = record["roms"]
        if len(media) != 1:
            continue
        rom = media[0]
        sha1 = rom.get("sha1")
        if not isinstance(sha1, str) or not re.fullmatch("[A-Fa-f0-9]{40}", sha1):
            continue
        if not isinstance(rom.get("size"), int) or rom["size"] <= 0:
            continue
        groups[base].append({
            "source_title": name,
            "revision": m.group("rev") if m else None,
            "sha1": sha1.upper(),
            "size": rom["size"],
            "evidence": source_locator(bundle, record),
        })

    candidates = []
    for edition, items in groups.items():
        if len(items) < 2 or not any(x["revision"] is None for x in items):
            continue
        if not any(x["revision"] is not None for x in items):
            continue
        if len({x["sha1"] for x in items}) != len(items):
            # Equal hashes or duplicate source observations require separate
            # investigation, never implicit revision equivalence.
            continue
        items.sort(key=lambda x: (x["revision"] is not None, x["source_title"], x["evidence"]["source_ordinal"]))
        candidates.append({
            "platform": bundle["platform"],
            "edition_label": edition,
            "source_revision": bundle["source_revision"],
            "evidence_status": "review-only",
            "members": items,
        })
    return sorted(candidates, key=lambda x: (x["edition_label"].casefold(), x["edition_label"]))


def build_report(root):
    manifest = json.loads((root / "generated/v1/catalog.json").read_bytes())
    platforms = []
    for item in manifest["platforms"]:
        bundle = json.loads((root / item["artifact_path"]).read_bytes())
        if bundle["platform"] != item["platform"] or bundle["source_revision"] != manifest["source_revision"]:
            raise ValueError("catalog/source revision mismatch")
        candidates = revisions_for_platform(bundle)
        platforms.append({
            "platform": item["platform"],
            "review_groups": len(candidates),
            "source_observations": sum(len(x["members"]) for x in candidates),
            "candidates": candidates,
        })
    return {
        "schema_version": 1,
        "kind": "exact-edition-revision-review",
        "source_revision": manifest["source_revision"],
        "interpretation": "Review only: exact source labels and SHA-1 are leads, not an approved work, release or build correspondence.",
        "platforms": platforms,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--review", action="store_true", help="show matching review groups")
    mode.add_argument("--summary", action="store_true", help="show per-platform counts")
    mode.add_argument("--verify", action="store_true", help="validate all input and known fixtures")
    mode.add_argument("--export", type=Path, help="write full review-only JSON to an output path")
    p.add_argument("--platform", help="optional platform ID filter for --review")
    p.add_argument("--title", help="case-insensitive edition substring filter for --review")
    p.add_argument("--limit", type=int, default=25, help="review group limit, 1..100")
    args = p.parse_args()
    if args.verify or args.summary or args.export:
        if args.platform or args.title or args.limit != 25:
            p.error("--platform, --title and --limit require --review")
    if args.review and not 1 <= args.limit <= 100:
        p.error("--limit must be between 1 and 100")
    report = build_report(args.root)
    if args.platform and args.platform not in {x["platform"] for x in report["platforms"]}:
        p.error("unknown platform ID")
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        args.export.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n",
                               encoding="utf-8")
        print(f"WROTE {args.export}")
    elif args.verify:
        # These reviewed candidate pairs exist in the pinned source snapshot.
        # They are regression controls, not canonical identity claims.
        expected = {
            ("gb", "Super Mario Land (World)"),
            ("gg", "Columns (Japan) (En)"),
        }
        discovered = {(p["platform"], g["edition_label"]) for p in report["platforms"]
                      for g in p["candidates"]}
        if not expected.issubset(discovered):
            raise SystemExit("FAIL: known exact-edition revision candidates disappeared")
        for platform in report["platforms"]:
            for group in platform["candidates"]:
                if group["evidence_status"] != "review-only":
                    raise SystemExit("FAIL: candidate misrepresented as curated identity")
                if any(m["evidence"]["source_ordinal"] < 1 for m in group["members"]):
                    raise SystemExit("FAIL: invalid source occurrence")
        print(f"PASS: revision review on {len(report['platforms'])} platforms; "
              f"{sum(x['review_groups'] for x in report['platforms'])} candidate groups")
    elif args.summary:
        print(json.dumps({
            "source_revision": report["source_revision"],
            "platforms": [{
                k: p[k] for k in ("platform", "review_groups", "source_observations")
            } for p in report["platforms"]],
        }, indent=2))
    else:
        groups = [g for platform in report["platforms"]
                  if args.platform is None or args.platform == platform["platform"]
                  for g in platform["candidates"]
                  if args.title is None or args.title.casefold() in g["edition_label"].casefold()]
        print(json.dumps({
            "source_revision": report["source_revision"],
            "matching_groups": len(groups),
            "displayed": groups[:args.limit],
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
