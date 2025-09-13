def score(text:str, *, require_tokens=None, max_words=400):
    ok = True; fails=[]
    if len(text.split()) > max_words: ok=False; fails.append("length_cap")
    if require_tokens:
        for tok in require_tokens:
            if tok.lower() not in text.lower():
                ok=False; fails.append(f"missing:{tok}")
    return {"score": 85 if ok else 55, "fails": fails}