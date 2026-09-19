import requests
import json
import jsonschema
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

def execute_contract_test(test_case: Dict[str, Any], base_url: str, auth_config: Optional[Dict] = None) -> Dict[str, Any]:
    """Execute a single contract test case"""
    try:
        # Build URL
        url = base_url + test_case['endpoint_path']
        
        # Replace path parameters
        if test_case.get('path_params'):
            for param_name, param_value in test_case['path_params'].items():
                url = url.replace(f"{{{param_name}}}", str(param_value))
        
        # Prepare headers
        headers = test_case.get('headers', {})
        if auth_config:
            headers.update(get_auth_headers(auth_config))
        
        # Execute request
        start_time = datetime.now(timezone.utc)
        
        response = requests.request(
            method=test_case['method'],
            url=url,
            headers=headers,
            params=test_case.get('query_params'),
            json=test_case.get('body'),
            timeout=10
        )
        
        end_time = datetime.now(timezone.utc)
        response_time = (end_time - start_time).total_seconds()
        
        # Parse response
        try:
            response_body = response.json()
        except:
            response_body = response.text
        
        return {
            "success": True,
            "status_code": response.status_code,
            "response_body": response_body,
            "response_time": response_time,
            "request_url": url,
            "request_method": test_case['method'],
            "request_body": test_case.get('body'),
            "error": None
        }
    
    except Exception as e:
        logger.error(f"Test execution failed: {str(e)}")
        return {
            "success": False,
            "status_code": None,
            "response_body": None,
            "response_time": None,
            "request_url": None,
            "request_method": test_case.get('method'),
            "request_body": test_case.get('body'),
            "error": str(e)
        }

def validate_response_schema(response_body: Any, expected_schema: Dict) -> Dict[str, Any]:
    """Validate response against expected schema"""
    try:
        jsonschema.validate(instance=response_body, schema=expected_schema)
        return {
            "valid": True,
            "errors": []
        }
    except jsonschema.ValidationError as e:
        return {
            "valid": False,
            "errors": [{
                "message": e.message,
                "path": list(e.path),
                "schema_path": list(e.schema_path)
            }]
        }
    except Exception as e:
        return {
            "valid": False,
            "errors": [{"message": str(e)}]
        }

def get_auth_headers(auth_config: Dict) -> Dict[str, str]:
    """Generate authentication headers from config"""
    headers = {}
    
    auth_type = auth_config.get('type', 'none')
    
    if auth_type == 'bearer':
        token = auth_config.get('token', '')
        headers['Authorization'] = f"Bearer {token}"
    
    elif auth_type == 'api_key':
        key_name = auth_config.get('key_name', 'X-API-Key')
        key_value = auth_config.get('key_value', '')
        headers[key_name] = key_value
    
    elif auth_type == 'basic':
        import base64
        username = auth_config.get('username', '')
        password = auth_config.get('password', '')
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers['Authorization'] = f"Basic {credentials}"
    
    return headers

async def execute_all_tests(contract_test_id: str, test_cases: list, base_url: str, auth_config: Optional[Dict], db) -> Dict[str, Any]:
    """Execute all test cases for a contract test"""
    results = []
    passed_count = 0
    failed_count = 0
    total_time = 0
    
    for test_case in test_cases:
        # Execute test
        result = execute_contract_test(test_case, base_url, auth_config)
        
        # Validate schema if expected
        schema_validation = {"valid": True, "errors": []}
        if test_case.get('expected_response_schema') and result['response_body']:
            schema_validation = validate_response_schema(
                result['response_body'],
                test_case['expected_response_schema']
            )
        
        # Check if test passed
        status_match = result['status_code'] == test_case.get('expected_status')
        schema_valid = schema_validation['valid']
        passed = status_match and schema_valid and result['success']
        
        if passed:
            passed_count += 1
        else:
            failed_count += 1
        
        if result['response_time']:
            total_time += result['response_time']
        
        # Check if result already exists for this test case
        async with db.execute(
            'SELECT id FROM contract_test_results WHERE contract_test_case_id = ?',
            (test_case['id'],)
        ) as cursor:
            existing = await cursor.fetchone()
        
        if existing:
            # Update existing result
            await db.execute(
                '''UPDATE contract_test_results SET
                   actual_status_code = ?, response_body = ?,
                   schema_validation_result = ?, response_time = ?, error_message = ?, executed_at = ?,
                   request_url = ?, request_method = ?, request_body = ?
                   WHERE contract_test_case_id = ?''',
                (
                    result['status_code'],
                    json.dumps(result['response_body']) if result['response_body'] else None,
                    'pass' if schema_validation['valid'] else 'fail',
                    result['response_time'],
                    result['error'] or (json.dumps(schema_validation['errors']) if not schema_validation['valid'] else None),
                    datetime.now(timezone.utc).isoformat(),
                    result.get('request_url'),
                    result.get('request_method'),
                    json.dumps(result.get('request_body')) if result.get('request_body') else None,
                    test_case['id']
                )
            )
            result_id = existing[0]
        else:
            # Insert new result
            result_id = str(__import__('uuid').uuid4())
            await db.execute(
                '''INSERT INTO contract_test_results 
                   (id, contract_test_case_id, actual_status_code, 
                    response_body, schema_validation_result, response_time, error_message, executed_at,
                    request_url, request_method, request_body)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    result_id,
                    test_case['id'],
                    result['status_code'],
                    json.dumps(result['response_body']) if result['response_body'] else None,
                    'pass' if schema_validation['valid'] else 'fail',
                    result['response_time'],
                    result['error'] or (json.dumps(schema_validation['errors']) if not schema_validation['valid'] else None),
                    datetime.now(timezone.utc).isoformat(),
                    result.get('request_url'),
                    result.get('request_method'),
                    json.dumps(result.get('request_body')) if result.get('request_body') else None
                )
            )
        
        # Update test case status
        await db.execute(
            'UPDATE contract_test_cases SET status = ? WHERE id = ?',
            ('passed' if passed else 'failed', test_case['id'])
        )
        
        results.append({
            "test_case_id": test_case['id'],
            "test_name": test_case['test_name'],
            "passed": passed,
            "status_code": result['status_code'],
            "expected_status": test_case.get('expected_status'),
            "schema_valid": schema_validation['valid'],
            "response_time": result['response_time'],
            "error": result['error']
        })
    
    await db.commit()
    
    return {
        "total": len(test_cases),
        "passed": passed_count,
        "failed": failed_count,
        "total_time": total_time,
        "results": results
    }
