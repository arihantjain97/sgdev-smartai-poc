import os, httpx

AOAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AOAI_KEY = os.environ["AZURE_OPENAI_API_KEY"]
DEP_MANAGER = os.environ["AOAI_MANAGER_DEPLOYMENT"]
DEP_WORKER  = os.environ["AOAI_WORKER_DEPLOYMENT"]

HEADERS = {"api-key": AOAI_KEY, "Content-Type": "application/json"}

async def chat_completion(messages, *, use="worker", max_tokens=800, temperature=0.2, timeout=60):
    deployment = DEP_MANAGER if use=="manager" else DEP_WORKER
    url = f"{AOAI_ENDPOINT}/openai/deployments/{deployment}/chat/completions?api-version=2024-10-01-preview"
    payload = {"messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=HEADERS, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]