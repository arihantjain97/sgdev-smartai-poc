from .prompt_vault import retrieve_template
from .appcfg import get as cfg_get


def compose_instruction(section_id: str, framework: str, inputs: dict, evidence_snippet: str = "") -> list:
    style = inputs.get("style", "Formal, consultant voice")
    length = inputs.get("length_limit", 350)
    grant = (inputs.get("grant") or inputs.get("grant_id") or "edg").lower()
    tags = [section_id, framework.lower(), grant] + inputs.get("tags", [])
    
    # Get template entry with metadata
    tpl_obj = retrieve_template(section_id, tags=tags)
    tpl = tpl_obj["template"]
    metadata = tpl_obj.get("metadata", {})
    
    # 1) Build evidence labels based on hints and user preferences
    hints = metadata.get("evidence_hints", {})
    prios = hints.get("priority_labels", [])
    opts = hints.get("optional_labels", [])
    
    # Extract available evidence labels from the evidence_snippet
    available = []
    if evidence_snippet:
        # Simple extraction of evidence labels from snippet headers
        import re
        available = re.findall(r'--- \[evidence:([^\]]+)\] ---', evidence_snippet)
    
    # Build chosen evidence order: prios first, then opts, then explicit user choices
    chosen = []
    chosen += [l for l in prios if l in available]
    chosen += [l for l in opts if (l in available and l not in chosen)]
    
    # If caller passed inputs.evidence_labels, respect that but keep prios first
    explicit = inputs.get("evidence_labels", [])
    for l in explicit:
        if l not in chosen and l in available:
            chosen.append(l)
    
    # 2) Build labels map for optional template blocks
    labels = {}
    # Common shortcuts (map to your canonical labels if present)
    if "acra_bizfile" in available: labels["registry"] = "acra_bizfile"
    if "audited_financials" in available: labels["financials"] = "audited_financials"
    if "vendor_quotation" in available: labels["vendor_quote"] = "vendor_quotation"
    if "cost_breakdown" in available: labels["costs"] = "cost_breakdown"
    if "market_analysis" in available: labels["market_analysis"] = "market_analysis"
    if "consultant_proposal" in available: labels["consultant_proposal"] = "consultant_proposal"
    
    # Build evidence window (use existing snippet for now)
    evidence_window = evidence_snippet[: int(inputs.get("evidence_char_cap") or cfg_get("EVIDENCE_CHAR_CAP", "6000"))]
    
    # Render template with all variables
    prompt_text = tpl.replace("{{framework}}", framework).replace("{{style}}", style).replace("{{length_limit}}", str(length)).replace("{{evidence_window}}", evidence_window)
    
    # Replace optional label blocks if they exist
    for key, value in labels.items():
        prompt_text = prompt_text.replace(f"{{{{labels.{key}}}}}", value)
    
    # You already build system+user; add a response header later with pack@ver
    return [
        {"role": "system", "content": "You are a grant consultant. Use only provided evidence; cite with [source:<label>]."},
        {"role": "user", "content": prompt_text}
    ], f"{tpl_obj['pack_id']}@{tpl_obj['version']}"