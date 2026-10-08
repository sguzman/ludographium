#!/usr/bin/env python3
"""Validate internal Markdown links and the README's advertised catalog counts."""
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE = re.compile(r"^\s*" + chr(96) * 3)


def validate_markdown(root, files):
    errors = []
    root = root.resolve()
    for path in files:
        rel = path.relative_to(root)
        fenced = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE.match(line):
                fenced = not fenced
                continue
            if fenced:
                continue
            for found in LINK.finditer(line):
                destination = found[1].split("#", 1)[0]
                if not destination or destination.startswith(("https://", "http://", "mailto:")):
                    continue
                candidate = (path.parent / unquote(destination)).resolve()
                if not candidate.is_relative_to(root) or not candidate.exists():
                    errors.append(f"{rel}:{lineno}: broken or unsafe link {found[1]}")
        if fenced:
            errors.append(f"{rel}: unclosed Markdown code fence")
    return errors


def validate_readme_totals(root):
    readme = (root / "README.md").read_text(encoding="utf-8")
    catalog = json.loads((root / "generated/v1/catalog.json").read_bytes())
    enrichment = json.loads((root / "reports/enrichment-coverage-v1.json").read_bytes())
    distribution = json.loads((root / "generated/v1/distribution.json").read_bytes())
    if catalog["source_revision"] != enrichment["source_revision"]:
        raise ValueError("source and enrichment reports differ in revision")
    totals = {
        "identification records": sum(p["source_records"] for p in catalog["platforms"]),
        "bibliographic claims": enrichment["total_claims"],
        "matched claims": enrichment["resolution_counts"]["matched"],
        "runtime indexed artifacts": len(distribution["artifacts"]),
    }
    if f"**{totals['identification records']:,}**" not in readme:
        raise ValueError(f"README missing current identification total: {totals['identification records']:,}")
    for key in ("bibliographic claims", "matched claims"):
        phrase = f"**{totals[key]:,} {key}**"
        if phrase not in readme:
            raise ValueError(f"README has stale {key} ({totals[key]:,})")
    if len(distribution["artifacts"]) != len(catalog["platforms"])*2+1:
        raise ValueError("distribution artifact count disagrees with source platforms")
    return totals


def main():
    files = sorted(path for path in ROOT.rglob("*.md")
                   if not any(folder in {"target", ".git"} for folder in path.parts))
    problems = validate_markdown(ROOT, files)
    if problems:
        raise SystemExit("FAIL:\n" + "\n".join(problems))
    totals = validate_readme_totals(ROOT)
    print(f"PASS: {len(files)} Markdown files, internal links and code fences valid")
    print("PASS: README totals match source observations: " +
          ", ".join(f"{key}={value:,}" for key, value in totals.items()))


if __name__ == "__main__":
    main()
