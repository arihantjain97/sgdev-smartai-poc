import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient

ACCOUNT = os.environ["STORAGE_ACCOUNT_NAME"]
CONTAINER_UPLOADS  = os.environ["STORAGE_CONTAINER_UPLOADS"]
CONTAINER_EVIDENCE = os.environ["STORAGE_CONTAINER_EVIDENCE"]
CONTAINER_OUTPUTS  = os.environ["STORAGE_CONTAINER_OUTPUTS"]
CONTAINER_TRACES   = os.environ["STORAGE_CONTAINER_TRACES"]
TABLE_SESSIONS     = os.environ["STORAGE_TABLE_SESSIONS"]

_cred = DefaultAzureCredential()
_blob = BlobServiceClient(f"https://{ACCOUNT}.blob.core.windows.net", credential=_cred)    
_table = TableServiceClient(endpoint=f"https://{ACCOUNT}.table.core.windows.net", credential=_cred)

def list_blobs(container: str, prefix: str = "", suffix: str = "") -> list[str]:
    cc = _blob.get_container_client(container)
    names = []
    for b in cc.list_blobs(name_starts_with=prefix):
        n = b.name
        if not suffix or n.endswith(suffix):
            names.append(n)
    return names

def put_text(container:str, name:str, text:str):
    _blob.get_container_client(container).upload_blob(name, text, overwrite=True)
    return f"https://{ACCOUNT}.blob.core.windows.net/{container}/{name}"

def get_text(container:str, name:str)->str:
    b = _blob.get_container_client(container).download_blob(name)
    return b.content_as_text()

def sessions():
    return _table.get_table_client(table_name=TABLE_SESSIONS)