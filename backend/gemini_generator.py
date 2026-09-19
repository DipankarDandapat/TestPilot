import json
import os
import re
import logging
from google import genai
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

GEMINI_FALLBACK_MODELS = [
    'gemini-2.0-flash',
    'gemini-1.5-flash',
    'gemini-2.5-flash',
]


def _get_gemini_models(client) -> list:
    """Dynamically fetch available Gemini models that support generateContent."""
    try:
        all_models = [m.name for m in client.models.list()
                      if 'generateContent' in (m.supported_actions or [])]
        flash_models = [m for m in all_models if 'flash' in m.lower() and 'embed' not in m.lower()]
        return flash_models if flash_models else all_models
    except Exception:
        return GEMINI_FALLBACK_MODELS


def build_prompt(api: Dict[str, Any], business_rules: Optional[str] = None) -> str:
    business_rules_section = ""
    if business_rules and business_rules.strip():
        business_rules_section = f"""

Business Requirements / Validation Rules:
{business_rules.strip()}

IMPORTANT: Use the above business requirements to generate targeted test cases that validate:
- Field length limits, formats, and allowed values
- Uniqueness constraints
- Conditional logic and dependencies between fields
- Permission/role-based access rules
- Boundary values based on specified ranges
- Business logic validation scenarios
"""

    return f"""
Generate comprehensive test cases for the following API:

API Name: {api['name']}
URL: {api['url']}
Method: {api['method']}
Headers: {json.dumps(api['headers'], indent=2)}
Query Params: {json.dumps(api['query_params'], indent=2) if api['query_params'] else 'None'}
Body: {json.dumps(api['body'], indent=2) if api['body'] else 'None'}
Description: {api['description']}
{business_rules_section}

Generate test cases in these MANDATORY categories:

1. POSITIVE TEST CASES (2-3 tests) - Valid inputs that should succeed
   - Happy path with valid data
   - Alternative valid scenarios

2. NEGATIVE TEST CASES (3-4 tests) - Invalid inputs that should fail gracefully
   - Invalid data types (string instead of number, etc.)
   - Missing required fields
   - Extra/unexpected fields
   - Malformed request body

3. SYMMETRIC TEST CASES (3-4 tests) - Boundary values and edge cases
   - Minimum values (0, empty string, empty array)
   - Maximum values (very large numbers, long strings)
   - Null/None values
   - Empty objects/arrays

4. SECURITY TEST CASES (3-4 tests) - Security vulnerabilities
   - SQL injection attempts (e.g., "' OR '1'='1", "1; DROP TABLE users--")
   - XSS payloads (e.g., "<script>alert('XSS')</script>")
   - Authentication bypass (missing/invalid tokens, expired tokens)
   - Authorization tests (accessing resources without permission)

For each test case, provide:
- name: A descriptive name
- description: What the test validates
- test_url: The URL to test (may be modified from original)
- test_method: HTTP method (may be same or different)
- test_headers: Headers to send (as JSON object)
- query_params: Query parameters (as JSON object or null)
- test_body: Request body if applicable (as JSON object or null)
- expected_status: Expected HTTP status code (200, 400, 401, 403, 422, 500, etc.)
- assertions: Validation rules (as JSON object with these fields):
  * expected_status: Expected status code
  * max_response_time: Maximum response time in seconds (default 2.0)
  * content_type: Expected content type (e.g., "application/json")
  * response_not_empty: Boolean, true if response should not be empty
  * response_schema: Object with required_fields array (optional)

Return ONLY valid JSON with NO markdown formatting. Use this exact structure:
{{
  "test_cases": [
    {{
      "type": "positive",
      "name": "Test name",
      "description": "What it tests",
      "test_url": "URL to test",
      "test_method": "GET",
      "test_headers": {{}},
      "query_params": null,
      "test_body": null,
      "expected_status": 200,
      "assertions": {{
        "expected_status": 200,
        "max_response_time": 2.0,
        "content_type": "application/json",
        "response_not_empty": true
      }}
    }}
  ]
}}

Generate 11-15 test cases total (2-3 positive, 3-4 negative, 3-4 symmetric, 3-4 security). CRITICAL: No trailing commas.
"""


def generate_test_cases_gemini(api: Dict[str, Any], business_rules: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate test cases using Google Gemini (google-genai SDK)."""
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_key or gemini_key == 'your-gemini-api-key-here':
        raise ValueError("GEMINI_API_KEY not configured")

    prompt = build_prompt(api, business_rules)
    client = genai.Client(api_key=gemini_key)
    primary = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
    models_to_try = _get_gemini_models(client)
    # Ensure primary model is tried first if it's in the list
    if primary in models_to_try:
        models_to_try = [primary] + [m for m in models_to_try if m != primary]
    elif models_to_try:
        pass  # use discovered order
    else:
        models_to_try = GEMINI_FALLBACK_MODELS

    last_error = None
    for model_name in models_to_try:
        try:
            logger.info(f"Trying Gemini model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=f"You are an expert API testing engineer. Return ONLY valid JSON with no markdown.\n{prompt}"
            )

            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = re.sub(r',\s*([}\]])', r'\1', response_text.strip())

            parsed = json.loads(response_text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict) and 'test_cases' in parsed:
                return parsed['test_cases']
            raise ValueError("Unexpected Gemini response structure")

        except Exception as e:
            last_error = e
            err_str = str(e)
            if any(code in err_str for code in ['503', '404', 'UNAVAILABLE', 'NOT_FOUND', 'no longer available']):
                logger.warning(f"Model {model_name} unavailable, trying next: {err_str[:120]}")
                continue
            raise

    raise Exception(f"All Gemini models failed. Last error: {last_error}")
