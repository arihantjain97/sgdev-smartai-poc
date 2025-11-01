#!/usr/bin/env python3
"""
index_packs.py
- Upserts docs into Azure AI Search using REST API.
- Reads a JSON array (from build_index_payload.py).

	•	Read the JSON produced by build_index_payload.py.
	•	Upsert those documents to Azure Cognitive Search.

Why separate?
	•	Needs admin key; you don’t want this in PR CI.
	•	Keeps the “mutating the world” step inside a gated Promote workflow.

Env:
  AZURE_SEARCH_ENDPOINT (e.g., https://<name>.search.windows.net)
  AZURE_SEARCH_INDEX    (e.g., smartai-prompts-v2)
  AZURE_SEARCH_ADMIN_KEY

Usage:
  python tools/index_packs.py --in artifacts/index_docs.json [--batch 1000]
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.request

def post_json(url: str, payload: dict, headers: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")

def chunked(iterable, n):
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf: yield buf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args()

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index = os.environ.get("AZURE_SEARCH_INDEX", "")
    key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "")

    if not (endpoint and index and key):
        print("ERR: set AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AZURE_SEARCH_ADMIN_KEY", file=sys.stderr)
        return 2

    docs = json.loads(open(args.infile, "r", encoding="utf-8").read())
    url = f"{endpoint}/indexes/{index}/docs/index?api-version=2023-11-01"
    headers = {
        "Content-Type": "application/json",
        "api-key": key
    }

    total = 0
    for batch in chunked(docs, args.batch):
        payload = {"value": [{"@search.action": "mergeOrUpload", **d} for d in batch]}
        _ = post_json(url, payload, headers)
        total += len(batch)
        time.sleep(0.05)  # gentle

    print(f"Indexed {total} docs to {index}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
