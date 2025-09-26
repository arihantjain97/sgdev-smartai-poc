from .prompt_vault import retrieve_template
from .appcfg import get as cfg_get


def compose_instruction(section_id:str, framework:str, inputs:dict, evidence_snippet:str="")->list:
    style   = inputs.get("style","Formal, consultant voice")
    length  = inputs.get("length_limit", 350)
    grant   = (inputs.get("grant") or inputs.get("grant_id") or "edg").lower()
    tags    = [section_id, framework.lower(), grant] + inputs.get("tags",[])
    tpl_obj = retrieve_template(section_id, tags=tags)
    tpl     = tpl_obj["template"]

    evidence_window = evidence_snippet[: int(inputs.get("evidence_char_cap") or cfg_get("EVIDENCE_CHAR_CAP","6000"))]
    prompt_text = (tpl
        .replace("{{framework}}", framework)
        .replace("{{style}}", style)
        .replace("{{length_limit}}", str(length))
        .replace("{{evidence_window}}", evidence_window)
    )

    # You already build system+user; add a response header later with pack@ver
    return [
      {"role":"system","content":"You are a grant consultant. Use only provided evidence; cite with [source:<label>]."},
      {"role":"user","content": prompt_text}
    ], f"{tpl_obj['pack_id']}@{tpl_obj['version']}"