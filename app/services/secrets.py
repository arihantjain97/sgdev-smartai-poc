# app/services/secrets.py
import os, time
from typing import Optional
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

_KV_URI = os.environ["KEYVAULT_URI"]
_cred = DefaultAzureCredential()
_client = SecretClient(vault_url=_KV_URI, credential=_cred)

_cache: dict[str, tuple[str, float]] = {}  # name -> (value, expires_at)

def get_secret(name: str, ttl_seconds: int = 900) -> str:
    now = time.time()
    if name in _cache and _cache[name][1] > now:
        return _cache[name][0]
    val = _client.get_secret(name).value
    _cache[name] = (val, now + ttl_seconds)
    return val