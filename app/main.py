from fastapi import FastAPI, UploadFile, Form
from pydantic import BaseModel
from services import storage, taxonomy, composer, evaluator
from services.aoai import chat_completion

app = FastAPI(title="SmartAI Proposal Builder (Dev)")

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
    # Try to load evidence snippet if exists (toy: hardcoded filename)
    snippet=""
    try: snippet = storage.get_text("evidence", f"{req.session_id}_{req.section_id}.txt")
    except: pass
    msgs = composer.compose_instruction(req.section_id, fw, req.inputs, snippet)
    out = await chat_completion(msgs, use="worker")
    ev = evaluator.score(out, require_tokens=["source:"] if any(c.isdigit() for c in out) else None)
    return {"section_id": req.section_id, "framework": fw, "output": out, "evaluation": ev}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)