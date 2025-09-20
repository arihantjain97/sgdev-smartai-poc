from fastapi import FastAPI, UploadFile, Form
from pydantic import BaseModel
from app.services import storage, taxonomy, composer, evaluator
from app.services.aoai import chat_completion

#test

app = FastAPI(title="SmartAI Proposal Builder (Dev)")

# health + root so the platform has a quick 200
@app.get("/")
def root():
    return {"ok": True, "service": "smartai-api"}

@app.get("/health")
def health():
    return {"ok": True}

class SessionCreate(BaseModel):
    grant: str = "EDG"
    company_name: str | None = None

@app.post("/v1/session")
async def create_session(body: SessionCreate):
    table = storage.sessions()
    from uuid import uuid4; sid = f"s_{uuid4().hex[:8]}"
    entity = {"PartitionKey":"session","RowKey":sid,"grant":body.grant,"status":"new"}
    table.upsert_entity(entity)
    return {"session_id": sid}

@app.get("/v1/session/{sid}/checklist")
async def checklist(sid: str):
    # Toy: two drafts + three uploads
    tasks = [
      {"id":"acra_extract", "type":"upload"},
      {"id":"audited_financials","type":"upload"},
      {"id":"vendor_quotation","type":"upload"},
      {"id":"consultancy_scope","type":"draft"},
      {"id":"business_case","type":"draft"}
    ]
    return {"session_id":sid,"tasks":tasks}

class DraftReq(BaseModel):
    session_id: str
    section_id: str
    inputs: dict = {}

@app.post("/v1/grants/edg/draft")
async def draft(req: DraftReq):
    fw = taxonomy.pick_framework(req.section_id)

    # --- Evidence selection rules ---
    # 1) If caller provides inputs.evidence_labels (list), use that order.
    # 2) Else if caller provides legacy inputs.evidence_label (single), use it.
    # 3) Else use sensible defaults per section.
    DEFAULT_EVIDENCE_BY_SECTION = {
        "business_case": ["acra_extract", "audited_financials"],
        "consultancy_scope": ["acra_extract"]
    }
    labels = None
    try:
        labels = req.inputs.get("evidence_labels")
        if isinstance(labels, str):
            labels = [labels]
    except Exception:
        labels = None
    if not labels:
        single = req.inputs.get("evidence_label")
        if single:
            labels = [single]
    if not labels:
        labels = DEFAULT_EVIDENCE_BY_SECTION.get(req.section_id, [req.section_id])

    # --- Load snippets in order; cap total length ---
    MAX_CHARS = int(req.inputs.get("evidence_char_cap", 6000))
    parts = []
    evidence_used = []
    for label in labels:
        blob_name = f"{req.session_id}_{label}.txt"
        try:
            txt = storage.get_text("evidence", blob_name)
            if not txt:
                continue
            header = f"\n\n--- [evidence:{label}] ---\n"
            parts.append(header + txt)
            evidence_used.append(label)
            if sum(len(p) for p in parts) >= MAX_CHARS:
                break
        except Exception:
            # Missing evidence file is OK; skip
            continue

    snippet = ""
    if parts:
        joined = "".join(parts)
        snippet = joined[:MAX_CHARS]

    # Surface the labels into inputs so the prompt can mention them
    if evidence_used:
        req.inputs["evidence_labels"] = evidence_used
        req.inputs["evidence_label"] = ",".join(evidence_used)  # back-compat for any single-label template

    msgs = composer.compose_instruction(req.section_id, fw, req.inputs, snippet)
    out = await chat_completion(msgs, use="worker")
    ev = evaluator.score(out, require_tokens=["source:"] if any(c.isdigit() for c in out) else None)
    return {
        "section_id": req.section_id,
        "framework": fw,
        "evidence_used": evidence_used,
        "output": out,
        "evaluation": ev
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)