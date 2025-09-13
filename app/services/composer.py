def compose_instruction(section_id:str, framework:str, inputs:dict, evidence_snippet:str="")->list:
    # framework slots (toy)
    slots = {
      "PAS": ["Problem","Agitate","Solve"],
      "SCQA":["Situation","Complication","Question","Answer"]
    }[framework]
    style = inputs.get("style","Formal, consultant voice")
    length = inputs.get("length_limit", 350)
    evidence_clause = f"Use only facts from: {inputs.get('evidence_label','[no-evidence]')}.\n{evidence_snippet}\n" if evidence_snippet else ""
    system = (
      f"You are a grant consultant. Draft section '{section_id}' using {framework} "
      f"with slots {slots}. Tone: {style}. Max words: {length}. "
      "Add [source:<label>] after any number you cite. "
      + evidence_clause
    )
    user = inputs.get("prompt","Write the draft.")
    return [{"role":"system","content":system},{"role":"user","content":user}]