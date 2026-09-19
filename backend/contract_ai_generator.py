import json
import os
from openai import OpenAI
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

def generate_request_from_schema(endpoint_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a single request from endpoint schema using OpenAI"""
    openai_key = os.environ.get('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not configured")
    
    client = OpenAI(api_key=openai_key)
    
    prompt = f"""
Generate a valid API request for the following endpoint:

Path: {endpoint_data['path']}
Method: {endpoint_data['method']}
Description: {endpoint_data.get('description', 'N/A')}

Parameters:
- Path params: {json.dumps(endpoint_data['parameters'].get('path', []), indent=2)}
- Query params: {json.dumps(endpoint_data['parameters'].get('query', []), indent=2)}
- Headers: {json.dumps(endpoint_data['parameters'].get('header', []), indent=2)}

Request Schema:
{json.dumps(endpoint_data.get('request_schema', {}), indent=2)}

Generate a realistic request with valid data that matches the schema.

Return ONLY valid JSON with this structure:
{{
  "path_params": {{}},
  "query_params": {{}},
  "headers": {{}},
  "body": {{}}
}}
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an API testing expert. Generate valid API requests based on schemas. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        response_text = response.choices[0].message.content.strip()
        return json.loads(response_text)
    
    except Exception as e:
        logger.error(f"OpenAI request generation failed: {str(e)}")
        # Fallback to basic generation
        return generate_fallback_request(endpoint_data)

def generate_fallback_request(endpoint_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate basic request without AI"""
    request = {
        "path_params": {},
        "query_params": {},
        "headers": {},
        "body": None
    }
    
    # Generate path params
    for param in endpoint_data['parameters'].get('path', []):
        request["path_params"][param['name']] = param.get('example', 'test-id')
    
    # Generate query params
    for param in endpoint_data['parameters'].get('query', []):
        if param.get('required'):
            request["query_params"][param['name']] = param.get('example', 'test-value')
    
    # Generate headers
    for param in endpoint_data['parameters'].get('header', []):
        if param.get('required'):
            request["headers"][param['name']] = param.get('example', 'test-header')
    
    # Generate body from schema
    if endpoint_data.get('request_schema'):
        request["body"] = generate_body_from_schema(endpoint_data['request_schema'])
    
    return request

def generate_body_from_schema(schema: Dict) -> Any:
    """Generate request body from schema"""
    if not schema:
        return None
    
    schema_type = schema.get("type", "object")
    
    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        body = {}
        
        for prop_name, prop_schema in properties.items():
            if prop_name in required:
                body[prop_name] = generate_value_from_schema(prop_schema)
        
        return body
    
    return generate_value_from_schema(schema)

def generate_value_from_schema(schema: Dict) -> Any:
    """Generate a value based on schema type"""
    schema_type = schema.get("type", "string")
    
    if "example" in schema:
        return schema["example"]
    
    if schema_type == "string":
        return "test-string"
    elif schema_type == "integer":
        return 1
    elif schema_type == "number":
        return 1.0
    elif schema_type == "boolean":
        return True
    elif schema_type == "array":
        items = schema.get("items", {})
        return [generate_value_from_schema(items)]
    elif schema_type == "object":
        return generate_body_from_schema(schema)
    
    return None

def generate_multiple_scenarios(endpoint_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate single test scenario per endpoint matching swagger definition"""
    scenarios = []
    
    # Generate only 1 test case per endpoint - happy path with swagger name
    try:
        request_data = generate_fallback_request(endpoint_data)
        
        # Use swagger summary or operation_id as test name
        test_name = endpoint_data.get('summary') or endpoint_data.get('operation_id') or f"{endpoint_data['method']} {endpoint_data['path']}"
        
        # Determine expected status from swagger response schemas
        expected_status = 200  # Default
        if endpoint_data.get('response_schemas'):
            # Get first successful status code (2xx or 3xx)
            for status_code in sorted(endpoint_data['response_schemas'].keys()):
                try:
                    status_int = int(status_code)
                    if 200 <= status_int < 400:
                        expected_status = status_int
                        break
                except (ValueError, TypeError):
                    continue
        
        scenarios.append({
            "name": test_name,
            "type": "positive",
            "request": request_data,
            "expected_status": expected_status
        })
    except Exception as e:
        logger.error(f"Failed to generate test case: {str(e)}")
    
    return scenarios
