#!/usr/bin/env python3
"""
lint_packs.py
Validates prompt packs. This patch adds backward-compat normalization so
legacy packs using `pack_id` and `templates:` continue to work:
  - id ← pack_id
  - sections ← templates.keys()
  - version inferred from directory name if missing (e.g., EDG.v1 → "1")
  - status defaults to "draft" if missing

Downstream validation/heuristics remain unchanged.

- Validates pack manifests and basic template structure.
- Enforces PAS/SCQA structure tokens.
- Fails (exit != 0) on any error.

Usage:
  python tools/lint_packs.py [--vault app/vault]
"""
from __future__ import annotations
import argparse, sys, re, json, os
from pathlib import Path
from typing import Dict, Any

PAS_TOKENS = ["Problem", "Agitate", "Solve"]
SCQA_TOKENS = ["Situation", "Complication", "Question", "Answer"]

REQUIRED_PACK_FIELDS = ["id", "version", "status", "sections"]

# Example path patterns we expect: app/vault/EDG.v1/pack.yml
# Capture "ver" from ".v1" or ".1.2.3"
VERSION_FROM_DIR = re.compile(r"[\\/](?P<name>[A-Za-z0-9._-]+)\.(?P<ver>v?\d[\w.-]*)[\\/]")

def infer_version_from_path(path: str) -> str:
    """Extract version from directory name like EDG.v1 → '1' or EDG.v1.2.3 → '1.2.3'"""
    m = VERSION_FROM_DIR.search(str(path))
    if m and m.group("ver"):
        # normalize "v1" or "1.2.3" -> "1" or "1.2.3"
        ver = m.group("ver").lstrip("vV")
        # If just a single number, default to SemVer format
        if re.match(r'^\d+$', ver):
            return f"{ver}.0.0"
        return ver
    return "1.0.0"

def normalize_pack(pack: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """
    Back-compat shim:
      - Prefer `id`, but fall back to `pack_id`.
      - Prefer explicit `sections`, else derive from `templates` keys if present.
      - Fill `version` from folder if missing.
      - Default `status` to "draft" if missing.
    Does NOT change downstream validation logic; it only ensures required keys exist.
    """
    norm = dict(pack) if pack else {}

    # id ← pack_id (back-compat)
    if "id" not in norm and "pack_id" in norm:
        norm["id"] = norm["pack_id"]
        print(f"WARNING: [PACK] {file_path}: using legacy 'pack_id' → 'id' (deprecated)", file=sys.stderr)

    # sections ← templates keys (back-compat)
    # If deriving from templates, prefer extracting from file field or use keys
    if "sections" not in norm:
        templates = norm.get("templates")
        if isinstance(templates, dict) and templates:
            # Try to extract section names from file field, fallback to keys
            sections = []
            for key, tmpl_data in templates.items():
                if isinstance(tmpl_data, dict) and "file" in tmpl_data:
                    # Extract basename from file path, e.g., "templates/about_company.md" -> "about_company"
                    file_path = tmpl_data["file"]
                    section_name = Path(file_path).stem  # removes .md extension
                    sections.append(section_name)
                else:
                    # Fallback to key name
                    sections.append(key)
            norm["sections"] = sections if sections else list(templates.keys())
        else:
            norm.setdefault("sections", [])
        if norm.get("sections"):
            print(f"WARNING: [PACK] {file_path}: deriving 'sections' from 'templates' (deprecated)", file=sys.stderr)

    # version
    if "version" not in norm or not norm["version"]:
        norm["version"] = infer_version_from_path(file_path)

    # status
    if "status" not in norm or not norm["status"]:
        norm["status"] = "draft"

    return norm

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
        # Normalize BEFORE schema/field checks
        pack = normalize_pack(pack, str(pack_yml_path))

        # Basic pack.yml shape
        for field in REQUIRED_PACK_FIELDS:
            if field not in pack:
                errors.append(f"[PACK] {pack_yml_path}: missing '{field}'")

        pack_id = pack.get("id", pack_dir.name.split(".")[0].upper())
        version = str(pack.get("version", ""))
        status = pack.get("status", "").lower() if isinstance(pack.get("status", ""), str) else pack.get("status")
        if status not in {"draft", "candidate", "approved"}:
            errors.append(f"[PACK] {pack_yml_path}: status must be 'draft', 'candidate', or 'approved'")
        
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
