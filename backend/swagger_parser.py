import json
from typing import Dict, List, Any, Optional

def parse_swagger_file(swagger_json: Dict[str, Any]) -> Dict[str, Any]:
    """Parse swagger file and detect version"""
    version = "3.0" if "openapi" in swagger_json else "2.0"
    
    # Extract base URL
    base_url = ""
    if version == "3.0":
        if "servers" in swagger_json and swagger_json["servers"]:
            base_url = swagger_json["servers"][0].get("url", "")
    else:
        schemes = swagger_json.get("schemes", ["https"])
        host = swagger_json.get("host", "")
        base_path = swagger_json.get("basePath", "")
        if host:
            base_url = f"{schemes[0]}://{host}{base_path}"
    
    # Extract security schemes
    security_schemes = {}
    if version == "3.0":
        security_schemes = swagger_json.get("components", {}).get("securitySchemes", {})
    else:
        security_schemes = swagger_json.get("securityDefinitions", {})
    
    return {
        "version": version,
        "base_url": base_url,
        "security_schemes": security_schemes
    }

def extract_endpoints(swagger_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all endpoints from swagger"""
    version = "3.0" if "openapi" in swagger_json else "2.0"
    paths = swagger_json.get("paths", {})
    endpoints = []
    
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.upper() not in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
                continue
            
            # Extract parameters
            parameters = extract_parameters(operation, path_item, version)
            
            # Extract request schema
            request_schema = extract_request_schema(operation, version, swagger_json)
            
            # Extract response schemas
            response_schemas = extract_response_schemas(operation, version, swagger_json)
            
            # Check authentication
            auth_required = "security" in operation or "security" in swagger_json
            
            endpoints.append({
                "path": path,
                "method": method.upper(),
                "summary": operation.get("summary", ""),
                "description": operation.get("description", ""),
                "parameters": parameters,
                "request_schema": request_schema,
                "response_schemas": response_schemas,
                "auth_required": auth_required,
                "operation_id": operation.get("operationId", f"{method}_{path}")
            })
    
    return endpoints

def extract_parameters(operation: Dict, path_item: Dict, version: str) -> Dict[str, List[Dict]]:
    """Extract parameters from operation"""
    params = {
        "path": [],
        "query": [],
        "header": [],
        "cookie": []
    }
    
    # Combine path-level and operation-level parameters
    all_params = path_item.get("parameters", []) + operation.get("parameters", [])
    
    for param in all_params:
        param_in = param.get("in", "query")
        param_data = {
            "name": param.get("name"),
            "required": param.get("required", False),
            "type": param.get("type") or param.get("schema", {}).get("type", "string"),
            "description": param.get("description", ""),
            "example": param.get("example") or param.get("schema", {}).get("example")
        }
        
        if param_in in params:
            params[param_in].append(param_data)
    
    return params

def extract_request_schema(operation: Dict, version: str, swagger_json: Dict) -> Optional[Dict]:
    """Extract request body schema"""
    if version == "3.0":
        request_body = operation.get("requestBody", {})
        if not request_body:
            return None
        
        content = request_body.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})
        
        return resolve_schema(schema, swagger_json, version)
    else:
        # Swagger 2.0
        for param in operation.get("parameters", []):
            if param.get("in") == "body":
                schema = param.get("schema", {})
                return resolve_schema(schema, swagger_json, version)
        return None

def extract_response_schemas(operation: Dict, version: str, swagger_json: Dict) -> Dict[str, Dict]:
    """Extract response schemas for different status codes"""
    responses = operation.get("responses", {})
    response_schemas = {}
    
    for status_code, response in responses.items():
        if version == "3.0":
            content = response.get("content", {})
            json_content = content.get("application/json", {})
            schema = json_content.get("schema", {})
        else:
            schema = response.get("schema", {})
        
        if schema:
            response_schemas[status_code] = {
                "description": response.get("description", ""),
                "schema": resolve_schema(schema, swagger_json, version)
            }
    
    return response_schemas

def resolve_schema(schema: Dict, swagger_json: Dict, version: str) -> Dict:
    """Resolve $ref in schema"""
    if not schema:
        return {}
    
    if "$ref" in schema:
        ref_path = schema["$ref"]
        parts = ref_path.split("/")[1:]  # Remove leading #
        
        resolved = swagger_json
        for part in parts:
            resolved = resolved.get(part, {})
        
        return resolve_schema(resolved, swagger_json, version)
    
    # Handle properties
    if "properties" in schema:
        resolved_props = {}
        for prop_name, prop_schema in schema["properties"].items():
            resolved_props[prop_name] = resolve_schema(prop_schema, swagger_json, version)
        schema["properties"] = resolved_props
    
    # Handle arrays
    if schema.get("type") == "array" and "items" in schema:
        schema["items"] = resolve_schema(schema["items"], swagger_json, version)
    
    return schema

def generate_example_from_schema(schema: Dict) -> Any:
    """Generate example data from schema"""
    if not schema:
        return None
    
    schema_type = schema.get("type", "object")
    
    if "example" in schema:
        return schema["example"]
    
    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        example = {}
        
        for prop_name, prop_schema in properties.items():
            if prop_name in required or len(properties) <= 5:
                example[prop_name] = generate_example_from_schema(prop_schema)
        
        return example
    
    elif schema_type == "array":
        items_schema = schema.get("items", {})
        return [generate_example_from_schema(items_schema)]
    
    elif schema_type == "string":
        return schema.get("example", "string")
    
    elif schema_type == "integer":
        return schema.get("example", 0)
    
    elif schema_type == "number":
        return schema.get("example", 0.0)
    
    elif schema_type == "boolean":
        return schema.get("example", True)
    
    return None
