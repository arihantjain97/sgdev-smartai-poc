def compose_instruction(section_id:str, framework:str, inputs:dict, evidence_snippet:str="")->list:
    # framework slots (toy)
    slots = {
      "PAS": ["Problem","Agitate","Solve"],
      "SCQA":["Situation","Complication","Question","Answer"]
    }[framework]
    style = inputs.get("style","Formal, consultant voice")
    length = inputs.get("length_limit", 350)

    # Prefer plural evidence_labels; fall back to single evidence_label; else [no-evidence]
    labels = inputs.get("evidence_labels") or inputs.get("evidence_label")
    if isinstance(labels, list):
        labels_str = ", ".join(labels) if labels else "[no-evidence]"
    else:
        labels_str = labels or "[no-evidence]"

    evidence_clause = ""
    if evidence_snippet:
        evidence_clause = (
            f"Use only facts from these evidence slices: {labels_str}.\n"
            f"{evidence_snippet}\n"
        )

    system = (
      f"You are a grant consultant. Draft section '{section_id}' using {framework} "
      f"with slots {slots}. Tone: {style}. Max words: {length}. "
      "Add [source:<label>] after any number you cite. "
      + evidence_clause
    )
    user = inputs.get("prompt","Write the draft.")
    return [{"role":"system","content":system},{"role":"user","content":user}]