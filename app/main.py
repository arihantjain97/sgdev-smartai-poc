from typing import Any, Optional, Dict, List
from fastapi import FastAPI, UploadFile, Form, Query, HTTPException, Response
from pydantic import BaseModel, Field
from app.services import storage, taxonomy, composer, evaluator
from app.services.aoai import chat_completion
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.services.appcfg import get_bool, get as cfg_get
from app.services.prompt_vault import _resolve_pack as _pv_resolve
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from pathlib import Path
import os
import json
import yaml
import logging

#test

app = FastAPI(title="SmartAI Proposal Builder (Dev)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "https://wonderful-pebble-0bc6fc600.1.azurestaticapps.net" ],
    allow_methods=["*"], allow_headers=["*"]
)

class NoCache(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        return resp
app.add_middleware(NoCache)

# health + root so the platform has a quick 200
@app.get("/")
def root():
    return {"ok": True, "service": "smartai-api"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/v1/config/features")
def features():
    packs_latest = {
        "EDG": cfg_get("PROMPT_PACK_LATEST.EDG", None),
        "PSG": cfg_get("PROMPT_PACK_LATEST.PSG", None),
    }
    return {
        "feature_psg_enabled": get_bool("FEATURE_PSG_ENABLED", False),
        "model_worker": cfg_get("MODEL.WORKER", "gpt-4.1-mini-worker"),
        "packs_latest": packs_latest,
    }

@app.get("/v1/prompts/active")
def prompts_active():
    """
    Lightweight observability for prompt configuration.
    
    All values are derived from PROMPT_PACK_LATEST.* and other config keys.
    No code should ever read PROMPT_PACK_ACTIVE anymore.
    """
    packs_latest = {
        "EDG": cfg_get("PROMPT_PACK_LATEST.EDG", None),
        "PSG": cfg_get("PROMPT_PACK_LATEST.PSG", None),
    }
    return {
        "packs_latest": packs_latest,
        "model_worker": cfg_get("MODEL.WORKER", "gpt-4.1-mini-worker"),
        "model_manager": cfg_get("MODEL.MANAGER", "gpt-4.1-mini-manager"),
        "feature_psg_enabled": get_bool("FEATURE_PSG_ENABLED", False),
        "appconfig_label": os.environ.get("APPCONFIG_LABEL", "dev"),
    }

class SessionCreate(BaseModel):
    grant: str = "EDG"
    company_name: str | None = None

# ------------------------------------------------------------
# Generic Fact Schema (base for all session metadata)
# ------------------------------------------------------------
class SessionFactsReq(BaseModel):
    """
    Generic session fact capture for eligibility, profiling, diagnostics.
    Works across grants, lead-gen, vendor profiling, and other use cases.
    """
    # Common across SME-type use cases
    local_equity_pct: float | None = Field(None, ge=0, le=100, description="Local equity percentage")
    turnover: float | None = Field(None, ge=0, description="Annual turnover/revenue")
    headcount: int | None = Field(None, ge=0, description="Number of employees")

    # Grant-specific attestations (optional)
    used_in_singapore: bool | None = Field(None, description="Will the grant outcome be used in Singapore?")
    no_payment_before_application: bool | None = Field(None, description="No payment made before application?")

    # Open extension for other verticals (lead-gen, diagnostics, etc.)
    extra: dict[str, Any] | None = Field(
        None,
        description="Free-form key-value facts, e.g. {'industry':'F&B','budget_range':'<50k'}"
    )

@app.post("/v1/session")
async def create_session(body: SessionCreate):
    table = storage.sessions()
    from uuid import uuid4; sid = f"s_{uuid4().hex[:8]}"
    entity = {"PartitionKey":"session","RowKey":sid,"grant":body.grant,"status":"new"}
    table.upsert_entity(entity)
    return {"session_id": sid}

# ------------------------------------------------------------
# Session Getter (debug / general retrieval)
# ------------------------------------------------------------
@app.get("/v1/session/{sid}")
async def get_session(sid: str):
    """
    Retrieve session metadata including all facts.
    """
    try:
        sess = storage.sessions().get_entity(partition_key="session", row_key=sid)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": sid, "session": dict(sess)}

# ------------------------------------------------------------
# Unified Fact Upsert Endpoint
# ------------------------------------------------------------
@app.post("/v1/session/{sid}/facts")
@app.post("/v1/session/{sid}/eligibility")  # backward-compatible alias
async def upsert_session_facts(sid: str, body: SessionFactsReq):
    """
    Upsert structured facts for a session (eligibility, profiling, diagnostics).
    
    This endpoint works as both:
    - /facts: Generic key-value fact capture for any use case
    - /eligibility: Backward-compatible alias for grant eligibility data
    
    Supports:
    - EDG/PSG grant eligibility (local_equity_pct, turnover, headcount)
    - Grant attestations (used_in_singapore, no_payment_before_application)
    - Free-form facts via 'extra' dict for lead-gen, diagnostics, vendor profiling
    """
    try:
        sess = storage.sessions().get_entity(partition_key="session", row_key=sid)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")

    # Convert model to dict, excluding unset fields
    payload = body.model_dump(exclude_unset=True)

    # Flatten extra dict if present
    extras = payload.pop("extra", {}) or {}
    
    # Merge structured fields into session
    for k, v in payload.items():
        sess[k] = v
    
    # Merge dynamic facts at same level
    for k, v in extras.items():
        sess[k] = v

    storage.sessions().upsert_entity(sess)
    
    # Return combined facts for verification
    all_facts = payload.copy()
    all_facts.update(extras)
    
    return {"session_id": sid, "facts": all_facts}

# ------------------------------------------------------------
# Validation Stub (non-blocking)
# ------------------------------------------------------------
@app.post("/v1/session/{sid}/validate")
async def validate_session(sid: str):
    try:
        sess = storage.sessions().get_entity(partition_key="session", row_key=sid)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")

    grant = (sess.get("grant") or "").upper()

    checks = []

    # PSG rule: equity >= 30%
    if grant == "PSG":
        equity = float(sess.get("local_equity_pct") or 0)
        if equity < 30:
            checks.append({
                "code": "PSG.ELIG.LOCAL_EQUITY_MIN_30",
                "level": "warning",
                "message": "Local equity below 30% (PSG minimum)."
            })

    return {"session_id": sid, "checks": checks}

@app.get("/v1/session/{sid}/checklist")
async def checklist(sid: str):
    # Read the session to know which grant this session is for
    try:
        sess = storage.sessions().get_entity(partition_key="session", row_key=sid)
        grant = (sess.get("grant") or "EDG").upper()
    except Exception:
        # If session not found or table hiccups, fall back safely
        grant = "EDG"

    if grant == "PSG":
        # PSG: uploads + drafts (no variant needed)
        tasks = [
            {"id": "vendor_quotation", "type": "upload"},
            {"id": "cost_breakdown", "type": "upload"},
            {"id": "business_impact", "type": "draft", "section_variant": None},
            {"id": "solution_description", "type": "draft", "section_variant": None},
            # (optional) compliance summary draft for your reviewers/UI
            {"id": "compliance_summary", "type": "draft", "section_variant": None},
        ]
    else:
        # EDG: uploads + drafts (WITH a variant example)
        tasks = [
            {"id": "acra_bizfile", "type": "upload"},
            {"id": "audited_financials", "type": "upload"},
            {"id": "consultancy_scope", "type": "draft", "section_variant": None},
            # Example: drive the "About the Project – I&P (Automation)" variant
            {"id": "about_project", "type": "draft",
             "section_variant": "about_project.i_and_p.automation"},
            # (optional) include a Market Access draft variant
            {"id": "expansion_plan", "type": "draft",
             "section_variant": "expansion_plan.market_access"},
        ]

    return {"session_id": sid, "grant": grant, "tasks": tasks}

# ============================================================
# Dynamic Checklist Helper Functions
# ============================================================

def load_pack_yml(pack: str, version: str) -> Optional[Dict[str, Any]]:
    """
    Load pack.yml from vault directory.
    Returns None if pack.yml not found.
    """
    try:
        vault_root = Path("app/vault")
        # Find pack directory matching pack and version
        # Pattern: EDG.v1, PSG.v1, etc.
        pack_dir = None
        for p in vault_root.glob("*.*"):
            pack_id = p.name.split(".")[0].upper()
            if pack_id == pack.upper():
                pack_yml = p / "pack.yml"
                if pack_yml.exists():
                    pack_data = yaml.safe_load(pack_yml.read_text(encoding="utf-8"))
                    # Check if version matches (or use first found if version not critical)
                    if pack_data.get("version") == version or not version:
                        pack_dir = p
                        break
        
        if pack_dir:
            pack_yml = pack_dir / "pack.yml"
            if pack_yml.exists():
                return yaml.safe_load(pack_yml.read_text(encoding="utf-8"))
    except Exception as e:
        logging.warning(f"Failed to load pack.yml for {pack}@{version}: {e}")
    return None

def query_template_index(pack: str, version: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Query Azure Search index for all templates matching pack and version.
    Returns dict mapping section_id to list of template variants.
    """
    templates_by_section: Dict[str, List[Dict[str, Any]]] = {}
    
    try:
        endpoint = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
        query_key = os.environ["AZURE_SEARCH_QUERY_KEY"]
        index_name = os.environ.get("AZURE_SEARCH_INDEX", "smartai-prompts")
        
        client = SearchClient(endpoint, index_name, AzureKeyCredential(query_key))
        
        # Resolve version if "latest-approved"
        if version == "latest-approved":
            _, resolved_ver = _pv_resolve(pack.lower())
        else:
            resolved_ver = version
        
        flt = f"pack_id eq '{pack.upper()}' and status eq 'approved'"
        if resolved_ver != "latest-approved":
            flt += f" and version eq '{resolved_ver}'"
        
        results = client.search(
            search_text="*",
            filter=flt,
            top=200,
            select=["metadata_json"],
        )
        
        for d in results:
            try:
                meta = json.loads(d.get("metadata_json") or "{}")
                section_id = meta.get("section_id")
                template_key = meta.get("template_key", "")
                
                if section_id:
                    if section_id not in templates_by_section:
                        templates_by_section[section_id] = []
                    
                    # Infer variant from template_key
                    # Template keys use __ (e.g., "about_project__i_and_p__automation")
                    # Variants use . (e.g., "about_project.i_and_p.automation")
                    variant = None
                    section_id_from_meta = meta.get("section_id", "")
                    
                    # If template_key has __ and section_id is different, this is likely a variant
                    if "__" in template_key and section_id_from_meta:
                        # Check if template_key represents a variant of section_id
                        # e.g., section_id="about_project", template_key="about_project__i_and_p__automation"
                        if template_key.startswith(section_id_from_meta + "__"):
                            # Extract variant part: everything after section_id + "__"
                            variant_part = template_key[len(section_id_from_meta) + 2:]  # +2 for "__"
                            if variant_part:
                                # Convert __ to . for variant format
                                variant = f"{section_id_from_meta}.{variant_part.replace('__', '.')}"
                    
                    templates_by_section[section_id].append({
                        "template_key": template_key,
                        "section_id": section_id,
                        "variant": variant,
                        "retrieval_tags": meta.get("retrieval_tags", []),
                        "metadata": meta,
                    })
            except Exception as e:
                logging.warning(f"Failed to parse template metadata: {e}")
                continue
                
    except Exception as e:
        logging.warning(f"Failed to query template index: {e}")
    
    return templates_by_section

def get_upload_tasks_for_pack(pack: str) -> List[Dict[str, str]]:
    """
    Get upload tasks for a pack. Currently hardcoded based on existing checklist logic.
    In future, this could be derived from pack.yml or evidence_hints.
    """
    if pack.upper() == "PSG":
        return [
            {"id": "vendor_quotation", "type": "upload"},
            {"id": "cost_breakdown", "type": "upload"},
        ]
    else:  # EDG
        return [
            {"id": "acra_bizfile", "type": "upload"},
            {"id": "audited_financials", "type": "upload"},
        ]

def resolve_variant_for_section(
    section_id: str,
    templates: List[Dict[str, Any]],
    pack_yml: Dict[str, Any],
    session: Dict[str, Any]
) -> Optional[str]:
    """
    Resolve which variant to use for a section.
    Rules:
    1. If session specifies sub-flow (innovation_productivity, market_access) -> match retrieval_tags
    2. Else if pack.yml has default variant -> use it
    3. Else -> None
    """
    if not templates:
        return None
    
    # Rule 1: Check session for sub-flow hints
    # Look for tags in session that might indicate sub-flow
    session_tags = []
    for key, val in session.items():
        if isinstance(val, (str, int, float)) and val:
            session_tags.append(str(val).lower())
    
    # Check for innovation_productivity or market_access hints
    for template in templates:
        tags = [t.lower() for t in template.get("retrieval_tags", [])]
        if "innovation_productivity" in tags or "automation" in tags or "product_development" in tags:
            if any(hint in session_tags for hint in ["automation", "productivity", "innovation"]):
                return template.get("variant")
        if "market_access" in tags:
            if any(hint in session_tags for hint in ["market", "expansion", "access"]):
                return template.get("variant")
    
    # Rule 2: Check pack.yml for default variant (if templates have section_variant defaults)
    # This would be in pack.yml defaults, but we don't have that structure yet
    # For now, prefer variants that match common patterns
    
    # Rule 3: If only one template, use its variant (or None)
    if len(templates) == 1:
        return templates[0].get("variant")
    
    # If multiple templates, prefer the one without variant (default) or first one
    for template in templates:
        if not template.get("variant"):
            return None  # Default template, no variant
    
    # Return first variant found
    return templates[0].get("variant") if templates else None

def build_dynamic_checklist(pack: str, active_version: str, session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build dynamic checklist from pack.yml and template index.
    Returns list of tasks in format: [{"id": "...", "type": "upload|draft", "section_variant": ...}]
    """
    tasks: List[Dict[str, Any]] = []
    
    try:
        # Load pack.yml
        pack_yml = load_pack_yml(pack, active_version)
        if not pack_yml:
            # Fallback to hardcoded checklist
            logging.warning(f"pack.yml not found for {pack}@{active_version}, using fallback")
            return get_fallback_checklist(pack)
        
        # Query template index
        templates_by_section = query_template_index(pack, active_version)
        
        # Get upload tasks
        upload_tasks = get_upload_tasks_for_pack(pack)
        tasks.extend(upload_tasks)
        
        # Get draft tasks from pack.yml templates
        templates_config = pack_yml.get("templates", {})
        
        # Build ordered list of draft sections from pack.yml
        # Prefer explicit sections list, else use templates dict keys in order
        sections_order = pack_yml.get("sections", [])
        if not sections_order:
            # Derive from templates keys (preserves YAML order in Python 3.7+)
            sections_order = list(templates_config.keys())
        
        # Process each section from templates config
        # Group by section_id to avoid duplicates, but preserve order from pack.yml
        sections_processed = {}  # section_id -> (variant, order)
        section_order_map = {}  # section_id -> first occurrence order
        
        for idx, section_key in enumerate(sections_order):
            template_config = templates_config.get(section_key, {})
            section_id = template_config.get("section_id", section_key)
            
            # Track first occurrence order for each section_id
            if section_id not in section_order_map:
                section_order_map[section_id] = idx
            
            # Skip if template status is not approved (unless pack status is approved)
            template_status = template_config.get("status", pack_yml.get("status", "draft"))
            if template_status != "approved" and pack_yml.get("status") != "approved":
                continue
            
            # Check if section exists in index
            section_templates = templates_by_section.get(section_id, [])
            if not section_templates:
                logging.warning(f"Section {section_id} not found in index, skipping")
                continue
            
            # Store section for later processing (we'll resolve variant after collecting all)
            if section_id not in sections_processed:
                sections_processed[section_id] = {
                    "templates": section_templates,
                    "order": section_order_map[section_id]
                }
        
        # Now process sections in order, resolving variants
        sorted_sections = sorted(sections_processed.items(), key=lambda x: x[1]["order"])
        
        for section_id, section_data in sorted_sections:
            section_templates = section_data["templates"]
            
            # Resolve variant
            variant = resolve_variant_for_section(section_id, section_templates, pack_yml, session)
            
            # Ensure variant uses . format (not __)
            if variant and "__" in variant:
                variant = variant.replace("__", ".")
            
            tasks.append({
                "id": section_id,
                "type": "draft",
                "section_variant": variant
            })
        
    except Exception as e:
        logging.error(f"Error building dynamic checklist: {e}")
        # Fallback to hardcoded
        return get_fallback_checklist(pack)
    
    return tasks

def get_fallback_checklist(pack: str) -> List[Dict[str, Any]]:
    """Fallback to hardcoded checklist matching existing /checklist endpoint."""
    if pack.upper() == "PSG":
        return [
            {"id": "vendor_quotation", "type": "upload"},
            {"id": "cost_breakdown", "type": "upload"},
            {"id": "business_impact", "type": "draft", "section_variant": None},
            {"id": "solution_description", "type": "draft", "section_variant": None},
            {"id": "compliance_summary", "type": "draft", "section_variant": None},
        ]
    else:  # EDG
        return [
            {"id": "acra_bizfile", "type": "upload"},
            {"id": "audited_financials", "type": "upload"},
            {"id": "consultancy_scope", "type": "draft", "section_variant": None},
            {"id": "about_project", "type": "draft", "section_variant": "about_project.i_and_p.automation"},
            {"id": "expansion_plan", "type": "draft", "section_variant": "expansion_plan.market_access"},
        ]

@app.get("/v1/session/{sid}/checklisttest")
async def checklist_test(sid: str):
    """
    Dynamic checklist endpoint built from pack.yml and template index.
    This is a test endpoint for verification before replacing the original /checklist.
    """
    try:
        sess = storage.sessions().get_entity(partition_key="session", row_key=sid)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get pack from session (rename grant -> pack)
    pack = (sess.get("grant") or "EDG").upper()
    
    # Resolve active version
    try:
        # Use same mechanism as draft endpoint
        active_version = cfg_get(f"PROMPT_PACK_LATEST.{pack}", None)
        if not active_version:
            # Fallback: try to get from index or use latest
            active_version = "latest-approved"
    except Exception:
        active_version = "latest-approved"
    
    # Build dynamic checklist
    try:
        tasks = build_dynamic_checklist(pack, active_version, dict(sess))
    except Exception as e:
        logging.warning(f"Dynamic checklist failed, using fallback: {e}")
        tasks = get_fallback_checklist(pack)
    
    return {"session_id": sid, "pack": pack, "tasks": tasks}

class DraftReq(BaseModel):
    session_id: str
    section_id: str
    section_variant: str | None = None
    inputs: dict = {}


# ------------------------------------------------------------
# Shared Draft Helper (grant-agnostic)
# ------------------------------------------------------------
async def _do_draft(req: DraftReq, response: Response, *, pack_hint: str):
    """
    Unified draft logic for any grant type.
    Uses pack_hint to select the appropriate prompt pack (edg, psg, etc.)
    """
    fw = taxonomy.pick_framework(req.section_id)

    # --- Evidence selection rules (EDG + PSG comprehensive defaults) ---
    # 1) If caller provides inputs.evidence_labels (list), use that order.
    # 2) Else if caller provides legacy inputs.evidence_label (single), use it.
    # 3) Else use sensible defaults per section.
    DEFAULT_EVIDENCE_BY_SECTION = {
        # EDG sections
        "business_case": ["acra_bizfile", "audited_financials"],
        "consultancy_scope": ["acra_bizfile"],
        "about_company": ["acra_bizfile", "audited_financials"],
        "about_project": ["acra_bizfile", "audited_financials"],
        "expansion_plan": ["acra_bizfile", "audited_financials"],
        "project_outcomes": ["audited_financials"],
        "project_milestones": ["acra_bizfile"],
        # PSG sections
        "solution_description": ["vendor_quotation", "product_brochure"],
        "vendor_quotation": ["vendor_quotation"],
        "cost_breakdown": ["cost_breakdown"],
        "business_impact": ["vendor_quotation", "cost_breakdown"],
        "compliance_summary": ["vendor_quotation", "cost_breakdown", "deployment_location_proof"],
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

    # --- Pack selection via pack_hint (EDG/PSG/etc.) ---
    try:
        msgs, packver, evidence_order_used = composer.compose_instruction(
            req.section_id, 
            fw, 
            req.inputs or {}, 
            snippet,
            section_variant=req.section_variant,
            pack_hint=pack_hint  # IMPORTANT: drives pack selection
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt Vault error: {type(e).__name__}: {e}")

    response.headers["x-prompt-pack"] = packver

    # --- Call AOAI ---
    try:
        out = await chat_completion(msgs, use="worker")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Model deployment error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    # --- Soft evaluator ---
    ev = evaluator.score(out, require_tokens=["source:"] if any(c.isdigit() for c in out) else None)

    # --- Lightweight warnings (grant-specific checks) ---
    warnings = []

    return {
        "section_id": req.section_id,
        "framework": fw,
        "evidence_used": evidence_order_used,  # Use the ordered labels from composer
        "output": out,
        "evaluation": ev,
        "warnings": warnings,
    }


# ------------------------------------------------------------
# Unified Draft Endpoint (grant-agnostic)
# ------------------------------------------------------------
@app.post("/v1/draft")
async def draft_any(req: DraftReq, response: Response):
    """
    Grant-agnostic draft endpoint.
    Determines grant type from session and selects appropriate prompt pack.
    """
    # Determine grant/pack from the session
    try:
        sess = storage.sessions().get_entity(partition_key="session", row_key=req.session_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Session not found")
    
    grant = (sess.get("grant") or "EDG").lower()
    return await _do_draft(req, response, pack_hint=grant)


# ------------------------------------------------------------
# Backward-Compatible Grant-Specific Wrappers
# ------------------------------------------------------------
@app.post("/v1/grants/edg/draft")
async def draft_edg(req: DraftReq, response: Response):
    """
    EDG-specific draft endpoint (backward-compatible wrapper).
    Forwards to unified draft logic with pack_hint='edg'.
    """
    return await _do_draft(req, response, pack_hint="edg")


@app.post("/v1/grants/psg/draft")
async def draft_psg(req: DraftReq, response: Response):
    """
    PSG-specific draft endpoint (backward-compatible wrapper).
    Forwards to unified draft logic with pack_hint='psg'.
    """
    return await _do_draft(req, response, pack_hint="psg")

def _strip_label(sid: str, name: str) -> str:
    # safe strip without relying on removeprefix/removesuffix
    pref = f"{sid}_"
    if name.startswith(pref):
        name = name[len(pref):]
    if name.endswith(".txt"):
        name = name[:-4]
    return name

@app.get("/v1/debug/evidence/{sid}")
def debug_list_evidence(sid: str, preview: int = Query(0, ge=0, le=4000)):
    try:
        # 1) list blobs
        blobs = storage.list_blobs("evidence", prefix=f"{sid}_", suffix=".txt")

        # 2) optionally read previews
        items = []
        for name in blobs:
            label = _strip_label(sid, name)
            txt = storage.get_text("evidence", name) if preview else ""
            items.append({
                "name": name,
                "label": label,
                "chars": (len(txt) if txt else None),
                "preview": (txt[:preview] if txt else "")
            })

        return {"session_id": sid, "items": items}

    except Exception as e:
        # Return a clear 500 body so you can see the exact cause in the browser
        raise HTTPException(status_code=500, detail=f"debug_list_evidence failed: {type(e).__name__}: {e}")


# dev-only
@app.get("/v1/debug/packs")
def debug_packs(pack: str = Query("psg"), ver: str = Query("latest-approved")):
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
    query_key = os.environ["AZURE_SEARCH_QUERY_KEY"]
    index_name = os.environ.get("AZURE_SEARCH_INDEX", "smartai-prompts")

    client = SearchClient(endpoint, index_name, AzureKeyCredential(query_key))

    # Resolve latest-approved → concrete version using the same helper as the vault
    # Also canonicalize pack IDs to uppercase for explicit versions
    if ver == "latest-approved":
        resolved_pack, resolved_ver = _pv_resolve(pack)
    else:
        resolved_pack = pack.strip().upper()
        resolved_ver = ver.strip()

    flt = f"pack_id eq '{resolved_pack}' and status eq 'approved'"
    if resolved_ver != "latest-approved":
        flt += f" and version eq '{resolved_ver}'"

    # IMPORTANT: only select retrievable fields; metadata_json contains section_id/version/template_key
    rs = client.search(
        search_text="*",
        filter=flt,
        top=200,
        select=["metadata_json"],   # <- keep it to this one
    )

    items, sections = [], set()
    for d in rs:
        meta_raw = d.get("metadata_json") or "{}"
        try:
            meta = json.loads(meta_raw)
        except Exception:
            meta = {}
        sid = meta.get("section_id")
        tkey = meta.get("template_key")
        ver  = meta.get("version")
        if sid:
            sections.add(sid)
        items.append({"section_id": sid, "template_key": tkey, "version": ver})

    return {
        "pack": resolved_pack,
        "version": resolved_ver,
        "sections": sorted(s for s in sections if s),
        "items": items
    }


@app.get("/v1/debug/whereami")
def whereami():
    import os
    return {
        "endpoint": os.environ.get("AZURE_SEARCH_ENDPOINT"),
        "index": os.environ.get("AZURE_SEARCH_INDEX", "smartai-prompts-v2"),
        # Don't print keys. Do a minimal query to prove visibility:
        "probe": "ok"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)