#!/usr/bin/env python3
"""
Comprehensive black-box API test suite for SmartAI API.

This script tests all endpoints from a frontend/client perspective,
including edge cases and error handling.

Usage:
    python test_api_suite.py [--base-url BASE_URL] [--verbose]

Environment:
    BASE_URL: API base URL (default: https://sgdev-smartai-api-01.azurewebsites.net)
"""

import requests
import json
import sys
import argparse
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TestResult:
    """Test result container"""
    name: str
    passed: bool
    message: str
    response: Optional[Dict[str, Any]] = None
    status_code: Optional[int] = None


class APITester:
    """Black-box API tester"""
    
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url.rstrip('/')
        self.verbose = verbose
        self.session_ids = {
            'edg': None,
            'psg': None,
        }
        self.results: list[TestResult] = []
    
    def log(self, message: str):
        """Print log message if verbose"""
        if self.verbose:
            print(f"  [LOG] {message}")
    
    def test(self, name: str, func, *args, **kwargs) -> TestResult:
        """Run a test and record result"""
        try:
            result = func(*args, **kwargs)
            if isinstance(result, TestResult):
                self.results.append(result)
                status = "✓" if result.passed else "✗"
                print(f"{status} {name}: {result.message}")
                if self.verbose and result.response:
                    print(f"    Response: {json.dumps(result.response, indent=2)}")
                return result
            else:
                # Assume success if function returns non-None
                result_obj = TestResult(name, True, "Passed", result)
                self.results.append(result_obj)
                print(f"✓ {name}: Passed")
                return result_obj
        except Exception as e:
            result_obj = TestResult(name, False, f"Exception: {str(e)}")
            self.results.append(result_obj)
            print(f"✗ {name}: Exception - {str(e)}")
            return result_obj
    
    # ============================================================
    # Health & Root Endpoints
    # ============================================================
    
    def test_root(self) -> TestResult:
        """Test GET /"""
        r = requests.get(f"{self.base_url}/")
        passed = r.status_code == 200 and r.json().get("ok") is True
        return TestResult("GET /", passed, 
                        f"Status {r.status_code}" if passed else f"Failed: {r.status_code}",
                        r.json(), r.status_code)
    
    def test_health(self) -> TestResult:
        """Test GET /health"""
        r = requests.get(f"{self.base_url}/health")
        passed = r.status_code == 200 and r.json().get("ok") is True
        return TestResult("GET /health", passed,
                        f"Status {r.status_code}" if passed else f"Failed: {r.status_code}",
                        r.json(), r.status_code)
    
    # ============================================================
    # Configuration Endpoints
    # ============================================================
    
    def test_config_features(self) -> TestResult:
        """Test GET /v1/config/features"""
        r = requests.get(f"{self.base_url}/v1/config/features")
        data = r.json()
        passed = (r.status_code == 200 and 
                 "feature_psg_enabled" in data and
                 "model_worker" in data and
                 "packs_latest" in data)
        return TestResult("GET /v1/config/features", passed,
                        "Valid config" if passed else f"Invalid response: {r.status_code}",
                        data, r.status_code)
    
    def test_prompts_active(self) -> TestResult:
        """Test GET /v1/prompts/active"""
        r = requests.get(f"{self.base_url}/v1/prompts/active")
        data = r.json()
        passed = (r.status_code == 200 and
                 "packs_latest" in data and
                 "model_worker" in data)
        return TestResult("GET /v1/prompts/active", passed,
                        "Valid prompts config" if passed else f"Invalid response: {r.status_code}",
                        data, r.status_code)
    
    # ============================================================
    # Session Management
    # ============================================================
    
    def test_create_session_edg(self) -> TestResult:
        """Test POST /v1/session (EDG)"""
        r = requests.post(f"{self.base_url}/v1/session", json={"grant": "EDG"})
        data = r.json()
        passed = r.status_code == 200 and "session_id" in data
        if passed:
            self.session_ids['edg'] = data["session_id"]
            self.log(f"Created EDG session: {self.session_ids['edg']}")
        return TestResult("POST /v1/session (EDG)", passed,
                        f"Session: {data.get('session_id')}" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_create_session_psg(self) -> TestResult:
        """Test POST /v1/session (PSG)"""
        r = requests.post(f"{self.base_url}/v1/session", json={"grant": "PSG"})
        data = r.json()
        passed = r.status_code == 200 and "session_id" in data
        if passed:
            self.session_ids['psg'] = data["session_id"]
            self.log(f"Created PSG session: {self.session_ids['psg']}")
        return TestResult("POST /v1/session (PSG)", passed,
                        f"Session: {data.get('session_id')}" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_create_session_with_company(self) -> TestResult:
        """Test POST /v1/session with company_name"""
        r = requests.post(f"{self.base_url}/v1/session", 
                         json={"grant": "EDG", "company_name": "Test Company Pte Ltd"})
        data = r.json()
        passed = r.status_code == 200 and "session_id" in data
        return TestResult("POST /v1/session (with company)", passed,
                        f"Session: {data.get('session_id')}" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_create_session_invalid_grant(self) -> TestResult:
        """Test POST /v1/session with invalid grant (edge case)"""
        r = requests.post(f"{self.base_url}/v1/session", json={"grant": "INVALID"})
        # Should still create session (grant is just a string field)
        passed = r.status_code == 200
        return TestResult("POST /v1/session (invalid grant)", passed,
                        "Created (grant is permissive)" if passed else f"Failed: {r.status_code}",
                        r.json() if r.status_code == 200 else None, r.status_code)
    
    def test_get_session(self) -> TestResult:
        """Test GET /v1/session/{sid}"""
        if not self.session_ids['edg']:
            return TestResult("GET /v1/session/{sid}", False, "No EDG session created")
        
        r = requests.get(f"{self.base_url}/v1/session/{self.session_ids['edg']}")
        data = r.json()
        passed = (r.status_code == 200 and 
                 "session_id" in data and 
                 "session" in data)
        return TestResult("GET /v1/session/{sid}", passed,
                        "Retrieved session" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_get_session_not_found(self) -> TestResult:
        """Test GET /v1/session/{sid} with non-existent session (edge case)"""
        r = requests.get(f"{self.base_url}/v1/session/s_nonexistent123")
        passed = r.status_code == 404
        return TestResult("GET /v1/session/{sid} (not found)", passed,
                        "404 as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code != 404 else None, r.status_code)
    
    # ============================================================
    # Facts & Eligibility
    # ============================================================
    
    def test_post_facts_basic(self) -> TestResult:
        """Test POST /v1/session/{sid}/facts (basic)"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/session/{sid}/facts", False, "No EDG session created")
        
        payload = {
            "local_equity_pct": 45.5,
            "turnover": 1200000,
            "headcount": 18
        }
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['edg']}/facts", json=payload)
        data = r.json()
        passed = (r.status_code == 200 and 
                 "session_id" in data and 
                 "facts" in data)
        return TestResult("POST /v1/session/{sid}/facts (basic)", passed,
                        "Facts posted" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_post_facts_psg_eligibility(self) -> TestResult:
        """Test POST /v1/session/{sid}/facts (PSG eligibility)"""
        if not self.session_ids['psg']:
            return TestResult("POST /v1/session/{sid}/facts (PSG)", False, "No PSG session created")
        
        payload = {
            "local_equity_pct": 60.0,
            "used_in_singapore": True,
            "no_payment_before_application": True
        }
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['psg']}/facts", json=payload)
        data = r.json()
        passed = r.status_code == 200 and "facts" in data
        return TestResult("POST /v1/session/{sid}/facts (PSG)", passed,
                        "PSG facts posted" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_post_facts_with_extra(self) -> TestResult:
        """Test POST /v1/session/{sid}/facts with extra dict"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/session/{sid}/facts (extra)", False, "No EDG session created")
        
        payload = {
            "local_equity_pct": 50,
            "extra": {
                "industry": "F&B",
                "budget_range": "<50k",
                "custom_field": "test_value"
            }
        }
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['edg']}/facts", json=payload)
        data = r.json()
        passed = r.status_code == 200 and "facts" in data
        return TestResult("POST /v1/session/{sid}/facts (with extra)", passed,
                        "Facts with extra posted" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_post_facts_eligibility_alias(self) -> TestResult:
        """Test POST /v1/session/{sid}/eligibility (backward-compatible alias)"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/session/{sid}/eligibility", False, "No EDG session created")
        
        payload = {"local_equity_pct": 55}
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['edg']}/eligibility", json=payload)
        data = r.json()
        passed = r.status_code == 200 and "facts" in data
        return TestResult("POST /v1/session/{sid}/eligibility (alias)", passed,
                        "Eligibility alias works" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_post_facts_invalid_session(self) -> TestResult:
        """Test POST /v1/session/{sid}/facts with invalid session (edge case)"""
        r = requests.post(f"{self.base_url}/v1/session/s_invalid123/facts", 
                         json={"local_equity_pct": 50})
        passed = r.status_code == 404
        return TestResult("POST /v1/session/{sid}/facts (invalid session)", passed,
                        "404 as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code != 404 else None, r.status_code)
    
    def test_post_facts_invalid_values(self) -> TestResult:
        """Test POST /v1/session/{sid}/facts with invalid values (edge case)"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/session/{sid}/facts (invalid values)", False, "No EDG session created")
        
        # Test negative equity (should be rejected by Pydantic)
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['edg']}/facts",
                         json={"local_equity_pct": -10})
        passed = r.status_code == 422  # Validation error
        return TestResult("POST /v1/session/{sid}/facts (invalid values)", passed,
                        "422 validation error as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code == 422 else None, r.status_code)
    
    def test_post_facts_out_of_range(self) -> TestResult:
        """Test POST /v1/session/{sid}/facts with out-of-range values (edge case)"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/session/{sid}/facts (out of range)", False, "No EDG session created")
        
        # Test equity > 100% (should be rejected by Pydantic)
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['edg']}/facts",
                         json={"local_equity_pct": 150})
        passed = r.status_code == 422  # Validation error
        return TestResult("POST /v1/session/{sid}/facts (out of range)", passed,
                        "422 validation error as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code == 422 else None, r.status_code)
    
    # ============================================================
    # Validation
    # ============================================================
    
    def test_validate_psg_warning(self) -> TestResult:
        """Test POST /v1/session/{sid}/validate (PSG with warning)"""
        if not self.session_ids['psg']:
            return TestResult("POST /v1/session/{sid}/validate (PSG warning)", False, "No PSG session created")
        
        # Set equity below 30% to trigger warning
        requests.post(f"{self.base_url}/v1/session/{self.session_ids['psg']}/facts",
                     json={"local_equity_pct": 25})
        
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['psg']}/validate")
        data = r.json()
        passed = (r.status_code == 200 and
                 "session_id" in data and
                 "checks" in data and
                 len(data["checks"]) == 1 and
                 data["checks"][0]["code"] == "PSG.ELIG.LOCAL_EQUITY_MIN_30")
        return TestResult("POST /v1/session/{sid}/validate (PSG warning)", passed,
                        f"Warning found: {data['checks'][0]['code']}" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_validate_psg_no_warning(self) -> TestResult:
        """Test POST /v1/session/{sid}/validate (PSG with no warning)"""
        if not self.session_ids['psg']:
            return TestResult("POST /v1/session/{sid}/validate (PSG no warning)", False, "No PSG session created")
        
        # Set equity above 30% - no warning expected
        requests.post(f"{self.base_url}/v1/session/{self.session_ids['psg']}/facts",
                     json={"local_equity_pct": 50})
        
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['psg']}/validate")
        data = r.json()
        passed = (r.status_code == 200 and
                 "session_id" in data and
                 "checks" in data and
                 len(data["checks"]) == 0)
        return TestResult("POST /v1/session/{sid}/validate (PSG no warning)", passed,
                        "No warnings (equity >= 30%)" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_validate_edg_no_checks(self) -> TestResult:
        """Test POST /v1/session/{sid}/validate (EDG - no rules yet)"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/session/{sid}/validate (EDG)", False, "No EDG session created")
        
        r = requests.post(f"{self.base_url}/v1/session/{self.session_ids['edg']}/validate")
        data = r.json()
        passed = (r.status_code == 200 and
                 "session_id" in data and
                 "checks" in data)
        return TestResult("POST /v1/session/{sid}/validate (EDG)", passed,
                        "Validation endpoint works" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_validate_invalid_session(self) -> TestResult:
        """Test POST /v1/session/{sid}/validate with invalid session (edge case)"""
        r = requests.post(f"{self.base_url}/v1/session/s_invalid123/validate")
        passed = r.status_code == 404
        return TestResult("POST /v1/session/{sid}/validate (invalid session)", passed,
                        "404 as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code != 404 else None, r.status_code)
    
    # ============================================================
    # Checklist
    # ============================================================
    
    def test_checklist_edg(self) -> TestResult:
        """Test GET /v1/session/{sid}/checklist (EDG)"""
        if not self.session_ids['edg']:
            return TestResult("GET /v1/session/{sid}/checklist (EDG)", False, "No EDG session created")
        
        r = requests.get(f"{self.base_url}/v1/session/{self.session_ids['edg']}/checklist")
        data = r.json()
        passed = (r.status_code == 200 and
                 "session_id" in data and
                 "grant" in data and
                 "tasks" in data and
                 data["grant"] == "EDG")
        return TestResult("GET /v1/session/{sid}/checklist (EDG)", passed,
                        f"EDG checklist with {len(data.get('tasks', []))} tasks" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_checklist_psg(self) -> TestResult:
        """Test GET /v1/session/{sid}/checklist (PSG)"""
        if not self.session_ids['psg']:
            return TestResult("GET /v1/session/{sid}/checklist (PSG)", False, "No PSG session created")
        
        r = requests.get(f"{self.base_url}/v1/session/{self.session_ids['psg']}/checklist")
        data = r.json()
        passed = (r.status_code == 200 and
                 "session_id" in data and
                 "grant" in data and
                 "tasks" in data and
                 data["grant"] == "PSG")
        return TestResult("GET /v1/session/{sid}/checklist (PSG)", passed,
                        f"PSG checklist with {len(data.get('tasks', []))} tasks" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_checklist_invalid_session(self) -> TestResult:
        """Test GET /v1/session/{sid}/checklist with invalid session (edge case)"""
        r = requests.get(f"{self.base_url}/v1/session/s_invalid123/checklist")
        # Should return default EDG checklist even for invalid session
        passed = r.status_code == 200
        return TestResult("GET /v1/session/{sid}/checklist (invalid session)", passed,
                        "Returns default checklist" if passed else f"Failed: {r.status_code}",
                        r.json() if r.status_code == 200 else None, r.status_code)
    
    # ============================================================
    # Draft Endpoints
    # ============================================================
    
    def test_draft_unified(self) -> TestResult:
        """Test POST /v1/draft (unified endpoint)"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/draft", False, "No EDG session created")
        
        payload = {
            "session_id": self.session_ids['edg'],
            "section_id": "consultancy_scope",
            "inputs": {}
        }
        r = requests.post(f"{self.base_url}/v1/draft", json=payload)
        data = r.json()
        # Draft may fail if AI service is unavailable, but should return proper error
        passed = (r.status_code in [200, 400, 500] and
                 isinstance(data, dict))
        return TestResult("POST /v1/draft (unified)", passed,
                        f"Status {r.status_code}" if passed else f"Unexpected: {r.status_code}",
                        data, r.status_code)
    
    def test_draft_edg_specific(self) -> TestResult:
        """Test POST /v1/grants/edg/draft"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/grants/edg/draft", False, "No EDG session created")
        
        payload = {
            "session_id": self.session_ids['edg'],
            "section_id": "about_company",
            "inputs": {}
        }
        r = requests.post(f"{self.base_url}/v1/grants/edg/draft", json=payload)
        data = r.json()
        passed = (r.status_code in [200, 400, 500] and isinstance(data, dict))
        return TestResult("POST /v1/grants/edg/draft", passed,
                        f"Status {r.status_code}" if passed else f"Unexpected: {r.status_code}",
                        data, r.status_code)
    
    def test_draft_psg_specific(self) -> TestResult:
        """Test POST /v1/grants/psg/draft"""
        if not self.session_ids['psg']:
            return TestResult("POST /v1/grants/psg/draft", False, "No PSG session created")
        
        payload = {
            "session_id": self.session_ids['psg'],
            "section_id": "solution_description",
            "inputs": {}
        }
        r = requests.post(f"{self.base_url}/v1/grants/psg/draft", json=payload)
        data = r.json()
        passed = (r.status_code in [200, 400, 500] and isinstance(data, dict))
        return TestResult("POST /v1/grants/psg/draft", passed,
                        f"Status {r.status_code}" if passed else f"Unexpected: {r.status_code}",
                        data, r.status_code)
    
    def test_draft_with_variant(self) -> TestResult:
        """Test POST /v1/draft with section_variant"""
        if not self.session_ids['edg']:
            return TestResult("POST /v1/draft (with variant)", False, "No EDG session created")
        
        payload = {
            "session_id": self.session_ids['edg'],
            "section_id": "about_project",
            "section_variant": "about_project.i_and_p.automation",
            "inputs": {}
        }
        r = requests.post(f"{self.base_url}/v1/draft", json=payload)
        data = r.json()
        passed = (r.status_code in [200, 400, 500] and isinstance(data, dict))
        return TestResult("POST /v1/draft (with variant)", passed,
                        f"Status {r.status_code}" if passed else f"Unexpected: {r.status_code}",
                        data, r.status_code)
    
    def test_draft_invalid_session(self) -> TestResult:
        """Test POST /v1/draft with invalid session (edge case)"""
        payload = {
            "session_id": "s_invalid123",
            "section_id": "consultancy_scope",
            "inputs": {}
        }
        r = requests.post(f"{self.base_url}/v1/draft", json=payload)
        passed = r.status_code == 404
        return TestResult("POST /v1/draft (invalid session)", passed,
                        "404 as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code != 404 else None, r.status_code)
    
    def test_draft_missing_fields(self) -> TestResult:
        """Test POST /v1/draft with missing required fields (edge case)"""
        r = requests.post(f"{self.base_url}/v1/draft", json={})
        passed = r.status_code == 422  # Validation error
        return TestResult("POST /v1/draft (missing fields)", passed,
                        "422 validation error as expected" if passed else f"Unexpected: {r.status_code}",
                        r.json() if r.status_code == 422 else None, r.status_code)
    
    # ============================================================
    # Debug Endpoints
    # ============================================================
    
    def test_debug_evidence(self) -> TestResult:
        """Test GET /v1/debug/evidence/{sid}"""
        if not self.session_ids['edg']:
            return TestResult("GET /v1/debug/evidence/{sid}", False, "No EDG session created")
        
        r = requests.get(f"{self.base_url}/v1/debug/evidence/{self.session_ids['edg']}")
        data = r.json()
        passed = (r.status_code == 200 and
                 "session_id" in data and
                 "items" in data)
        return TestResult("GET /v1/debug/evidence/{sid}", passed,
                        f"Found {len(data.get('items', []))} evidence items" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_debug_evidence_with_preview(self) -> TestResult:
        """Test GET /v1/debug/evidence/{sid}?preview=100"""
        if not self.session_ids['edg']:
            return TestResult("GET /v1/debug/evidence/{sid} (preview)", False, "No EDG session created")
        
        r = requests.get(f"{self.base_url}/v1/debug/evidence/{self.session_ids['edg']}?preview=100")
        data = r.json()
        passed = r.status_code == 200 and "items" in data
        return TestResult("GET /v1/debug/evidence/{sid} (preview)", passed,
                        "Preview parameter works" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_debug_packs(self) -> TestResult:
        """Test GET /v1/debug/packs"""
        r = requests.get(f"{self.base_url}/v1/debug/packs")
        data = r.json()
        passed = (r.status_code == 200 and
                 "pack" in data and
                 "version" in data)
        return TestResult("GET /v1/debug/packs", passed,
                        f"Pack: {data.get('pack')}@{data.get('version')}" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_debug_packs_with_params(self) -> TestResult:
        """Test GET /v1/debug/packs?pack=edg&ver=1.0.0"""
        r = requests.get(f"{self.base_url}/v1/debug/packs?pack=edg&ver=1.0.0")
        data = r.json()
        passed = r.status_code == 200 and "pack" in data
        return TestResult("GET /v1/debug/packs (with params)", passed,
                        "Query params work" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    def test_debug_whereami(self) -> TestResult:
        """Test GET /v1/debug/whereami"""
        r = requests.get(f"{self.base_url}/v1/debug/whereami")
        data = r.json()
        passed = (r.status_code == 200 and
                 "endpoint" in data and
                 "index" in data and
                 "probe" in data)
        return TestResult("GET /v1/debug/whereami", passed,
                        "Debug info retrieved" if passed else f"Failed: {r.status_code}",
                        data, r.status_code)
    
    # ============================================================
    # Test Runner
    # ============================================================
    
    def run_all_tests(self):
        """Run all tests in logical order"""
        print("=" * 70)
        print("SmartAI API Test Suite")
        print("=" * 70)
        print(f"Base URL: {self.base_url}\n")
        
        # Health & Root
        print("\n[Health & Root Endpoints]")
        self.test("Root endpoint", self.test_root)
        self.test("Health endpoint", self.test_health)
        
        # Configuration
        print("\n[Configuration Endpoints]")
        self.test("Config features", self.test_config_features)
        self.test("Prompts active", self.test_prompts_active)
        
        # Session Management
        print("\n[Session Management]")
        self.test("Create EDG session", self.test_create_session_edg)
        self.test("Create PSG session", self.test_create_session_psg)
        self.test("Create session with company", self.test_create_session_with_company)
        self.test("Create session (invalid grant)", self.test_create_session_invalid_grant)
        self.test("Get session", self.test_get_session)
        self.test("Get session (not found)", self.test_get_session_not_found)
        
        # Facts & Eligibility
        print("\n[Facts & Eligibility]")
        self.test("Post facts (basic)", self.test_post_facts_basic)
        self.test("Post facts (PSG)", self.test_post_facts_psg_eligibility)
        self.test("Post facts (with extra)", self.test_post_facts_with_extra)
        self.test("Post facts (eligibility alias)", self.test_post_facts_eligibility_alias)
        self.test("Post facts (invalid session)", self.test_post_facts_invalid_session)
        self.test("Post facts (invalid values)", self.test_post_facts_invalid_values)
        self.test("Post facts (out of range)", self.test_post_facts_out_of_range)
        
        # Validation
        print("\n[Validation]")
        self.test("Validate (PSG warning)", self.test_validate_psg_warning)
        self.test("Validate (PSG no warning)", self.test_validate_psg_no_warning)
        self.test("Validate (EDG)", self.test_validate_edg_no_checks)
        self.test("Validate (invalid session)", self.test_validate_invalid_session)
        
        # Checklist
        print("\n[Checklist]")
        self.test("Checklist (EDG)", self.test_checklist_edg)
        self.test("Checklist (PSG)", self.test_checklist_psg)
        self.test("Checklist (invalid session)", self.test_checklist_invalid_session)
        
        # Drafts
        print("\n[Draft Endpoints]")
        self.test("Draft (unified)", self.test_draft_unified)
        self.test("Draft (EDG specific)", self.test_draft_edg_specific)
        self.test("Draft (PSG specific)", self.test_draft_psg_specific)
        self.test("Draft (with variant)", self.test_draft_with_variant)
        self.test("Draft (invalid session)", self.test_draft_invalid_session)
        self.test("Draft (missing fields)", self.test_draft_missing_fields)
        
        # Debug
        print("\n[Debug Endpoints]")
        self.test("Debug evidence", self.test_debug_evidence)
        self.test("Debug evidence (preview)", self.test_debug_evidence_with_preview)
        self.test("Debug packs", self.test_debug_packs)
        self.test("Debug packs (params)", self.test_debug_packs_with_params)
        self.test("Debug whereami", self.test_debug_whereami)
        
        # Summary
        print("\n" + "=" * 70)
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"Summary: {passed}/{total} tests passed ({100*passed//total if total > 0 else 0}%)")
        print("=" * 70)
        
        if passed < total:
            print("\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  ✗ {r.name}: {r.message}")
        
        return passed == total


def main():
    parser = argparse.ArgumentParser(description="SmartAI API Test Suite")
    parser.add_argument("--base-url", 
                       default="https://sgdev-smartai-api-01.azurewebsites.net",
                       help="API base URL")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    args = parser.parse_args()
    
    tester = APITester(args.base_url, args.verbose)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()




