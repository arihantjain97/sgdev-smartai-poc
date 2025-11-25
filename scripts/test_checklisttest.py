#!/usr/bin/env python3
"""
Test script for /v1/session/{sid}/checklisttest endpoint.

Tests the dynamic checklist generation from pack.yml and template index.
"""

import requests
import json
import sys

BASE_URL = "https://sgdev-smartai-api-01.azurewebsites.net"

def test_edg_checklist():
    """Test Case 1: EDG full path"""
    print("\n=== Test Case 1: EDG Checklist ===")
    
    # Create EDG session
    r = requests.post(f"{BASE_URL}/v1/session", json={"grant": "EDG"})
    assert r.status_code == 200, f"Failed to create session: {r.status_code}"
    sid = r.json()["session_id"]
    print(f"Created EDG session: {sid}")
    
    # Call checklisttest
    r = requests.get(f"{BASE_URL}/v1/session/{sid}/checklisttest")
    assert r.status_code == 200, f"Failed to get checklist: {r.status_code}"
    data = r.json()
    
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Assertions
    assert "session_id" in data, "Missing session_id"
    assert "pack" in data, "Missing pack"
    assert data["pack"] == "EDG", f"Expected pack=EDG, got {data['pack']}"
    assert "tasks" in data, "Missing tasks"
    assert isinstance(data["tasks"], list), "Tasks must be a list"
    assert len(data["tasks"]) > 0, "Tasks list is empty"
    
    # Check for upload tasks
    upload_tasks = [t for t in data["tasks"] if t.get("type") == "upload"]
    assert len(upload_tasks) >= 2, f"Expected at least 2 upload tasks, got {len(upload_tasks)}"
    assert any(t["id"] == "acra_bizfile" for t in upload_tasks), "Missing acra_bizfile upload"
    assert any(t["id"] == "audited_financials" for t in upload_tasks), "Missing audited_financials upload"
    
    # Check for draft tasks
    draft_tasks = [t for t in data["tasks"] if t.get("type") == "draft"]
    assert len(draft_tasks) > 0, "Expected at least one draft task"
    
    # Check order: uploads first
    assert data["tasks"][0]["type"] == "upload", "First task should be upload"
    
    print("✓ EDG checklist test passed")
    return True

def test_psg_checklist():
    """Test Case 2: PSG path"""
    print("\n=== Test Case 2: PSG Checklist ===")
    
    # Create PSG session
    r = requests.post(f"{BASE_URL}/v1/session", json={"grant": "PSG"})
    assert r.status_code == 200, f"Failed to create session: {r.status_code}"
    sid = r.json()["session_id"]
    print(f"Created PSG session: {sid}")
    
    # Call checklisttest
    r = requests.get(f"{BASE_URL}/v1/session/{sid}/checklisttest")
    assert r.status_code == 200, f"Failed to get checklist: {r.status_code}"
    data = r.json()
    
    print(f"Response: {json.dumps(data, indent=2)}")
    
    # Assertions
    assert data["pack"] == "PSG", f"Expected pack=PSG, got {data['pack']}"
    assert "tasks" in data, "Missing tasks"
    
    # Check for PSG-specific uploads
    upload_tasks = [t for t in data["tasks"] if t.get("type") == "upload"]
    assert any(t["id"] == "vendor_quotation" for t in upload_tasks), "Missing vendor_quotation upload"
    assert any(t["id"] == "cost_breakdown" for t in upload_tasks), "Missing cost_breakdown upload"
    
    # Check for draft tasks
    draft_tasks = [t for t in data["tasks"] if t.get("type") == "draft"]
    assert len(draft_tasks) > 0, "Expected at least one draft task"
    
    print("✓ PSG checklist test passed")
    return True

def test_missing_session():
    """Test Case 3: Missing session"""
    print("\n=== Test Case 3: Missing Session ===")
    
    r = requests.get(f"{BASE_URL}/v1/session/s_nonexistent123/checklisttest")
    assert r.status_code == 404, f"Expected 404 for missing session, got {r.status_code}"
    
    print("✓ Missing session test passed")
    return True

def test_variant_format():
    """Test Case 4: Check variant format uses dots, not underscores"""
    print("\n=== Test Case 4: Variant Format ===")
    
    # Create EDG session
    r = requests.post(f"{BASE_URL}/v1/session", json={"grant": "EDG"})
    sid = r.json()["session_id"]
    
    r = requests.get(f"{BASE_URL}/v1/session/{sid}/checklisttest")
    data = r.json()
    
    # Check that variants use . format, not __
    draft_tasks = [t for t in data["tasks"] if t.get("type") == "draft"]
    for task in draft_tasks:
        variant = task.get("section_variant")
        if variant:
            assert "__" not in variant, f"Variant should use dots, not underscores: {variant}"
            assert "." in variant or variant is None, f"Variant format issue: {variant}"
    
    print("✓ Variant format test passed")
    return True

def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing /v1/session/{sid}/checklisttest endpoint")
    print("=" * 70)
    
    tests = [
        test_edg_checklist,
        test_psg_checklist,
        test_missing_session,
        test_variant_format,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test error: {e}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Summary: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

