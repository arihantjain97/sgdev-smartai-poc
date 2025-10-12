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

_cache: Dict[Tuple[str,str,str,str], Tuple[dict,float]] = {}
# key=(pack,ver,section,variant) -> (doc, expires)

def _active_pack() -> Tuple[str,str]:
    v = cfg_get("PROMPT_PACK_ACTIVE", "edg@latest-approved")
    if "@" not in v: return v, "latest-approved"
    p, ver = v.split("@",1)
    return p, ver

def _resolve_pack(pack_hint: Optional[str]) -> Tuple[str, str]:
    """
    Resolve pack and version from hint or fall back to active pack.
    Accept forms: "psg", "edg", "psg@1.0.0"
    """
    if pack_hint:
        if "@" in pack_hint:
            p, ver = pack_hint.split("@", 1)
            return p.strip(), ver.strip()
        return pack_hint.strip(), "latest-approved"
    return _active_pack()

def _cache_get(pack, ver, section, variant) -> Optional[dict]:
    key = (pack, ver, section, variant or "")
    item = _cache.get(key)
    if item and item[1] > time.time():
        return item[0]
    return None

def _cache_set(pack, ver, section, variant, doc, ttl=30):
    _cache[(pack,ver,section,variant or "")] = (doc, time.time()+ttl)

def retrieve_template(section_id: str, tags: Optional[List[str]] = None, section_variant: Optional[str] = None, pack_hint: Optional[str] = None) -> dict:
    # NEW: resolve desired pack first (honors pack_hint if provided)
    pack, ver = _resolve_pack(pack_hint)
    cached = _cache_get(pack, ver, section_id, section_variant)
    if cached:
        return cached

    flt = f"pack_id eq '{pack}' and status eq 'approved' and section_id eq '{section_id}'"
    if ver != "latest-approved":
        flt += f" and version eq '{ver}'"

    search_text = " ".join(tags or [section_id])

    # ONLY ask for fields that are retrievable in your index
    SELECT_FIELDS = ["template_text", "metadata_json"]

    results = _client.search(
        search_text=search_text,
        filter=flt,
        top=3,
        query_type="simple",
        select=SELECT_FIELDS,
    )

    hit = None
    for d in results:
        meta = {}
        try:
            meta = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            meta = {}
        hit = {
            "template": d.get("template_text", ""),
            "pack_id": meta.get("pack_id"),      # <— from metadata_json
            "version": meta.get("version"),      # <— from metadata_json
            "metadata": meta,
        }
        break

    if not hit:
        # Fallback search (keep the same select)
        results = _client.search(
            search_text=section_id,
            filter=f"pack_id eq '{pack}' and status eq 'approved' and section_id eq '{section_id}'",
            top=1,
            select=SELECT_FIELDS,
        )
        for d in results:
            meta = {}
            try:
                meta = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                meta = {}
            hit = {
                "template": d.get("template_text", ""),
                "pack_id": meta.get("pack_id"),
                "version": meta.get("version"),
                "metadata": meta,
            }
            break

    if not hit:
        raise LookupError(f"No template found for {pack}@{ver}:{section_id}")

    _cache_set(pack, ver, section_id, section_variant, hit)
    return hit