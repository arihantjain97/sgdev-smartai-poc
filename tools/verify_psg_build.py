#!/usr/bin/env python3
"""
verify_psg_build.py
- Builds approved docs for PSG only and validates the output shape against expectations.
"""
from __future__ import annotations
import json, re, subprocess, sys, os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_build() -> None:
    cmd = [
        sys.executable,
        os.path.join(REPO_ROOT, "tools", "build_index_payload.py"),
        "--status", "approved",
        "--packs", "psg@1.0.1",
        "--out", os.path.join(REPO_ROOT, "artifacts", "index_docs.json"),
    ]
    print("+", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    if res.returncode != 0:
        raise SystemExit(res.returncode)

def inspect_and_validate() -> None:
    path = os.path.join(REPO_ROOT, "artifacts", "index_docs.json")
    docs = json.load(open(path, "r", encoding="utf-8"))
    print("docs:", len(docs))
    assert len(docs) == 5, f"Expected 5 docs for PSG, got {len(docs)}"
    d0 = docs[0]
    print("id:", d0["id"])
    print("keys:", sorted(d0.keys()))
    # 2a. Azure-safe id
    assert re.fullmatch(r"[A-Za-z0-9_=\-]+", d0["id"]), f"Bad id: {d0['id']}"
    # 2b. Top-level fields match index schema
    expected = {"id","pack_id","version","status","section_id","retrieval_tags","template_text","metadata_json"}
    assert expected == set(d0.keys()), f"Unexpected keys: {sorted(set(d0.keys()) - expected)}"
    # 2c. metadata_json has API-expected fields
    meta = json.loads(d0["metadata_json"])
    for k in ["pack_id","version","section_id","template_key","path","labels","updated_at"]:
        assert k in meta, f"metadata_json missing {k}"
    print("metadata_json OK:", list(meta.keys()))

def main() -> int:
    run_build()
    inspect_and_validate()
    return 0

if __name__ == "__main__":
    sys.exit(main())


