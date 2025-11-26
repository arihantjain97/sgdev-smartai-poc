#!/usr/bin/env python3
"""
Test script for /v1/session/{sid}/checklisttest endpoint.

Tests the dynamic checklist generation from pack.yml and template index.
"""

import requests
import json
import sys

API = "https://sgdev-smartai-api-01.azurewebsites.net"

def pp(x):
    print(json.dumps(x, indent=2))

def create_session(pack):
    # grant == pack (backend uses grant field to mean pack)
    resp = requests.post(f"{API}/v1/session", json={"grant": pack})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]

def test_edg_checklist():
    print("TEST: EDG checklisttest")
    sid = create_session("EDG")
    r = requests.get(f"{API}/v1/session/{sid}/checklisttest")
    assert r.status_code == 200, r.text
    data = r.json()
    pp(data)
    
    assert data["pack"] == "EDG"
    tasks = data["tasks"]
    
    # uploads first (from pack.yml)
    u0, u1 = tasks[0], tasks[1]
    assert u0["type"] == "upload"
    assert u1["type"] == "upload"
    assert u0["id"] in ["acra_bizfile"]
    assert u1["id"] in ["audited_financials"]
    
    # drafts exist
    draft_tasks = [t for t in tasks if t["type"] == "draft"]
    assert len(draft_tasks) > 0
    
    # variant sanity
    for t in draft_tasks:
        v = t.get("section_variant")
        if v:
            assert "__" not in v
    
    print("EDG checklisttest: PASS\n")

def test_psg_checklist():
    print("TEST: PSG checklisttest")
    sid = create_session("PSG")
    r = requests.get(f"{API}/v1/session/{sid}/checklisttest")
    assert r.status_code == 200, r.text
    data = r.json()
    pp(data)
    
    assert data["pack"] == "PSG"
    tasks = data["tasks"]
    
    # uploads first
    uids = [t["id"] for t in tasks if t["type"] == "upload"]
    assert "vendor_quotation" in uids
    assert "cost_breakdown" in uids
    
    print("PSG checklisttest: PASS\n")

def test_missing_session():
    print("TEST: Missing session 404")
    r = requests.get(f"{API}/v1/session/doesnotexist/checklisttest")
    assert r.status_code == 404
    print("Missing session: PASS\n")

def test_variant_format():
    print("TEST: variant format")
    sid = create_session("EDG")
    r = requests.get(f"{API}/v1/session/{sid}/checklisttest")
    assert r.status_code == 200
    data = r.json()
    
    for t in data["tasks"]:
        v = t.get("section_variant")
        if v:
            assert "__" not in v, f"Invalid variant format: {v}"
    
    print("Variant format: PASS\n")

def main():
    try:
        test_edg_checklist()
        test_psg_checklist()
        test_missing_session()
        test_variant_format()
        print("ALL TESTS PASSED")
        sys.exit(0)
    except Exception as e:
        print("TEST FAILED:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()

