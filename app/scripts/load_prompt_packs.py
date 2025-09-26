import os, json, sys, pathlib, hashlib, yaml
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"].rstrip("/")
SEARCH_KEY      = os.environ["AZURE_SEARCH_ADMIN_KEY"]
INDEX_NAME      = os.environ.get("AZURE_SEARCH_INDEX","smartai-prompts")

root = pathlib.Path(__file__).resolve().parents[1]  # repo root

def read_text(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")

"""
def doc_id(pack_id, version, section_id, fname) -> str:
    # stable id so upserts overwrite
    basis = f"{pack_id}|{version}|{section_id}|{fname}"
    h = hashlib.sha1(basis.encode()).hexdigest()[:12]
    return f"{pack_id}-{version}-{section_id}-{h}"
"""

def doc_id(pack_id, version, section_id, fname) -> str:
    version_s = version.replace(".", "_")   # "1.0.0" → "1_0_0"
    basis = f"{pack_id}|{version}|{section_id}|{fname}"
    h = hashlib.sha1(basis.encode()).hexdigest()[:12]
    return f"{pack_id}-{version_s}-{section_id}-{h}"


def pack_to_docs(pack_dir: pathlib.Path):
    yml = yaml.safe_load(read_text(pack_dir / "pack.yml"))
    pack_id = yml["pack_id"]
    version = yml["version"]
    status  = yml.get("status","draft")
    labels  = yml.get("labels",{})
    templates = yml.get("templates",{})

    for section_id, t in templates.items():
        file_rel = t["file"]
        text = read_text(pack_dir / file_rel)
        tags = t.get("retrieval_tags",[])
        rubric = t.get("rubric",{})

        meta = {
            "pack_id": pack_id,
            "version": version,
            "labels": labels,
            "section_id": section_id,
            "rubric": rubric
        }

        yield {
            "id": doc_id(pack_id, version, section_id, file_rel),
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