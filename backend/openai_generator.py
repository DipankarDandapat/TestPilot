import json
import os
import re
import logging
from openai import OpenAI
from openai.types.shared_params import ResponseFormatJSONObject
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


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


def generate_test_cases_openai(api: Dict[str, Any], business_rules: Optional[str] = None) -> List[Dict[str, Any]]:
    """Generate test cases using OpenAI."""
    openai_key = os.environ.get('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not configured")

    openai_model = os.environ.get('OPENAI_MODEL', 'gpt-4-turbo-preview')
    client = OpenAI(api_key=openai_key)
    prompt = build_prompt(api, business_rules)

    logger.info(f"Using OpenAI model: {openai_model}")

    response = client.chat.completions.create(
        model=openai_model,
        messages=[
            ChatCompletionSystemMessageParam(
                role="system",
                content="You are an expert API testing engineer who generates comprehensive test cases. "
                        "Always return ONLY a valid JSON object with no additional text, explanations, or markdown formatting. "
                        "CRITICAL: Do not include trailing commas in JSON objects or arrays."
            ),
            ChatCompletionUserMessageParam(role="user", content=prompt)
        ],
        temperature=0.3,
        response_format=ResponseFormatJSONObject(type="json_object")
    )

    response_text = response.choices[0].message.content.strip()
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
    raise ValueError("Unexpected OpenAI response structure")
