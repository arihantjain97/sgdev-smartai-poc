# composer.py
from .prompt_vault import retrieve_template
from .appcfg import get as cfg_get

import re
from typing import Dict, List, Tuple, Any, Optional

# --- tiny mustache-ish helpers (no external deps) ----------------------------

_BLOCK_OPEN = re.compile(r"{{#\s*labels\.([a-zA-Z0-9_]+)\s*}}")
_BLOCK_CLOSE = re.compile(r"{{/\s*labels\.([a-zA-Z0-9_]+)\s*}}")

def _render_label_blocks(text: str, labels: Dict[str, str]) -> str:
    """
    Supports:
      {{#labels.key}} ... [source:{{labels.key}}] ... {{/labels.key}}
    If labels[key] exists, keep inner and replace {{labels.key}} with the value.
    Else, drop the whole block.
    """
    # Find blocks and resolve from inside out
    out = []
    stack = []
    i = 0
    while i < len(text):
        m_open = _BLOCK_OPEN.search(text, i)
        m_close = _BLOCK_CLOSE.search(text, i)

        if m_open and (not m_close or m_open.start() < m_close.start()):
            # Push current segment
            out.append(text[i:m_open.start()])
            stack.append((m_open.group(1), len(out)))  # key, insertion index
            out.append("")  # placeholder for block content
            i = m_open.end()
        elif m_close and stack:
            key = m_close.group(1)
            blk_key, idx = stack.pop()
            # current segment inside the block is out[idx]
            block_inner = "".join(out[idx:]) + text[i:m_close.start()]
            # truncate to idx (remove accumulated inner)
            out = out[:idx]
            if blk_key == key and key in labels:
                # substitute {{labels.key}} -> value
                block_inner = re.sub(r"{{\s*labels\."+re.escape(key)+r"\s*}}", labels[key], block_inner)
                out.append(block_inner)
            # else: drop the whole block (append nothing)
            i = m_close.end()
        else:
            # no more blocks
            out.append(text[i:])
            break

    rendered = "".join(out)
    # Replace any remaining simple {{labels.key}} occurrences
    for k, v in labels.items():
        rendered = re.sub(r"{{\s*labels\."+re.escape(k)+r"\s*}}", v, rendered)
    # Remove any unresolved label refs safely
    rendered = re.sub(r"{{\s*labels\.[a-zA-Z0-9_]+\s*}}", "", rendered)
    # Clean up any double spaces that might have been left behind
    rendered = re.sub(r"\s+", " ", rendered).strip()
    return rendered

# --- evidence label helpers ---------------------------------------------------

_LABEL_HEAD = re.compile(r'---\s*\[evidence:([^\]]+)\]\s*---')

def _extract_labels_from_snippet(snippet: str) -> List[str]:
    return _LABEL_HEAD.findall(snippet or "")

def _ordered_labels(
    available: List[str],
    hints: Dict[str, Any],
    explicit: List[str]
) -> List[str]:
    seen = set()
    order: List[str] = []

    # priority -> optional -> explicit (but keep de-dup and must exist)
    for src in (hints.get("priority_labels") or []):
        if src in available and src not in seen:
            seen.add(src); order.append(src)
    for src in (hints.get("optional_labels") or []):
        if src in available and src not in seen:
            seen.add(src); order.append(src)
    for src in (explicit or []):
        if src in available and src not in seen:
            seen.add(src); order.append(src)

    # append any remaining available labels
    for src in available:
        if src not in seen:
            seen.add(src); order.append(src)
    return order

def _labels_map_from_available(avail: List[str]) -> Dict[str, str]:
    m: Dict[str, str] = {}
    # common
    if "acra_bizfile" in avail:           m["registry"] = "acra_bizfile"
    if "audited_financials" in avail:     m["financials"] = "audited_financials"
    # PSG
    if "vendor_quotation" in avail:       m["vendor_quote"] = "vendor_quotation"
    if "cost_breakdown" in avail:         m["costs"] = "cost_breakdown"
    if "deployment_location_proof" in avail: m["deployment_proof"] = "deployment_location_proof"
    if "annex3_package" in avail:         m["annex3_package"] = "annex3_package"
    # market/evidence hints
    if "market_analysis" in avail:        m["market_analysis"] = "market_analysis"
    if "consultant_proposal" in avail:    m["consultant_proposal"] = "consultant_proposal"
    return m

# --- main entrypoint ----------------------------------------------------------

def compose_instruction(
    section_id: str,
    framework: str,
    inputs: dict,
    evidence_snippet: str = "",
    *,
    section_variant: Optional[str] = None,
    pack_hint: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], str, List[str]]:
    """
    Returns (messages, pack_header, evidence_order_used)
    - messages: for chat completion
    - pack_header: 'pack@version' string (for x-prompt-pack)
    - evidence_order_used: the labels we prioritized
    """

    style = inputs.get("style", "Formal, consultant voice")
    length = int(inputs.get("length_limit", 350))
    grant = (inputs.get("grant") or inputs.get("grant_id") or "edg").lower()
    user_prompt = (inputs.get("prompt") or "").strip()

    # tags help retrieval choose variant-specific prompts too
    tags = [section_id, framework.lower(), grant] + list(inputs.get("tags", []))
    if section_variant:
        # add variant tokens to help retrieval ranking
        tags += section_variant.replace(".", " ").replace("__", " ").split()

    # Retrieve template (+metadata) with awareness of variant & pack if provided
    tpl_obj = retrieve_template(
        section_id,
        tags=tags,
        section_variant=section_variant,   # <-- supports Day-7 delta
        pack_hint=pack_hint
    ) or {}

    tpl = tpl_obj.get("template") or ""
    metadata = tpl_obj.get("metadata", {})
    pack_header = f"{tpl_obj.get('pack_id','unknown')}@{tpl_obj.get('version','0.0.0')}"

    # Evidence selection
    hints = metadata.get("evidence_hints", {}) or {}
    available = _extract_labels_from_snippet(evidence_snippet)

    # if caller passed explicit labels but snippet is empty, still respect explicit
    if not available and inputs.get("evidence_labels"):
        # allow composer to order explicit labels by hints anyway
        available = list(dict.fromkeys(inputs["evidence_labels"]))  # preserve order, de-dup

    chosen_order = _ordered_labels(
        available=available,
        hints=hints,
        explicit=inputs.get("evidence_labels", [])
    )

    # Build labels map for optional blocks
    labels_map = _labels_map_from_available(chosen_order)

    # Evidence window
    cap_cfg = cfg_get("EVIDENCE_CHAR_CAP")
    cap = int(cap_cfg) if str(cap_cfg).isdigit() else 6000
    evidence_window = (evidence_snippet or "")[: cap]

    # Fill core vars first (leave labels blocks untouched here)
    # We use a lightweight replace for {{framework}}, {{style}}, {{length_limit}}, {{evidence_window}}
    def _kv_replace(s: str, kv: Dict[str, str]) -> str:
        for k, v in kv.items():
            s = s.replace("{{" + k + "}}", str(v))
        return s

    prompt_text = _kv_replace(tpl, {
        "framework": framework,
        "style": style,
        "length_limit": str(length),
        "evidence_window": evidence_window,
        "user_prompt": user_prompt
    })

    # Render optional label blocks + substitute {{labels.*}}
    prompt_text = _render_label_blocks(prompt_text, labels_map)

    # Prepend the operator's free-text prompt so the model MUST address it
    if user_prompt:
        prompt_text = (
            "Operator prompt (must be addressed explicitly): "
            + user_prompt
            + "\n\n"
            + prompt_text
        )

    # Final messages; keep system brief and generic to avoid over-constraining the template
    messages = [
        {
            "role": "system",
            "content": "You are a grant consultant. Use only the provided evidence; cite factual claims with [source:<label>]."
        },
        {
            "role": "user",
            "content": prompt_text
        }
    ]

    return messages, pack_header, chosen_order