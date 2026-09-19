from typing import Dict, List, Any, Optional
import json
import random
import urllib.parse


class FallbackTestEngine:
    """
    Enhanced Rule-based test case generator.
    Generates 10-15 realistic, AI-like test cases for API security and functional testing
    across all HTTP methods (GET, POST, PUT, PATCH, DELETE).
    """

    # Security payloads
    SQL_INJECTION_PAYLOADS = [
        "' OR '1'='1",
        "1; DROP TABLE users--",
        "admin'--",
        "' OR 1=1--",
        "'); SELECT SLEEP(5); --"
    ]

    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "'\"><svg/onload=alert(1)>"
    ]

    OS_COMMAND_PAYLOADS = [
        "; ls -la",
        "| cat /etc/passwd",
        "& whoami",
        "$(whoami)"
    ]

    def __init__(self, api_config: Dict[str, Any]):
        self.api = api_config
        self.method = api_config['method'].upper()
        self.url = api_config['url']
        self.headers = api_config.get('headers', {})
        self.body = api_config.get('body')
        self.query_params = api_config.get('query_params') or {}

    def generate_test_cases(self) -> List[Dict[str, Any]]:
        """Generate 10-15 comprehensive test cases based on HTTP method and payload"""
        test_cases = []

        # 1. Positive Tests (2-3 cases)
        test_cases.extend(self._generate_positive_tests())

        # 2. Negative Tests (3-4 cases)
        test_cases.extend(self._generate_negative_tests())

        # 3. Boundary/Symmetric Tests (3-4 cases)
        test_cases.extend(self._generate_boundary_tests())

        # 4. Security Tests (4-5 cases)
        test_cases.extend(self._generate_security_tests())

        # Ensure we have at least 10 cases, if not, add more variations
        if len(test_cases) < 10:
            test_cases.append(self._generate_generic_error_case())

        return test_cases[:15]  # Cap at 15 as requested

    def _generate_positive_tests(self) -> List[Dict[str, Any]]:
        tests = []
        # Happy Path
        tests.append({
            "type": "positive",
            "name": f"Baseline {self.method} Request - Standard Success Path",
            "description": f"Verifies that the {self.method} endpoint correctly processes a standard, well-formed request with all required parameters.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": self._clean_query_params(self.query_params),
            "test_body": self.body,
            "expected_status": self._get_success_status()
        })

        # Variation (Query params or Body)
        if self.query_params or self.body:
            tests.append({
                "type": "positive",
                "name": f"Extended {self.method} Request - Parameter Variation",
                "description": "Validates the API's ability to handle different valid data types and structures within the expected schema.",
                "test_url": self.url,
                "test_method": self.method,
                "test_headers": self._clean_headers(self.headers),
                "query_params": self._vary_params(self.query_params),
                "test_body": self._create_alternative_valid_body() if self.body else None,
                "expected_status": self._get_success_status()
            })
        else:
            # If no params/body, add a cache-busting variation
            tests.append({
                "type": "positive",
                "name": f"Cache-Bypass {self.method} Request",
                "description": "Ensures the API returns fresh data by appending a unique timestamp to the request.",
                "test_url": self.url,
                "test_method": self.method,
                "test_headers": self._clean_headers(self.headers),
                "query_params": {"_t": str(random.randint(100000, 999999))},
                "test_body": None,
                "expected_status": self._get_success_status()
            })

        return tests

    def _generate_negative_tests(self) -> List[Dict[str, Any]]:
        tests = []
        # Missing Auth
        tests.append({
            "type": "negative",
            "name": "Authentication Bypass Attempt - Missing Credentials",
            "description": "Evaluates system security when mandatory authentication or identification headers are omitted.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": {k: v for k, v in self.headers.items() if
                             k.lower() not in ['authorization', 'cookie', 'x-api-key']},
            "query_params": self._clean_query_params(self.query_params),
            "test_body": self.body,
            "expected_status": 401
        })

        # Invalid Method
        invalid_method = "POST" if self.method == "GET" else "GET"
        tests.append({
            "type": "negative",
            "name": "Method Not Allowed - Verb Restriction Check",
            "description": f"Ensures the endpoint restricts access to only allowed HTTP verbs, rejecting {invalid_method} requests.",
            "test_url": self.url,
            "test_method": invalid_method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": self._clean_query_params(self.query_params),
            "test_body": None,
            "expected_status": 405
        })

        # Bad Accept Header
        tests.append({
            "type": "negative",
            "name": "Content Negotiation Failure - Invalid Accept Header",
            "description": "Tests the API's response when the client requests an unsupported media type via the Accept header.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": {**self._clean_headers(self.headers), "Accept": "application/xml"},
            "query_params": self._clean_query_params(self.query_params),
            "test_body": self.body,
            "expected_status": 406
        })

        return tests

    def _generate_boundary_tests(self) -> List[Dict[str, Any]]:
        tests = []
        # Resource ID Boundary
        if "/" in self.url:
            tests.append({
                "type": "symmetric",
                "name": "Resource Validation - Non-existent Identifier",
                "description": "Verifies the API's error handling when a request targets a resource ID that does not exist.",
                "test_url": self.url + "999999999",
                "test_method": self.method,
                "test_headers": self._clean_headers(self.headers),
                "query_params": self._clean_query_params(self.query_params),
                "test_body": self.body,
                "expected_status": 404
            })

            tests.append({
                "type": "symmetric",
                "name": "Resource Validation - Malformed Identifier",
                "description": "Tests the API's resilience when provided with a syntactically invalid resource identifier (e.g., non-alphanumeric).",
                "test_url": self.url + "!@#$%^&*",
                "test_method": self.method,
                "test_headers": self._clean_headers(self.headers),
                "query_params": self._clean_query_params(self.query_params),
                "test_body": self.body,
                "expected_status": 400
            })

        # Parameter Boundary
        tests.append({
            "type": "symmetric",
            "name": "Edge Case - Excessive Parameter Length",
            "description": "Determines the server's behavior when subjected to an unusually large query parameter or payload field.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": self._clean_query_params({**self.query_params, "long_param": "A" * 2000}),
            "test_body": self._create_large_body() if self.body else None,
            "expected_status": 414 if self.method == "GET" else 413
        })

        return tests

    def _generate_security_tests(self) -> List[Dict[str, Any]]:
        tests = []
        # SQL Injection in URL/Params
        tests.append({
            "type": "security",
            "name": "Vulnerability Scan - SQL Injection (URL/Params)",
            "description": "Probes the endpoint for SQL injection vulnerabilities by injecting payloads into the URL path or query parameters.",
            "test_url": self.url + urllib.parse.quote(self.SQL_INJECTION_PAYLOADS[0]),
            "test_method": self.method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": self._clean_query_params({**self.query_params, "id": self.SQL_INJECTION_PAYLOADS[1]}),
            "test_body": self._inject_payload(self.SQL_INJECTION_PAYLOADS) if self.body else None,
            "expected_status": 400
        })

        # XSS in Params
        tests.append({
            "type": "security",
            "name": "Vulnerability Scan - Cross-Site Scripting (XSS)",
            "description": "Tests if the API correctly sanitizes input to prevent reflected XSS attacks via query parameters.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": self._clean_query_params({**self.query_params, "q": self.XSS_PAYLOADS[0]}),
            "test_body": self._inject_payload(self.XSS_PAYLOADS) if self.body else None,
            "expected_status": 400
        })

        # OS Command Injection
        tests.append({
            "type": "security",
            "name": "Vulnerability Scan - OS Command Injection",
            "description": "Attempts to execute arbitrary shell commands through input fields or parameters to test for command injection flaws.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": self._clean_query_params({**self.query_params, "cmd": self.OS_COMMAND_PAYLOADS[0]}),
            "test_body": self._inject_payload(self.OS_COMMAND_PAYLOADS) if self.body else None,
            "expected_status": 400
        })

        # Header Injection
        tests.append({
            "type": "security",
            "name": "Vulnerability Scan - HTTP Header Injection",
            "description": "Tests for CRLF injection or header manipulation by injecting malicious values into custom headers.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": {**self._clean_headers(self.headers),
                             "X-Forwarded-For": "127.0.0.1\r\nSet-Cookie: exploit=true"},
            "query_params": self._clean_query_params(self.query_params),
            "test_body": self.body,
            "expected_status": 400
        })

        return tests

    def _generate_generic_error_case(self) -> Dict[str, Any]:
        return {
            "type": "negative",
            "name": "Resilience Test - Unexpected Input Format",
            "description": "Tests the API's stability when receiving data in a format that deviates from the expected schema.",
            "test_url": self.url,
            "test_method": self.method,
            "test_headers": self._clean_headers(self.headers),
            "query_params": {"unexpected": "data_format_123"},
            "test_body": "plain text instead of json" if self.method in ['POST', 'PUT', 'PATCH'] else None,
            "expected_status": 400
        }

    # Helper methods
    def _clean_headers(self, headers: Dict[str, Any]) -> Dict[str, str]:
        if not headers: return {}
        return {k: str(v) for k, v in headers.items() if v is not None}
    
    def _clean_query_params(self, params: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        if not params: return None
        return {k: str(v) for k, v in params.items() if v is not None}

    def _get_success_status(self) -> int:
        status_map = {'GET': 200, 'POST': 201, 'PUT': 200, 'PATCH': 200, 'DELETE': 204}
        return status_map.get(self.method, 200)

    def _vary_params(self, params: Dict[str, Any]) -> Optional[Dict[str, str]]:
        if not params: return {"v": "1"}
        new_params = {}
        for k, v in params.items():
            if isinstance(v, str):
                new_params[k] = f"alt_{v}"
            else:
                new_params[k] = str(v)
        return new_params

    def _create_alternative_valid_body(self) -> Optional[Dict[str, Any]]:
        if not self.body or not isinstance(self.body, dict): return self.body
        alt_body = {}
        for key, value in self.body.items():
            if isinstance(value, str):
                alt_body[key] = f"test_{value}_{random.randint(100, 999)}"
            elif isinstance(value, int):
                alt_body[key] = value + 1
            else:
                alt_body[key] = value
        return alt_body

    def _create_large_body(self) -> Any:
        if not self.body: return {"data": "A" * 10000}
        if isinstance(self.body, dict):
            return {k: ("B" * 5000 if isinstance(v, str) else v) for k, v in self.body.items()}
        return "C" * 10000

    def _inject_payload(self, payloads: List[str]) -> Any:
        payload = random.choice(payloads)
        if not self.body or not isinstance(self.body, dict): return {"input": payload}
        injected_body = self.body.copy()
        string_keys = [k for k, v in injected_body.items() if isinstance(v, str)]
        target_key = random.choice(string_keys) if string_keys else next(iter(injected_body))
        injected_body[target_key] = payload
        return injected_body


def generate_fallback_tests(api_config: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    engine = FallbackTestEngine(api_config)
    return {"test_cases": engine.generate_test_cases()}
