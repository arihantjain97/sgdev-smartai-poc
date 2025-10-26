#!/usr/bin/env python3
"""
lint_packs.py
- Validates pack manifests and basic template structure.
- Enforces PAS/SCQA structure tokens.
- Fails (exit != 0) on any error.

Usage:
  python tools/lint_packs.py [--vault app/vault]
"""
from __future__ import annotations
import argparse, sys, re, json
from pathlib import Path

PAS_TOKENS = ["Problem", "Agitate", "Solve"]
SCQA_TOKENS = ["Situation", "Complication", "Question", "Answer"]

REQUIRED_PACK_FIELDS = ["id", "version", "status", "sections"]

def read_yaml(path: Path) -> dict:
    import yaml
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def find_packs(vault_dir: Path):
    for p in vault_dir.glob("*.*"):
        pack_yml = p / "pack.yml"
        if pack_yml.exists():
            yield p, pack_yml

def check_tokens(md_text: str, required_tokens: list[str], file: Path, errs: list[str]):
    for tok in required_tokens:
        # token must appear as a header or strong marker at least once
        pattern = rf"(^|\n)\s*(#+\s*{re.escape(tok)}\b|(\*\*|__){re.escape(tok)}(\*\*|__))"
        if not re.search(pattern, md_text, flags=re.IGNORECASE):
            errs.append(f"[TOKENS] {file}: missing token '{tok}'")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="app/vault", help="Root of packs")
    args = ap.parse_args()

    vault = Path(args.vault)
    if not vault.exists():
        print(f"ERR: vault path not found: {vault}", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    for pack_dir, pack_yml_path in find_packs(vault):
        pack = read_yaml(pack_yml_path)

        # Basic pack.yml shape
        for field in REQUIRED_PACK_FIELDS:
            if field not in pack:
                errors.append(f"[PACK] {pack_yml_path}: missing '{field}'")

        pack_id = pack.get("id", pack_dir.name.split(".")[0].upper())
        version = str(pack.get("version", ""))
        status = pack.get("status", "").lower() if isinstance(pack.get("status", ""), str) else pack.get("status")
        if status not in {"candidate", "approved"}:
            errors.append(f"[PACK] {pack_yml_path}: status must be 'candidate' or 'approved'")
        
        # Validate version format (basic SemVer check)
        if not version:
            errors.append(f"[PACK] {pack_yml_path}: version is required")
        elif not re.match(r'^\d+\.\d+\.\d+$', version):
            warnings.append(f"[PACK] {pack_yml_path}: version '{version}' doesn't follow SemVer format (x.y.z)")

        sections = pack.get("sections", [])
        if not isinstance(sections, list) or not sections:
            errors.append(f"[PACK] {pack_yml_path}: 'sections' must be a non-empty list")

        # Check templates exist & tokens present
        tmpl_dir = pack_dir / "templates"
        if not tmpl_dir.exists():
            errors.append(f"[PACK] {pack_yml_path}: templates/ folder missing")
            continue

        # Enforce section→template parity
        for sec in sections:
            f = tmpl_dir / f"{sec}.md"
            if not f.exists():
                errors.append(f"[PACK] {pack_yml_path}: section '{sec}' missing template {f}")

        # Decide structure expectation by filename heuristic
        for md in sorted(tmpl_dir.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            fname = md.stem.lower()
            if any(key in fname for key in ["business_case", "impact", "solution", "proposal", "vendor"]):
                check_tokens(text, PAS_TOKENS, md, errors)
            else:
                # default to SCQA for "about_*", "scope", "milestones", etc.
                check_tokens(text, SCQA_TOKENS, md, errors)

        # Optional schema check against repo schema (non-fatal if not present)
        schema_path = Path("smartai-prompts-v2.schema.json")
        if schema_path.exists():
            try:
                import jsonschema
                schema = json.loads(schema_path.read_text(encoding="utf-8"))
                doc = {
                    "id": f"{pack_id}@{version}",
                    "pack": pack_id,
                    "version": version,
                    "status": status,
                    "sections": sections,
                }
                jsonschema.validate(doc, schema)
            except Exception as e:
                warnings.append(f"[SCHEMA] {pack_yml_path}: {e}")

    for w in warnings: print(f"WARNING: {w}")
    if errors:
        for e in errors: print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("lint_packs: OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
