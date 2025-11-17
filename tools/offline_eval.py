#!/usr/bin/env python3
"""
offline_eval.py
- Lightweight CI-time evaluation (no model calls).
- Computes proxy metrics over pack templates:
    * groundedness_proxy: share of non-empty lines that contain a citation marker "[source:"
    * avg_chars_per_template and per-section caps (optional)
- Fails PR if thresholds are not met.

Usage:
  python tools/offline_eval.py \
    --vault app/vault \
    --out artifacts/eval_report.json \
    --min_grounded 0.80 \
    --max_chars 12000 \
    [--goldens "app/vault/**/golden/*.jsonl"] \
    [--dry-worker]
"""
from __future__ import annotations
import argparse, json, sys, glob
from pathlib import Path

def read_yaml(path: Path) -> dict:
    import yaml
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def discover_templates(vault_root: Path):
    """Discover all templates from pack.yml files.
    
    Iterates over pack["templates"] dict, yielding (pack_id, version, section, md_path)
    for each template. Uses section_id from template config if present, otherwise
    uses the template key name as the section.
    """
    for pack_dir in sorted(vault_root.glob("*.*")):
        pack_yml = pack_dir / "pack.yml"
        if not pack_yml.exists():
            continue
        pack = read_yaml(pack_yml)
        pack_id = str(pack.get("id") or pack.get("pack_id") or pack_dir.name.split(".")[0].upper()).upper()
        version = str(pack.get("version"))
        templates = pack.get("templates", {}) or {}
        for tmpl_name, cfg in templates.items():
            file_rel = cfg.get("file")
            if not file_rel:
                continue
            md_path = pack_dir / file_rel
            section = cfg.get("section_id") or tmpl_name
            yield pack_id, version, section, md_path

def groundedness_proxy(md_text: str) -> float:
    lines = [ln.strip() for ln in md_text.splitlines()]
    nonempty = [ln for ln in lines if ln]
    if not nonempty:
        return 0.0
    cited = [ln for ln in nonempty if "[source:" in ln.lower()]
    return len(cited) / max(1, len(nonempty))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="app/vault")
    ap.add_argument("--out", default="artifacts/eval_report.json")
    ap.add_argument("--goldens", default="app/vault/**/golden/*.jsonl")
    ap.add_argument("--min_grounded", type=float, default=0.80)
    ap.add_argument("--max_chars", type=int, default=12000)
    ap.add_argument("--dry-worker", action="store_true", help="placeholder flag for CI parity")
    args = ap.parse_args()

    vault = Path(args.vault)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    results = []
    failures = []

    # Optional: ingest golden hints (caps/overrides)
    # Format (jsonl): {"pack":"PSG","section":"business_case","max_chars":15000,"min_grounded":0.8}
    golden_overrides = {}
    for path in glob.glob(args.goldens, recursive=True):
        p = Path(path)
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip(): continue
            try:
                rec = json.loads(ln)
                pack = rec.get("pack", "").upper()
                sec = rec.get("section")
                if sec:
                    # Key by (pack, section) for per-pack control
                    key = f"{pack}:{sec}" if pack else sec
                    golden_overrides.setdefault(key, {}).update(rec)
            except Exception:
                # ignore malformed lines
                pass

    for pack_id, version, section, md_path in discover_templates(vault):
        if not md_path.exists():
            print(f"ERR: missing template {md_path}", file=sys.stderr)
            failures.append({
                "pack": pack_id, "version": version, "section": section, 
                "reasons": [f"missing template {md_path}"]
            })
            continue
            
        body = md_path.read_text(encoding="utf-8")
        g = groundedness_proxy(body)
        char_len = len(body)

        # Try pack-specific override first, then section-only
        pack_section_key = f"{pack_id}:{section}"
        section_key = section
        sec_caps = golden_overrides.get(pack_section_key, golden_overrides.get(section_key, {}))
        min_g = float(sec_caps.get("min_grounded", args.min_grounded))
        max_c = int(sec_caps.get("max_chars", args.max_chars))

        ok = (g >= min_g) and (char_len <= max_c)
        if not ok:
            reasons = []
            if g < min_g: reasons.append(f"groundedness {g:.2f} < {min_g:.2f}")
            if char_len > max_c: reasons.append(f"chars {char_len} > {max_c}")
            failures.append({
                "pack": pack_id, "version": version, "section": section, "reasons": reasons
            })

        results.append({
            "pack": pack_id,
            "version": version,
            "section": section,
            "groundedness_proxy": round(g, 4),
            "chars": char_len,
            "min_grounded": min_g,
            "max_chars": max_c,
            "path": str(md_path)
        })

    report = {"results": results, "failures": failures}
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"offline_eval: wrote {out} with {len(failures)} failure(s).")
    return 1 if failures else 0

# Quick local sanity checks (run from repo root):
#   python tools/offline_eval.py --vault app/vault --out /tmp/eval_report.json
# Then open /tmp/eval_report.json and confirm:
#   - "results" contains entries for PSG.v1 and EDG.v1 templates.
#   - "failures" is empty on a clean main.
#
# To see a failure, temporarily remove all "[source:" substrings from
# app/vault/PSG.v1/templates/cost_breakdown.md and rerun:
#   python tools/offline_eval.py --vault app/vault --out /tmp/eval_report.json
# You should now see at least one failure where groundedness_proxy < min_grounded.

if __name__ == "__main__":
    sys.exit(main())
