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
import argparse, json, os, sys, urllib.request, urllib.parse

def query_search(endpoint: str, index: str, key: str, query: str) -> dict:
    url = f"{endpoint}/indexes/{index}/docs/search?api-version=2023-11-01"
    params = {"search": query, "count": "true"}
    url_with_params = f"{url}&{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(url_with_params, headers={"api-key": key})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--packs", required=True, help='Comma-separated like "psg@1.0.0,edg@1.0.1"')
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
            query = f"pack:{pack_id.upper()} AND version:{version}"
            result = query_search(endpoint, index, key, query)
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
