# app/services/prompt_vault.py
import os, time, json
from typing import Dict, List, Tuple, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from .appcfg import get as cfg_get

_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
_SEARCH_KEY      = os.environ["AZURE_SEARCH_QUERY_KEY"]  # use *query* key in app svc
_INDEX           = os.environ.get("AZURE_SEARCH_INDEX","smartai-prompts")

_client = SearchClient(_SEARCH_ENDPOINT, _INDEX, AzureKeyCredential(_SEARCH_KEY))

_cache: Dict[Tuple[str,str,str], Tuple[dict,float]] = {}
# key=(pack,ver,section) -> (doc, expires)

def _active_pack() -> Tuple[str,str]:
    v = cfg_get("PROMPT_PACK_ACTIVE", "edg@latest-approved")
    if "@" not in v: return v, "latest-approved"
    p, ver = v.split("@",1)
    return p, ver

def _cache_get(pack, ver, section) -> Optional[dict]:
    key = (pack, ver, section)
    item = _cache.get(key)
    if item and item[1] > time.time():
        return item[0]
    return None

def _cache_set(pack, ver, section, doc, ttl=30):
    _cache[(pack,ver,section)] = (doc, time.time()+ttl)

def retrieve_template(section_id: str, tags: Optional[List[str]]=None) -> dict:
    pack, ver = _active_pack()
    cached = _cache_get(pack, ver, section_id)
    if cached: return cached

    # Build filter
    flt = f"pack_id eq '{pack}' and status eq 'approved' and section_id eq '{section_id}'"
    if ver != "latest-approved":
        flt += f" and version eq '{ver}'"

    search_text = " ".join(tags or [section_id])

    results = _client.search(
        search_text=search_text,
        filter=flt,
        top=3,
        query_type="simple",
    )

    hit = None
    for d in results:
        hit = {
          "template": d["template_text"],
          "pack_id": d["pack_id"],
          "version": d["version"],
          "metadata": json.loads(d["metadata_json"]) if d.get("metadata_json") else {}
        }
        break

    if not hit:
        # Fallback: ask for any template for the section (latest approved for pack)
        results = _client.search(search_text=section_id, filter=f"pack_id eq '{pack}' and status eq 'approved' and section_id eq '{section_id}'", top=1)
        for d in results:
            hit = {
              "template": d["template_text"],
              "pack_id": d["pack_id"],
              "version": d["version"],
              "metadata": json.loads(d["metadata_json"]) if d.get("metadata_json") else {}
            }
            break

    if not hit:
        raise LookupError(f"No template found for {pack}@{ver}:{section_id}")

    _cache_set(pack, ver, section_id, hit)
    return hit