def pick_framework(section_id:str)->str:
    if section_id == "business_case": return "PAS"
    if section_id == "consultancy_scope": return "SCQA"
    return "SCQA"