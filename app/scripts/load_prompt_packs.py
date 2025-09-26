import os, json, sys, pathlib, hashlib, yaml, re
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
SEARCH_KEY      = os.environ["AZURE_SEARCH_ADMIN_KEY"]
INDEX_NAME      = os.environ.get("AZURE_SEARCH_INDEX","smartai-prompts")

root = pathlib.Path(__file__).resolve().parents[1]  # repo root

def read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


_ALLOWED = re.compile(r"[^A-Za-z0-9_\-=]")  # Azure Search key charset

def _safe(s: str) -> str:
    # map anything not allowed to "_"
    return _ALLOWED.sub("_", s)

def doc_id(pack_id: str, version: str, section_id: str, tmpl_key: str) -> str:
    """
    Stable, collision-proof document id:
      - unique on (pack_id, version, section_id, tmpl_key)
      - independent of filename so you can reuse/rename files without creating new docs
    """
    version_s  = version.replace(".", "_")          # e.g. "1.0.1" -> "1_0_1"
    pack_s     = _safe(pack_id)
    section_s  = _safe(section_id)
    tmpl_s     = _safe(tmpl_key)

    # Basis excludes filename on purpose; tmpl_key is the disambiguator for variants
    basis = f"{pack_id}|{version}|{section_id}|{tmpl_key}"
    h = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]

    return f"{pack_s}-{version_s}-{section_s}-{tmpl_s}-{h}"


def pack_to_docs(pack_dir: pathlib.Path):
    yml = yaml.safe_load(read_text(pack_dir / "pack.yml"))
    pack_id = yml["pack_id"]
    version = yml["version"]
    status  = yml.get("status","draft")
    labels  = yml.get("labels",{})
    templates = yml.get("templates",{})

    for tmpl_key, t in templates.items():
        file_rel = t["file"]
        text     = read_text(pack_dir / file_rel)
        tags     = t.get("retrieval_tags", [])
        rubric   = t.get("rubric", {})

        # Allow explicit override; otherwise use the YAML key as section_id
        section_id = t.get("section_id", tmpl_key)

        meta = {
            "pack_id": pack_id,
            "version": version,
            "labels": labels,
            "section_id": section_id,
            "rubric": rubric,
            "template_key": tmpl_key,   # helpful for debugging
            "file": file_rel,           # optional: keep for traceability
        }

        yield {
            "id": doc_id(pack_id, version, section_id, tmpl_key),  # 👈 uses tmpl_key
            "pack_id": pack_id,
            "version": version,
            "status": status,
            "section_id": section_id,
            "retrieval_tags": tags,
            "template_text": text,
            "metadata_json": json.dumps(meta, ensure_ascii=False),
        }

def main():
    client = SearchClient(SEARCH_ENDPOINT, INDEX_NAME, AzureKeyCredential(SEARCH_KEY))
    docs = []
    for pack_dir in (root / "vault").glob("*.*"):
        if not (pack_dir / "pack.yml").exists():
            continue
        docs.extend(list(pack_to_docs(pack_dir)))

    # Only upload approved on Day-2 (dev)
    approved = [d for d in docs if d["status"] == "approved"]
    if not approved:
        print("No approved templates found. Set status: approved in pack.yml", file=sys.stderr)
        sys.exit(1)

    # Upsert
    r = client.upload_documents(approved)
    failed = [x for x in r if not x.succeeded]
    if failed:
        print("Some docs failed:", failed, file=sys.stderr)
        sys.exit(2)

    print(f"Uploaded {len(approved)} docs to {INDEX_NAME}")

if __name__ == "__main__":
    main()