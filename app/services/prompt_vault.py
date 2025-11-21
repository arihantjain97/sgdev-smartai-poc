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
    """
    Default pack when caller does not pass pack_hint.
    
    We keep 'latest-approved' so _resolve_pack() will always resolve
    the real version via PROMPT_PACK_LATEST.EDG in App Config.
    """
    return "edg", "latest-approved"

def _resolve_pack(pack_hint: Optional[str]) -> Tuple[str, str]:
    """
    Resolve pack and version from hint or fall back to active pack.
    Accept forms: "psg", "edg", "psg@1.0.0".

    Returns canonical (PACK_ID_UPPER, version), because index rows store
    pack_id as uppercase (e.g., "PSG", "EDG").
    """
    if pack_hint:
        if "@" in pack_hint:
            p, ver = pack_hint.split("@", 1)
        else:
            p, ver = pack_hint, "latest-approved"
    else:
        p, ver = _active_pack()  # defaults to EDG@latest-approved

    p = (p or "").strip()
    ver = (ver or "latest-approved").strip()

    # Canonicalise pack IDs to uppercase -> matches index docs with pack_id="PSG"/"EDG"
    p_norm = p.upper()

    # Map "latest-approved" -> concrete version via per-pack config
    if ver == "latest-approved":
        key = f"PROMPT_PACK_LATEST.{p_norm}"  # e.g. PROMPT_PACK_LATEST.PSG
        pinned = (cfg_get(key) or "").strip()
        if pinned:
            ver = pinned

    return p_norm, ver

def _cache_get(pack, ver, section, variant) -> Optional[dict]:
    key = (pack, ver, section, variant or "")
    item = _cache.get(key)
    if item and item[1] > time.time():
        return item[0]
    return None

def _cache_set(pack, ver, section, variant, doc, ttl=30):
    _cache[(pack,ver,section,variant or "")] = (doc, time.time()+ttl)

def retrieve_template(
    section_id: str,
    tags: Optional[List[str]] = None,
    section_variant: Optional[str] = None,
    pack_hint: Optional[str] = None,
) -> dict:
    """
    Retrieve the template for a given section/pack.

    - pack_hint: "psg", "psg@1.0.3", etc. (resolved via _resolve_pack)
    - If a concrete version is requested (ver != "latest-approved") and not found,
      we hard-fail with LookupError instead of silently downgrading.
    """
    pack, ver = _resolve_pack(pack_hint)
    cached = _cache_get(pack, ver, section_id, section_variant)
    if cached:
        return cached

    flt = f"pack_id eq '{pack}' and status eq 'approved' and section_id eq '{section_id}'"
    if ver != "latest-approved":
        flt += f" and version eq '{ver}'"

    search_text = " ".join(tags or [section_id])
    SELECT_FIELDS = ["template_text", "metadata_json"]

    # Primary search: honour pack + version strictly
    results = _client.search(
        search_text=search_text,
        filter=flt,
        top=3,
        query_type="simple",
        select=SELECT_FIELDS,
    )

    hit: Optional[dict] = None
    for d in results:
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

    # If explicit version requested and nothing found → hard fail
    if not hit and ver != "latest-approved":
        raise LookupError(f"No template found for {pack}@{ver}:{section_id}")

    # Optional, looser fallback only for "latest-approved"
    if not hit and ver == "latest-approved":
        results = _client.search(
            search_text=section_id,
            filter=f"pack_id eq '{pack}' and status eq 'approved' and section_id eq '{section_id}'",
            top=1,
            select=SELECT_FIELDS,
        )
        for d in results:
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