# app/services/appcfg.py
import os, time
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.appconfiguration import AzureAppConfigurationClient

_ENDPOINT = os.environ["APPCONFIG_ENDPOINT"]
_LABEL   = os.environ.get("APPCONFIG_LABEL", None)
_cred    = DefaultAzureCredential()
_client  = AzureAppConfigurationClient(_ENDPOINT, credential=_cred)

_cache: dict[tuple[str, Optional[str]], tuple[str, float]] = {}  # (key,label) -> (val, expires)

def get(key: str, default: Optional[str] = None, *, ttl_seconds: int = 30) -> str:
    now = time.time()
    k = (key, _LABEL)
    if k in _cache and _cache[k][1] > now: return _cache[k][0]
    try:
        cfg = _client.get_configuration_setting(key=key, label=_LABEL)
        val = cfg.value
    except Exception:
        val = default
    _cache[k] = (val, now + ttl_seconds)
    return val

def get_bool(key: str, default: bool = False) -> bool:
    v = get(key, None)
    if v is None: return default
    return str(v).lower() in ("1","true","yes","on")