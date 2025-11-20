# Run: python test_validate.py
# Note: Requires environment variables to be set (STORAGE_ACCOUNT_NAME, etc.)

import os
import sys

# Set minimal dummy env vars if not present (for import to work)
# These will be overridden by actual env vars if they exist
if "STORAGE_ACCOUNT_NAME" not in os.environ:
    print("Warning: Environment variables not set. Setting minimal values for import...")
    os.environ.setdefault("STORAGE_ACCOUNT_NAME", "dummy")
    os.environ.setdefault("STORAGE_CONTAINER_UPLOADS", "dummy")
    os.environ.setdefault("STORAGE_CONTAINER_EVIDENCE", "dummy")
    os.environ.setdefault("STORAGE_CONTAINER_OUTPUTS", "dummy")
    os.environ.setdefault("STORAGE_CONTAINER_TRACES", "dummy")
    os.environ.setdefault("STORAGE_TABLE_SESSIONS", "dummy")
    print("Note: Actual storage calls will fail. Ensure proper environment is configured.\n")

from app.main import app
from fastapi.testclient import TestClient

c = TestClient(app)

# 1. Create PSG session
r = c.post("/v1/session", json={"grant": "PSG"})
sid = r.json()["session_id"]

# 2. Inject facts (equity < 30)
c.post(f"/v1/session/{sid}/facts", json={"local_equity_pct": 25})

# 3. Call validate
v = c.post(f"/v1/session/{sid}/validate").json()
print("\nValidation Output:")
print(v)
assert len(v["checks"]) == 1, "Expected 1 warning"
assert v["checks"][0]["code"] == "PSG.ELIG.LOCAL_EQUITY_MIN_30"
print("\nOK ✓  Validation engine working as expected.\n")

