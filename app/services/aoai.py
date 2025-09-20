# app/services/aoai.py
import os, httpx
from .secrets import get_secret
from .appcfg import get

AOAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
# Pull key from Key Vault at runtime (cached)
def _headers():
    return {"api-key": get_secret("aoai-key-dev"), "Content-Type": "application/json"}

def _deployment(use: str) -> str:
    if use == "manager":
        return get("MODEL.MANAGER", default="gpt-4.1-manager")
    # default worker
    return get("MODEL.WORKER", default="gpt-4.1-mini-worker")

async def chat_completion(messages, *, use="worker", max_tokens=800, temperature=0.2, timeout=60):
    dep = _deployment(use)
    url = f"{AOAI_ENDPOINT}/openai/deployments/{dep}/chat/completions?api-version=2024-10-01-preview"
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=_headers(), json=payload)
    if r.status_code == 404:
        # Clear error for bad deployment name (test case)
        raise ValueError(f"MODEL.WORKER/manager points to unknown deployment: '{dep}'")
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]