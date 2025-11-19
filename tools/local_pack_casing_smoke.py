#!/usr/bin/env python3
"""
local_pack_casing_smoke.py

Local smoke test for pack_id casing and pack filters.

Checks:
1. tools/build_index_payload.py can build docs for PSG@1.0.1 and EDG@1.0.1.
2. All produced docs:
   - have pack_id in UPPERCASE at the top level, and
   - have metadata_json.pack_id matching and also UPPERCASE.

This is a pure local check — no deployment, no FastAPI, no curl.
It reuses the same CLI path as the Promote Pack workflow.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "local_smoke_index_docs.json"


def run_build_index_payload() -> None:
    """
    Run tools/build_index_payload.py with a fixed pack set:
    PSG@1.0.1 and EDG@1.0.1.

    Uses the same CLI entry point as CI:
      python tools/build_index_payload.py --status approved --packs "PSG@1.0.1,EDG@1.0.1" --out artifacts/...
    """
    OUT.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "tools/build_index_payload.py",
        "--vault", "app/vault",
        "--status", "approved",
        "--packs", "PSG@1.0.1,EDG@1.0.1",
        "--out", str(OUT),
    ]

    print("Running build_index_payload:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        raise SystemExit(f"[FAIL] build_index_payload.py exited with code {result.returncode}")


def load_docs():
    """
    Load the JSON docs file produced by build_index_payload.
    """
    if not OUT.exists():
        raise SystemExit(f"[FAIL] Expected output file not found: {OUT}")

    with OUT.open("r", encoding="utf-8") as f:
        return json.load(f)


def assert_uppercase_pack_ids(docs) -> None:
    """
    Assert that:
      - At least one doc was produced.
      - Each doc has pack_id in UPPERCASE.
      - metadata_json.pack_id matches doc["pack_id"] and is also UPPERCASE.
    """
    if not docs:
        raise AssertionError(
            "No docs built; expected at least one document for PSG@1.0.1 / EDG@1.0.1. "
            "Check --packs filtering or pack status in pack.yml."
        )

    for d in docs:
        pack_id = d.get("pack_id")
        if not pack_id:
            raise AssertionError(f"Doc missing pack_id: {d}")

        if not pack_id.isupper():
            raise AssertionError(f"pack_id not uppercase: {pack_id!r}")

        meta_raw = d.get("metadata_json") or "{}"
        try:
            meta = json.loads(meta_raw)
        except Exception as e:
            raise AssertionError(f"metadata_json is not valid JSON for doc {d.get('id')}: {e}")

        m_pack = meta.get("pack_id")
        if m_pack != pack_id:
            raise AssertionError(
                f"metadata_json.pack_id mismatch for doc {d.get('id')}: "
                f"{m_pack!r} != {pack_id!r}"
            )

        if not m_pack.isupper():
            raise AssertionError(
                f"metadata_json.pack_id not uppercase for doc {d.get('id')}: {m_pack!r}"
            )

    print(f"[OK] {len(docs)} docs with uppercase pack_id in both top-level and metadata_json.")


def main() -> None:
    print("=== Local pack casing smoke test ===")
    run_build_index_payload()
    docs = load_docs()
    assert_uppercase_pack_ids(docs)
    print("[PASS] local_pack_casing_smoke.py completed successfully.")


if __name__ == "__main__":
    main()

