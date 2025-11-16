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
import argparse, json, os, sys, time, urllib.request, urllib.error, urllib.parse

def post_json(url: str, payload: dict, headers: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"\n=== Azure Search HTTPError {e.code} ===", file=sys.stderr)
        print(f"URL: {req.full_url}", file=sys.stderr)
        print("Response headers:", e.headers, file=sys.stderr)
        print("Body:", body[:2000], file=sys.stderr)  # print the first ~2KB
        raise

def chunked(iterable, n):
    buf = []
    for x in iterable:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf: yield buf

def fetch_index_schema(endpoint: str, index: str, key: str) -> set[str]:
    url = f"{endpoint}/indexes/{urllib.parse.quote(index)}?api-version=2024-07-01"
    req = urllib.request.Request(url, headers={"api-key": key})
    try:
        with urllib.request.urlopen(req) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        fields = meta.get("fields", [])
        allowed = {f["name"] for f in fields if isinstance(f, dict) and "name" in f}
        return allowed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"ERR: Failed to fetch index schema: HTTP {e.code}", file=sys.stderr)
        print("Body:", body[:500], file=sys.stderr)
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", help="JSON file of docs to index")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--print-schema", action="store_true", help="Print Azure Search index schema and exit")
    args = ap.parse_args()

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index = os.environ.get("AZURE_SEARCH_INDEX", "")
    key = os.environ.get("AZURE_SEARCH_ADMIN_KEY", "")

    if args.print_schema:
        url = f"{endpoint}/indexes/{index}?api-version=2024-07-01"
        headers = {"api-key": key}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                schema = json.loads(resp.read().decode("utf-8"))
                print(json.dumps(schema.get("fields", []), indent=2))
                return 0
        except Exception as e:
            print("ERR: Failed to fetch schema:", e)
            return 2

    if not args.infile:
        print("ERR: --in is required unless using --print-schema", file=sys.stderr)
        return 2

    if not (endpoint and index and key):
        print("ERR: set AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AZURE_SEARCH_ADMIN_KEY", file=sys.stderr)
        return 2

    docs = json.loads(open(args.infile, "r", encoding="utf-8").read())
    
    # Schema preflight check
    allowed = fetch_index_schema(endpoint, index, key)
    allowed_with_action = set(allowed) | {"@search.action"}
    doc_keys = set().union(*[set(d.keys()) for d in docs]) if docs else set()
    unknown = sorted(doc_keys - allowed_with_action)
    if unknown:
        print(f"WARN: unknown fields not in schema: {unknown}", file=sys.stderr)
    
    url = f"{endpoint}/indexes/{index}/docs/index?api-version=2024-07-01"
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
