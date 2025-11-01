#!/usr/bin/env python3
"""
build_index_payload.py
Purpose
	•	Walks your repo under app/vault/**/pack.yml.
	•	Validates + normalizes each pack.
	•	Produces a single JSON array of documents ready for Azure Search, saved to a file (e.g., artifacts/index_docs.json).

Why split it out
	•	PR CI can run this safely (no admin keys).
	•	You get a reviewable artifact (what would be indexed).
	•	It’s deterministic input to the next step.

Usage:
  python tools/build_index_payload.py --status candidate --out artifacts/index_docs.json [--packs "psg@1.0.0,edg@1.0.1"]
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
from datetime import datetime, timezone

def read_yaml(path: Path) -> dict:
    import yaml
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def discover_packs(vault_root: Path):
    for p in vault_root.glob("*.*"):
        y = p / "pack.yml"
        if y.exists():
            yield p, y

def normalize_pack_id(name: str) -> str:
    return name.split(".")[0].upper()

def should_include(pack_id: str, version: str, status: str, cli_status: str, packs_filter: set[str] | None):
    if cli_status and status != cli_status:
        return False
    if packs_filter is None:
        return True
    key = f"{pack_id.lower()}@{version}"
    return key in packs_filter

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="app/vault")
    ap.add_argument("--status", choices=["candidate", "approved"], required=True)
    ap.add_argument("--packs", help='Comma-separated like "psg@1.0.0,edg@1.0.1"', default=None)
    ap.add_argument("--out", default="artifacts/index_docs.json")
    args = ap.parse_args()

    vault = Path(args.vault)
    if not vault.exists():
        print(f"ERR: vault path not found: {vault}", file=sys.stderr)
        return 2
    
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    packs_filter = None
    if args.packs:
        packs_filter = {x.strip().lower() for x in args.packs.split(",") if x.strip()}

    docs = []
    now = datetime.now(timezone.utc).isoformat()

    for pack_dir, pack_yml in discover_packs(vault):
        pack = read_yaml(pack_yml)
        pack_id = (pack.get("id") or normalize_pack_id(pack_dir.name)).upper()
        version = pack.get("version")
        if not version:
            print(f"ERR: {pack_yml}: version is required", file=sys.stderr)
            return 1
        version = str(version)
        status = str(pack.get("status")).lower()
        labels = pack.get("labels", {})
        
        # --- Back-compat: derive `sections` from `templates` if missing ---
        sections = pack.get("sections", [])
        if not sections:
            tmpl = pack.get("templates")
            if isinstance(tmpl, dict) and tmpl:
                sections = list(tmpl.keys())
                print(f"WARNING: [PACK] {pack_yml}: deriving 'sections' from 'templates' (deprecated)", file=sys.stderr)
        # -----------------------------------------------------------------

        if not should_include(pack_id, version, status, args.status, packs_filter):
            continue

        if not sections:
            print(f"WARN: [PACK] {pack_yml}: no sections found (neither 'sections' nor 'templates'); skipping", file=sys.stderr)
            continue

        tmpl_dir = pack_dir / "templates"
        for section in sections:
            md_path = tmpl_dir / f"{section}.md"
            if not md_path.exists():
                # tolerate missing section but flag it in output for visibility
                body = f"[[MISSING TEMPLATE: {md_path}]]"
            else:
                body = md_path.read_text(encoding="utf-8")

            doc_id = f"{pack_id}:{version}:{section}:{args.status}"
            docs.append({
                "id": doc_id,
                "pack": pack_id,
                "version": version,
                "status": args.status,
                "section": section,
                "path": str(md_path),
                "labels": labels,
                "body": body,
                "updated_at": now,
            })

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)

    if not docs:
        print("WARN: no docs built (check --status and --packs filters)", file=sys.stderr)
    
    print(f"Wrote {len(docs)} docs → {out_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
