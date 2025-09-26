# app/services/aoai.py
import os, httpx
from .secrets import get_secret
from .appcfg import get

def _get_endpoint() -> str:
    ep = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not ep:
        raise RuntimeError("AOAI not configured: set AZURE_OPENAI_ENDPOINT")
    return ep.rstrip("/")

# Pull key from Key Vault at runtime (cached)
def _headers():
    return {"api-key": get_secret("aoai-key-dev"), "Content-Type": "application/json"}

def _deployment(use: str) -> str:
    if use == "manager":
        dep = get("MODEL.MANAGER", default="gpt-4.1-manager")
    else:
        dep = get("MODEL.WORKER", default="gpt-4.1-mini-worker")
    return dep.strip()

async def chat_completion(messages, *, use="worker", max_tokens=800, temperature=0.2, timeout=60):
    endpoint = _get_endpoint()
    dep = _deployment(use)
    #url = f"{endpoint}/openai/deployments/{dep}/chat/completions?api-version=2024-10-01-preview"
    url = f"{endpoint}/openai/deployments/{dep}/chat/completions?api-version=2024-02-15-preview"  # <= use a known-stable version

    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=_headers(), json=payload)
    if r.status_code == 404:
        raise ValueError(f"MODEL.WORKER/manager points to unknown deployment: '{dep}'")
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Surface the AOAI body so you see the real reason in your 500
        raise RuntimeError(f"AOAI {r.status_code}: {r.text[:500]}") from e

    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"AOAI returned non-JSON ({r.status_code}): {r.text[:500]}")
    return data["choices"][0]["message"]["content"]