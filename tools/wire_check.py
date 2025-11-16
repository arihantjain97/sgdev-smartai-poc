#!/usr/bin/env python3
"""
wire_check.py
- Verifies indexed docs are searchable in Azure AI Search.
- Queries by pack@version and reports counts.

Env:
  AZURE_SEARCH_ENDPOINT (e.g., https://<name>.search.windows.net)
  AZURE_SEARCH_INDEX    (e.g., smartai-prompts-v2)
  AZURE_SEARCH_QUERY_KEY

Usage:
  python tools/wire_check.py --packs "psg@1.0.0,edg@1.0.1"
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.parse, urllib.error

def query_search(endpoint: str, index: str, key: str, query: str, debug: bool = False) -> dict:
    # 2024-07-01: use POST /docs/search with JSON body
    url = f"{endpoint}/indexes/{index}/docs/search?api-version=2024-07-01"
    payload = {
        "search": query,
        "count": True,
        "top": 50,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "api-key": key,
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if debug:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"\n=== wire_check HTTPError {e.code} ===", file=sys.stderr)
            print(f"URL: {req.full_url}", file=sys.stderr)
            print("Body:", body[:200], file=sys.stderr)
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", required=True, help='Comma-separated like "psg@1.0.0,edg@1.0.1"')
    ap.add_argument("--debug", action="store_true", help="Print debug info on HTTP errors")
    args = ap.parse_args()

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index = os.environ.get("AZURE_SEARCH_INDEX", "")
    key = os.environ.get("AZURE_SEARCH_QUERY_KEY", "")

    if not (endpoint and index and key):
        print("ERR: set AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, AZURE_SEARCH_QUERY_KEY", file=sys.stderr)
        return 2

    packs = [p.strip() for p in args.packs.split(",") if p.strip()]
    all_good = True

    for pack_spec in packs:
        try:
            pack_id, version = pack_spec.split("@", 1)
            # Search for docs with this pack and version
            query = f"pack_id:{pack_id.upper()} AND version:{version}"
            result = query_search(endpoint, index, key, query, debug=args.debug)
            count = result.get("@odata.count", 0)
            print(f"{pack_spec}: {count} docs")
            if count == 0:
                all_good = False
        except Exception as e:
            print(f"ERR: {pack_spec}: {e}", file=sys.stderr)
            all_good = False

    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
