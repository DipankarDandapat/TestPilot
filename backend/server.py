from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
import traceback
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import requests
import json
from openai import OpenAI
import aiosqlite
import uvicorn
import re
import urllib.parse
from fallback_test_engine import generate_fallback_tests
from report_generator import generate_html_report
from fastapi.responses import HTMLResponse
from fastapi import UploadFile, File
import swagger_parser
import contract_ai_generator
import contract_test_executor
import gemini_generator
import openai_generator
from genson import SchemaBuilder


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(ROOT_DIR / 'app.log')
    ],
    force=True
)
logger = logging.getLogger(__name__)

# SQLite database path
DB_PATH = ROOT_DIR / 'api_testing.db'

# Initialize database
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS api_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT NOT NULL,
                headers TEXT,
                query_params TEXT,
                body TEXT,
                description TEXT,
                project_name TEXT DEFAULT '',
                created_at TEXT
            )
        ''')
        # Add project_name column if not exists (migration)
        try:
            await db.execute('ALTER TABLE api_configs ADD COLUMN project_name TEXT DEFAULT ""')
        except:
            pass
        await db.execute('''
            CREATE TABLE IF NOT EXISTS test_cases (
                id TEXT PRIMARY KEY,
                api_id TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                test_url TEXT NOT NULL,
                test_method TEXT NOT NULL,
                test_headers TEXT,
                query_params TEXT,
                test_body TEXT,
                expected_status INTEGER,
                assertions TEXT,
                created_at TEXT,
                FOREIGN KEY (api_id) REFERENCES api_configs (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id TEXT PRIMARY KEY,
                test_case_id TEXT NOT NULL,
                api_id TEXT NOT NULL,
                type TEXT NOT NULL,
                request_url TEXT,
                request_method TEXT,
                request_headers TEXT,
                query_params TEXT,
                request_body TEXT,
                response_status INTEGER,
                response_body TEXT,
                response_headers TEXT,
                response_time REAL,
                error TEXT,
                passed INTEGER,
                failures TEXT,
                executed_at TEXT,
                FOREIGN KEY (test_case_id) REFERENCES test_cases (id),
                FOREIGN KEY (api_id) REFERENCES api_configs (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS collection_apis (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                api_id TEXT NOT NULL,
                order_index INTEGER,
                FOREIGN KEY (collection_id) REFERENCES collections (id),
                FOREIGN KEY (api_id) REFERENCES api_configs (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS collection_runs (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                executed_at TEXT,
                total_apis INTEGER,
                total_tests INTEGER,
                passed_tests INTEGER,
                failed_tests INTEGER,
                total_time REAL,
                FOREIGN KEY (collection_id) REFERENCES collections (id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS collection_run_results (
                id TEXT PRIMARY KEY,
                collection_run_id TEXT NOT NULL,
                test_result_id TEXT NOT NULL,
                api_id TEXT NOT NULL,
                test_case_id TEXT NOT NULL,
                passed INTEGER,
                FOREIGN KEY (collection_run_id) REFERENCES collection_runs (id),
                FOREIGN KEY (test_result_id) REFERENCES test_results (id),
                FOREIGN KEY (api_id) REFERENCES api_configs (id),
                FOREIGN KEY (test_case_id) REFERENCES test_cases (id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS api_test_results (
                id TEXT PRIMARY KEY,
                api_id TEXT NOT NULL UNIQUE,
                success INTEGER NOT NULL,
                status_code INTEGER,
                response_time REAL,
                request_url TEXT,
                request_method TEXT,
                request_headers TEXT,
                request_body TEXT,
                response_body TEXT,
                response_headers TEXT,
                response_cookies TEXT,
                error TEXT,
                executed_at TEXT,
                FOREIGN KEY (api_id) REFERENCES api_configs (id)
            )
        ''')

        # Clean up duplicate api_test_results (keep only latest per api_id)
        await db.execute('''
            DELETE FROM api_test_results WHERE id NOT IN (
                SELECT id FROM api_test_results GROUP BY api_id HAVING MAX(executed_at)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS collection_variables (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                description TEXT,
                is_secret INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                created_at TEXT,
                FOREIGN KEY (collection_id) REFERENCES collections (id) ON DELETE CASCADE,
                UNIQUE(collection_id, scope, key)
            )
        ''')

        # Contract testing tables
        await db.execute('''
            CREATE TABLE IF NOT EXISTS contract_tests (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                swagger_file_path TEXT,
                swagger_json TEXT NOT NULL,
                base_url TEXT,
                auth_config TEXT,
                created_at TEXT,
                updated_at TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS contract_test_endpoints (
                id TEXT PRIMARY KEY,
                contract_test_id TEXT NOT NULL,
                endpoint_path TEXT NOT NULL,
                http_method TEXT NOT NULL,
                request_schema TEXT,
                response_schema TEXT,
                auth_required INTEGER DEFAULT 0,
                parameters TEXT,
                created_at TEXT,
                FOREIGN KEY (contract_test_id) REFERENCES contract_tests (id) ON DELETE CASCADE
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS contract_test_cases (
                id TEXT PRIMARY KEY,
                contract_test_id TEXT NOT NULL,
                endpoint_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                generated_request TEXT,
                expected_response_schema TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (contract_test_id) REFERENCES contract_tests (id) ON DELETE CASCADE,
                FOREIGN KEY (endpoint_id) REFERENCES contract_test_endpoints (id) ON DELETE CASCADE
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS contract_test_results (
                id TEXT PRIMARY KEY,
                contract_test_case_id TEXT NOT NULL,
                actual_status_code INTEGER,
                expected_status_code INTEGER,
                response_body TEXT,
                schema_validation_result TEXT,
                response_time REAL,
                error_message TEXT,
                executed_at TEXT,
                FOREIGN KEY (contract_test_case_id) REFERENCES contract_test_cases (id) ON DELETE CASCADE
            )
        ''')
        
        await db.commit()

# Create the main app without a prefix
app = FastAPI()

# Add CORS middleware FIRST
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000",
        "https://sub.dipankardandapat.xyz"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}\n{traceback.format_exc()}")
        raise

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class APIConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    url: str
    method: str  # GET, POST, PUT, PATCH, DELETE
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    description: Optional[str] = ""
    project_name: Optional[str] = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class APIConfigCreate(BaseModel):
    name: str
    url: str
    method: str
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    description: Optional[str] = ""
    project_name: Optional[str] = ""


class TestCase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_id: str
    type: str  # positive, negative, symmetric, security
    name: str
    description: str
    test_url: str
    test_method: str
    test_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, str]] = None
    test_body: Optional[Dict[str, Any]] = None
    expected_status: Optional[int] = None
    assertions: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    test_case_id: str
    api_id: str
    type: str  # positive, negative, symmetric, security
    request_url: str
    request_method: str
    request_headers: Dict[str, str]
    query_params: Optional[Dict[str, str]] = None
    request_body: Optional[Dict[str, Any]] = None
    response_status: Optional[int] = None
    response_body: Optional[Any] = None
    response_headers: Optional[Dict[str, str]] = None
    response_time: Optional[float] = None
    error: Optional[str] = None
    passed: bool
    failures: Optional[List[Dict[str, Any]]] = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GenerateTestCasesRequest(BaseModel):
    api_id: str
    business_rules: Optional[str] = None
    provider: Optional[str] = "openai"  # openai | gemini | local


class RunTestsRequest(BaseModel):
    api_id: str
    test_case_ids: Optional[List[str]] = None  # If None, run all tests for the API


class ParseCurlRequest(BaseModel):
    curl_command: str


class TestCaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    test_url: Optional[str] = None
    test_method: Optional[str] = None
    test_headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, str]] = None
    test_body: Optional[Dict[str, Any]] = None
    expected_status: Optional[int] = None
    assertions: Optional[Dict[str, Any]] = None


class Collection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    api_ids: List[str] = []


class CollectionRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    collection_id: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_apis: int
    total_tests: int
    passed_tests: int
    failed_tests: int
    total_time: float


class CollectionVariable(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    collection_id: str
    scope: str  # 'headers', 'query_params', 'body', 'url'
    key: str
    value: str
    description: Optional[str] = ""
    is_secret: bool = False
    enabled: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CollectionVariableCreate(BaseModel):
    scope: str
    key: str
    value: str
    description: Optional[str] = ""
    is_secret: bool = False
    enabled: bool = True


class CollectionVariableUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None
    is_secret: Optional[bool] = None
    enabled: Optional[bool] = None


# Routes
@api_router.get("/")
async def root():
    return {"message": "API Testing Platform"}


# Assertion validation function
def validate_assertions(response, response_time, assertions):
    """Validate all assertions and return list of failures"""
    failures = []
    
    if not assertions:
        return failures
    
    # Status code assertion
    if 'expected_status' in assertions and assertions['expected_status']:
        if response.status_code != assertions['expected_status']:
            failures.append({
                'assertion_type': 'status_code',
                'expected': assertions['expected_status'],
                'actual': response.status_code,
                'message': f"Expected status {assertions['expected_status']} but got {response.status_code}"
            })
    
    # Response time assertion
    if 'max_response_time' in assertions and assertions['max_response_time']:
        if response_time > assertions['max_response_time']:
            failures.append({
                'assertion_type': 'response_time',
                'expected': f"< {assertions['max_response_time']}s",
                'actual': f"{response_time:.2f}s",
                'message': f"Response time {response_time:.2f}s exceeded threshold of {assertions['max_response_time']}s"
            })
    
    # Content-Type assertion
    if 'content_type' in assertions and assertions['content_type']:
        actual_content_type = response.headers.get('Content-Type', '')
        if assertions['content_type'] not in actual_content_type:
            failures.append({
                'assertion_type': 'content_type',
                'expected': assertions['content_type'],
                'actual': actual_content_type,
                'message': f"Expected Content-Type '{assertions['content_type']}' but got '{actual_content_type}'"
            })
    
    # Response not empty assertion
    if assertions.get('response_not_empty'):
        try:
            body = response.json() if response.text else None
            if not body:
                failures.append({
                    'assertion_type': 'response_not_empty',
                    'expected': 'Non-empty response',
                    'actual': 'Empty response',
                    'message': 'Expected non-empty response body'
                })
        except:
            pass
    
    # Response schema validation
    if 'response_schema' in assertions and assertions['response_schema']:
        try:
            body = response.json()
            schema = assertions['response_schema']
            
            # Check required fields
            if 'required_fields' in schema:
                for field in schema['required_fields']:
                    if field not in body:
                        failures.append({
                            'assertion_type': 'required_field',
                            'expected': f"Field '{field}' present",
                            'actual': f"Field '{field}' missing",
                            'message': f"Required field '{field}' is missing from response"
                        })
        except:
            pass
    
    return failures


# Helper function to generate assertions based on test type
def generate_assertions_for_type(test_type, expected_status):
    """Generate default assertions based on test type"""
    assertions = {
        'expected_status': expected_status,
        'max_response_time': 2.0
    }
    
    if test_type == 'positive':
        assertions.update({
            'content_type': 'application/json',
            'response_not_empty': True
        })
    elif test_type == 'negative':
        assertions.update({
            'content_type': 'application/json'
        })
    elif test_type == 'security':
        assertions.update({
            'max_response_time': 3.0
        })
    
    return assertions
def apply_collection_variables(api_config: Dict[str, Any], variables: List[Dict[str, Any]]) -> tuple:
    """Apply collection variables to API config at runtime"""
    # Ensure api_config is a dict
    if hasattr(api_config, 'keys') and not isinstance(api_config, dict):
        api_config = {k: api_config[k] for k in api_config.keys()}
    
    resolved = {
        'url': api_config.get('url', ''),
        'method': api_config.get('method', 'GET'),
        'headers': (api_config.get('headers') or {}).copy(),
        'query_params': (api_config.get('query_params') or {}).copy() if api_config.get('query_params') else None,
        'body': (api_config.get('body') or {}).copy() if api_config.get('body') else None
    }
    
    replacements = []
    
    for var in variables:
        # Ensure var is a dict
        if hasattr(var, 'keys') and not isinstance(var, dict):
            var = {k: var[k] for k in var.keys()}
        
        if not var.get('enabled'):
            continue
        
        scope = var['scope']
        key = var['key']
        value = var['value']
        
        # Replace in headers
        if scope == 'headers' and key in resolved['headers']:
            old_value = resolved['headers'][key]
            resolved['headers'][key] = value
            replacements.append({'scope': 'headers', 'key': key, 'old_value': old_value, 'new_value': value})
        
        # Replace in query params
        elif scope == 'query_params' and resolved['query_params'] and key in resolved['query_params']:
            old_value = resolved['query_params'][key]
            resolved['query_params'][key] = value
            replacements.append({'scope': 'query_params', 'key': key, 'old_value': old_value, 'new_value': value})
        
        # Replace in body
        elif scope == 'body' and resolved['body'] and isinstance(resolved['body'], dict) and key in resolved['body']:
            old_value = resolved['body'][key]
            resolved['body'][key] = value
            replacements.append({'scope': 'body', 'key': key, 'old_value': old_value, 'new_value': value})
        
        # Replace full URL (complete replacement)
        elif scope == 'url' and key == 'fullUrl':
            old_url = resolved['url']
            resolved['url'] = value
            replacements.append({'scope': 'url', 'key': 'fullUrl', 'old_value': old_url, 'new_value': value})
        
        # Replace base URL (protocol + domain only)
        elif scope == 'url' and key == 'baseUrl':
            url_pattern = r'^(https?://[^/]+)'
            match = re.match(url_pattern, resolved['url'])
            if match:
                old_base = match.group(1)
                resolved['url'] = resolved['url'].replace(old_base, value, 1)
                replacements.append({'scope': 'url', 'key': 'baseUrl', 'old_value': old_base, 'new_value': value})
    
    return resolved, replacements


# Parse cURL command
@api_router.post("/parse-curl")
async def parse_curl(request: ParseCurlRequest):
    try:
        curl_cmd = request.curl_command.strip()
        
        # Remove line breaks and normalize whitespace
        curl_cmd = ' '.join(curl_cmd.split())
        
        # Remove 'curl' from the beginning
        curl_cmd = re.sub(r'^curl\s+', '', curl_cmd, flags=re.IGNORECASE)
        
        # Extract method first (to help identify URL position)
        method = "GET"
        method_match = re.search(r'(?:-X|--request)\s+([A-Z]+)', curl_cmd)
        if method_match:
            method = method_match.group(1)
            # Remove method flag from command
            curl_cmd = re.sub(r'(?:-X|--request)\s+[A-Z]+\s*', '', curl_cmd)
        
        # Remove common flags that don't affect parsing
        curl_cmd = re.sub(r'--location\s*', '', curl_cmd)
        curl_cmd = re.sub(r'--compressed\s*', '', curl_cmd)
        curl_cmd = re.sub(r'-L\s*', '', curl_cmd)
        
        # Extract headers first (to remove them from URL search)
        headers = {}
        header_pattern = r'(?:-H|--header)\s+[\'"]([^\'"]+)[\'"]'
        header_matches = re.finditer(header_pattern, curl_cmd)
        for match in header_matches:
            header = match.group(1)
            if ':' in header:
                key, value = header.split(':', 1)
                headers[key.strip()] = value.strip()
        # Remove headers from command
        curl_cmd = re.sub(header_pattern, '', curl_cmd)
        
        # Extract body/data (to remove from URL search)
        body = None
        # Match data flags with various quote styles and handle escaped quotes
        body_patterns = [
            r'(?:-d|--data|--data-raw|--data-binary)\s+\'([^\']*(?:\\\'[^\']*)*)\'',  # Single quotes
            r'(?:-d|--data|--data-raw|--data-binary)\s+"([^"]*(?:\\\\"[^"]*)*)"',  # Double quotes
            r'(?:-d|--data|--data-raw|--data-binary)\s+([^\s\'"]+)',  # No quotes
        ]
        
        for pattern in body_patterns:
            body_match = re.search(pattern, curl_cmd, re.DOTALL)
            if body_match:
                body_str = body_match.group(1).strip()
                # Unescape quotes
                body_str = body_str.replace("\\\"", '"').replace("\\\'", "'")
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError:
                    # Try cleaning whitespace
                    body_str_clean = body_str.replace('\n', '').replace('\r', '')
                    try:
                        body = json.loads(body_str_clean)
                    except json.JSONDecodeError:
                        # Only use raw_data if it's actually non-JSON content
                        body = {"raw_data": body_str}
                break
        
        # Remove body from command
        if body is not None:
            for pattern in body_patterns:
                curl_cmd = re.sub(pattern, '', curl_cmd)
        
        # Extract URL - now it should be one of the remaining tokens
        url = None
        
        # Pattern 1: Quoted URL
        url_match = re.search(r'[\'"]([^\s\'"]+://[^\s\'"]+)[\'"]', curl_cmd)
        if url_match:
            url = url_match.group(1)
        
        # Pattern 2: Unquoted URL with protocol
        if not url:
            url_match = re.search(r'(https?://[^\s]+)', curl_cmd)
            if url_match:
                url = url_match.group(1)
        
        # Pattern 3: Any remaining token that looks like a URL
        if not url:
            # Remove all known flags
            remaining = re.sub(r'-[a-zA-Z]\s+[^-\s]+', '', curl_cmd)
            remaining = re.sub(r'--[a-z-]+\s+[^-\s]+', '', remaining)
            tokens = remaining.split()
            for token in tokens:
                if '://' in token or token.startswith('http') or '.' in token:
                    url = token.strip('\'"')
                    break
        
        if not url:
            raise HTTPException(status_code=400, detail="Could not extract URL from cURL command")
        
        # Clean URL from any trailing characters
        url = url.rstrip('\\').rstrip()
        
        # Extract query parameters from URL
        query_params = None
        if '?' in url:
            base_url, query_string = url.split('?', 1)
            url = base_url
            query_params = {}
            for param in query_string.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    query_params[key] = value
        
        return {
            "url": url,
            "method": method,
            "headers": headers if headers else None,
            "query_params": query_params,
            "body": body
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing cURL: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to parse cURL command: {str(e)}")


# Get overall statistics
@api_router.get("/stats")
async def get_overall_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        # Get total test cases
        async with db.execute('SELECT COUNT(*) FROM test_cases') as cursor:
            total_test_cases = (await cursor.fetchone())[0]
        
        # Get total test results
        async with db.execute('SELECT COUNT(*) FROM test_results') as cursor:
            total_test_runs = (await cursor.fetchone())[0]
        
        # Get passed tests
        async with db.execute('SELECT COUNT(*) FROM test_results WHERE passed = 1') as cursor:
            total_passed = (await cursor.fetchone())[0]
        
        # Get failed tests
        async with db.execute('SELECT COUNT(*) FROM test_results WHERE passed = 0') as cursor:
            total_failed = (await cursor.fetchone())[0]
    
    return {
        "total_test_cases": total_test_cases,
        "total_test_runs": total_test_runs,
        "total_passed": total_passed,
        "total_failed": total_failed
    }


# Get total API count
@api_router.get("/apis/count")
async def get_apis_count(project_name: Optional[str] = None, search: Optional[str] = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if search:
            search_term = f"%{search}%"
            async with db.execute(
                'SELECT COUNT(*) FROM api_configs WHERE (project_name LIKE ? OR name LIKE ? OR method LIKE ? OR url LIKE ?)',
                (search_term, search_term, search_term, search_term)
            ) as cursor:
                total = (await cursor.fetchone())[0]
        elif project_name:
            async with db.execute('SELECT COUNT(*) FROM api_configs WHERE project_name = ?', (project_name,)) as cursor:
                total = (await cursor.fetchone())[0]
        else:
            async with db.execute('SELECT COUNT(*) FROM api_configs') as cursor:
                total = (await cursor.fetchone())[0]
    return {"total": total}


# API Configuration endpoints
@api_router.post("/apis", response_model=APIConfig)
async def create_api_config(input: APIConfigCreate):
    try:
        logger.info(f"Received request: {input.model_dump()}")
        
        data = input.model_dump()
        api_obj = APIConfig(**data)
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'INSERT INTO api_configs (id, name, url, method, headers, body, description, created_at, query_params, project_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (api_obj.id, api_obj.name, api_obj.url, api_obj.method,
                 json.dumps(api_obj.headers) if api_obj.headers else json.dumps({}),
                 json.dumps(api_obj.body) if api_obj.body is not None else None,
                 api_obj.description or '', api_obj.created_at.isoformat(),
                 json.dumps(api_obj.query_params) if api_obj.query_params else None,
                 api_obj.project_name or '')
            )
            await db.commit()
        
        logger.info(f"API created: {api_obj.id}")
        return api_obj
    
    except Exception as e:
        logger.error(f"Error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/apis", response_model=List[APIConfig])
async def get_api_configs(page: int = 1, limit: int = 10, project_name: Optional[str] = None, search: Optional[str] = None):
    try:
        logger.info(f"GET /api/apis called - page: {page}, limit: {limit}, search: {search}")
        offset = (page - 1) * limit
        
        async with aiosqlite.connect(DB_PATH, timeout=5.0) as db:
            db.row_factory = aiosqlite.Row
            
            # Build query with optional search filter
            where_clause = ""
            params = []
            if search:
                where_clause = "WHERE (project_name LIKE ? OR name LIKE ? OR method LIKE ? OR url LIKE ?)"
                search_term = f"%{search}%"
                params = [search_term, search_term, search_term, search_term]
            elif project_name:
                where_clause = "WHERE project_name = ?"
                params = [project_name]
            
            # Get total count
            async with db.execute(f'SELECT COUNT(*) FROM api_configs {where_clause}', params) as cursor:
                total = (await cursor.fetchone())[0]
            
            # Get paginated results ordered by created_at DESC (newest first)
            async with db.execute(
                f'SELECT * FROM api_configs {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?',
                params + [limit, offset]
            ) as cursor:
                rows = await cursor.fetchall()
        
        logger.info(f"Found {len(rows)} API configs (total: {total})")
        apis = []
        for row in rows:
            # Safely get query_params with error handling
            query_params_value = None
            try:
                if 'query_params' in row.keys() and row['query_params']:
                    query_params_value = json.loads(row['query_params'])
            except (json.JSONDecodeError, TypeError):
                query_params_value = None
            
            # Safely get project_name
            project_name_value = ''
            try:
                if 'project_name' in row.keys():
                    project_name_value = row['project_name'] or ''
            except:
                project_name_value = ''
            
            apis.append(APIConfig(
                id=row['id'],
                name=row['name'],
                url=row['url'],
                method=row['method'],
                headers=json.loads(row['headers']) if row['headers'] else {},
                query_params=query_params_value,
                body=json.loads(row['body']) if row['body'] else None,
                description=row['description'] or '',
                project_name=project_name_value,
                created_at=datetime.fromisoformat(row['created_at'])
            ))
        
        logger.info(f"Returning {len(apis)} APIs")
        return apis
    except Exception as e:
        logger.error(f"Error in get_api_configs: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/projects")
async def get_projects():
    """Get distinct project names for autocomplete"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT project_name FROM api_configs WHERE project_name != '' ORDER BY project_name"
        ) as cursor:
            rows = await cursor.fetchall()
    return [row[0] for row in rows]


@api_router.get("/apis/{api_id}", response_model=APIConfig)
async def get_api_config(api_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM api_configs WHERE id = ?', (api_id,)) as cursor:
            row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="API not found")
    
    # Safely get query_params with error handling
    query_params_value = None
    try:
        if 'query_params' in row.keys() and row['query_params']:
            query_params_value = json.loads(row['query_params'])
    except (json.JSONDecodeError, TypeError):
        query_params_value = None
    
    # Safely get project_name
    project_name_value = ''
    try:
        if 'project_name' in row.keys():
            project_name_value = row['project_name'] or ''
    except:
        project_name_value = ''
    
    return APIConfig(
        id=row['id'],
        name=row['name'],
        url=row['url'],
        method=row['method'],
        headers=json.loads(row['headers']) if row['headers'] else {},
        query_params=query_params_value,
        body=json.loads(row['body']) if row['body'] else None,
        description=row['description'] or '',
        project_name=project_name_value,
        created_at=datetime.fromisoformat(row['created_at'])
    )


class APIConfigUpdate(BaseModel):
    url: Optional[str] = None
    method: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None


@api_router.put("/apis/{api_id}")
async def update_api_config(api_id: str, update_data: APIConfigUpdate):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM api_configs WHERE id = ?', (api_id,)) as cursor:
            row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="API not found")
    
    update_fields = []
    params = []
    
    if update_data.url is not None:
        update_fields.append('url = ?')
        params.append(update_data.url)
    if update_data.method is not None:
        update_fields.append('method = ?')
        params.append(update_data.method)
    if update_data.headers is not None:
        update_fields.append('headers = ?')
        params.append(json.dumps(update_data.headers))
    if update_data.query_params is not None:
        update_fields.append('query_params = ?')
        params.append(json.dumps(update_data.query_params) if update_data.query_params else None)
    if update_data.body is not None:
        update_fields.append('body = ?')
        params.append(json.dumps(update_data.body) if update_data.body else None)
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.append(api_id)
    query = f"UPDATE api_configs SET {', '.join(update_fields)} WHERE id = ?"
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()
    
    return {"message": "API updated successfully"}


@api_router.delete("/apis/{api_id}")
async def delete_api_config(api_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('DELETE FROM api_configs WHERE id = ?', (api_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="API not found")
        
        await db.execute('DELETE FROM test_cases WHERE api_id = ?', (api_id,))
        await db.execute('DELETE FROM test_results WHERE api_id = ?', (api_id,))
        await db.commit()
    
    return {"message": "API deleted successfully"}


# Test API endpoint before generating test cases
@api_router.post("/apis/{api_id}/test")
async def test_api_endpoint(api_id: str):
    # Get API config
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM api_configs WHERE id = ?', (api_id,)) as cursor:
            row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="API not found")
    
    # Parse API config
    query_params_value = None
    try:
        if 'query_params' in row.keys() and row['query_params']:
            query_params_value = json.loads(row['query_params'])
    except (json.JSONDecodeError, TypeError):
        query_params_value = None
    
    api_url = row['url']
    api_method = row['method']
    api_headers = json.loads(row['headers']) if row['headers'] else {}
    api_body = json.loads(row['body']) if row['body'] else None
    
    logger.info(f"Testing API - Method: {api_method}, URL: {api_url}")
    
    result_data = None
    try:
        start_time = datetime.now(timezone.utc)
        
        # Construct URL with query params
        if query_params_value:
            from urllib.parse import urlencode
            query_string = urlencode(query_params_value)
            if '?' in api_url:
                api_url += '&' + query_string
            else:
                api_url += '?' + query_string
        
        request_kwargs = {
            'method': api_method,
            'url': api_url,
            'headers': api_headers,
            'timeout': 10
        }
        
        if api_body:
            content_type = api_headers.get('Content-Type') or api_headers.get('content-type', '')
            if 'application/json' in content_type.lower():
                request_kwargs['json'] = api_body
            else:
                request_kwargs['data'] = api_body
        
        response = requests.request(**request_kwargs)
        end_time = datetime.now(timezone.utc)
        response_time = (end_time - start_time).total_seconds()
        
        # Try to parse response as JSON
        try:
            response_body = response.json()
        except:
            response_body = response.text
        
        result_data = {
            "success": True,
            "status_code": response.status_code,
            "response_time": response_time,
            "response_body": response_body,
            "response_headers": dict(response.headers),
            "response_cookies": {k: v for k, v in response.cookies.items()},
            "request_url": api_url,
            "request_method": api_method,
            "request_headers": api_headers,
            "request_body": api_body
        }
    
    except Exception as e:
        logger.error(f"Error testing API: {str(e)}")
        result_data = {
            "success": False,
            "error": str(e),
            "request_url": api_url,
            "request_method": api_method,
            "request_headers": api_headers,
            "request_body": api_body
        }
    
    # Store result in database (UPSERT - one record per api_id)
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        # Delete existing record for this api_id, then insert fresh
        await db.execute('DELETE FROM api_test_results WHERE api_id = ?', (api_id,))
        result_id = str(uuid.uuid4())
        await db.execute(
            '''INSERT INTO api_test_results 
               (id, api_id, success, status_code, response_time, request_url, request_method, 
                request_headers, request_body, response_body, response_headers, response_cookies, error, executed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (result_id, api_id, 1 if result_data.get('success') else 0,
             result_data.get('status_code'), result_data.get('response_time'),
             result_data.get('request_url'), result_data.get('request_method'),
             json.dumps(result_data.get('request_headers')) if result_data.get('request_headers') else None,
             json.dumps(result_data.get('request_body')) if result_data.get('request_body') else None,
             json.dumps(result_data.get('response_body')) if result_data.get('response_body') else None,
             json.dumps(result_data.get('response_headers')) if result_data.get('response_headers') else None,
             json.dumps(result_data.get('response_cookies')) if result_data.get('response_cookies') else None,
             result_data.get('error'), now)
        )
        await db.commit()
    
    result_data['id'] = result_id
    result_data['executed_at'] = now
    return result_data


# Get stored API test results
@api_router.get("/apis/{api_id}/test-results")
async def get_api_test_results(api_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM api_test_results WHERE api_id = ? ORDER BY executed_at DESC LIMIT 1',
            (api_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        # Parse cookies
        cookies_value = None
        try:
            if 'response_cookies' in row.keys() and row['response_cookies']:
                cookies_value = json.loads(row['response_cookies'])
        except (json.JSONDecodeError, TypeError, KeyError):
            cookies_value = None

        results.append({
            'id': row['id'],
            'success': bool(row['success']),
            'status_code': row['status_code'],
            'response_time': row['response_time'],
            'request_url': row['request_url'],
            'request_method': row['request_method'],
            'request_headers': json.loads(row['request_headers']) if row['request_headers'] else {},
            'request_body': json.loads(row['request_body']) if row['request_body'] else None,
            'response_body': json.loads(row['response_body']) if row['response_body'] and row['response_body'].startswith(('{', '[', '"')) else row['response_body'],
            'response_headers': json.loads(row['response_headers']) if row['response_headers'] else None,
            'response_cookies': cookies_value,
            'error': row['error'],
            'executed_at': row['executed_at']
        })
    
    return results


# Test Case Generation endpoint
@api_router.post("/generate-testcases")
async def generate_test_cases(request: GenerateTestCasesRequest):
    # Get API config
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM api_configs WHERE id = ?', (request.api_id,)) as cursor:
            row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="API not found")
    
    # Safely get query_params with error handling
    query_params_value = None
    try:
        if 'query_params' in row.keys() and row['query_params']:
            query_params_value = json.loads(row['query_params'])
    except (json.JSONDecodeError, TypeError):
        query_params_value = None
    
    api = {
        'name': row['name'],
        'url': row['url'],
        'method': row['method'],
        'headers': json.loads(row['headers']) if row['headers'] else {},
        'query_params': query_params_value,
        'body': json.loads(row['body']) if row['body'] else None,
        'description': row['description'] or ''
    }

    business_rules = request.business_rules
    provider = (request.provider or "openai").lower()
    test_cases_data = None
    used_fallback = False

    if provider == "local":
        # Local rule-based engine
        used_fallback = True
        try:
            fallback_result = generate_fallback_tests(api)
            test_cases_data = fallback_result['test_cases']
            logger.info(f"Generated {len(test_cases_data)} test cases using local engine")
        except Exception as e:
            logger.error(f"Local engine failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Local engine failed: {str(e)}")

    elif provider == "gemini":
        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key or gemini_key == 'your-gemini-api-key-here':
            raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured. Please add your Gemini API key to the .env file.")
        try:
            test_cases_data = gemini_generator.generate_test_cases_gemini(api, business_rules)
            logger.info(f"Generated {len(test_cases_data)} test cases using Gemini")
        except Exception as e:
            logger.error(f"Gemini generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Gemini generation failed: {str(e)}")

    else:
        # OpenAI
        openai_key = os.environ.get('OPENAI_API_KEY')
        if not openai_key:
            raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured. Please add it to your .env file.")
        try:
            test_cases_data = openai_generator.generate_test_cases_openai(api, business_rules)
            logger.info(f"Generated {len(test_cases_data)} test cases using OpenAI")
        except Exception as e:
            logger.error(f"OpenAI generation failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"OpenAI generation failed: {str(e)}")
    
    # Save test cases to database (common for both OpenAI and fallback)
    if not test_cases_data:
        raise HTTPException(status_code=500, detail="No test cases generated")
    
    test_cases = []
    try:
        for tc_data in test_cases_data:
            # Handle test_body - convert string to dict if needed
            test_body = tc_data.get('test_body') if isinstance(tc_data, dict) else None
            if isinstance(test_body, str):
                test_body = {"raw_data": test_body}
            
            # Generate assertions if not provided by AI
            assertions = tc_data.get('assertions')
            if not assertions:
                assertions = generate_assertions_for_type(
                    tc_data['type'],
                    tc_data.get('expected_status')
                )
            
            test_case = TestCase(
                api_id=request.api_id,
                type=tc_data['type'],
                name=tc_data['name'],
                description=tc_data['description'],
                test_url=tc_data['test_url'],
                test_method=tc_data['test_method'],
                test_headers=tc_data.get('test_headers', {}),
                query_params=tc_data.get('query_params'),
                test_body=test_body,
                expected_status=tc_data.get('expected_status'),
                assertions=assertions
            )

            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    'INSERT INTO test_cases (id, api_id, type, name, description, test_url, test_method, test_headers, test_body, expected_status, assertions, created_at, query_params) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (test_case.id, test_case.api_id, test_case.type, test_case.name,
                     test_case.description, test_case.test_url, test_case.test_method,
                     json.dumps(test_case.test_headers), json.dumps(test_case.test_body) if test_case.test_body else None,
                     test_case.expected_status, json.dumps(test_case.assertions) if test_case.assertions else None,
                     test_case.created_at.isoformat(),
                     json.dumps(test_case.query_params) if test_case.query_params else None)
                )
                await db.commit()
            
            test_cases.append(test_case)

        return {
            "message": f"Generated {len(test_cases)} test cases" + (" using local engine" if used_fallback else f" using {provider.upper()}"),
            "test_cases": test_cases,
            "used_fallback": used_fallback
        }
    except Exception as save_error:
        logger.error(f"Error saving test cases: {str(save_error)}")
        raise HTTPException(status_code=500, detail=f"Failed to save test cases: {str(save_error)}")


# Update test case
@api_router.put("/testcases/{test_case_id}", response_model=TestCase)
async def update_test_case(test_case_id: str, update_data: TestCaseUpdate):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM test_cases WHERE id = ?', (test_case_id,)) as cursor:
            row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    # Build update query dynamically
    update_fields = []
    params = []
    
    if update_data.name is not None:
        update_fields.append('name = ?')
        params.append(update_data.name)
    if update_data.description is not None:
        update_fields.append('description = ?')
        params.append(update_data.description)
    if update_data.test_url is not None:
        update_fields.append('test_url = ?')
        params.append(update_data.test_url)
    if update_data.test_method is not None:
        update_fields.append('test_method = ?')
        params.append(update_data.test_method)
    if update_data.test_headers is not None:
        update_fields.append('test_headers = ?')
        params.append(json.dumps(update_data.test_headers))
    if update_data.query_params is not None:
        update_fields.append('query_params = ?')
        params.append(json.dumps(update_data.query_params) if update_data.query_params else None)
    if update_data.test_body is not None:
        update_fields.append('test_body = ?')
        params.append(json.dumps(update_data.test_body) if update_data.test_body else None)
    if update_data.expected_status is not None:
        update_fields.append('expected_status = ?')
        params.append(update_data.expected_status)
    if update_data.assertions is not None:
        update_fields.append('assertions = ?')
        params.append(json.dumps(update_data.assertions) if update_data.assertions else None)
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.append(test_case_id)
    query = f"UPDATE test_cases SET {', '.join(update_fields)} WHERE id = ?"
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()
        
        # Fetch updated test case
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM test_cases WHERE id = ?', (test_case_id,)) as cursor:
            updated_row = await cursor.fetchone()
    
    query_params_value = None
    try:
        if 'query_params' in updated_row.keys() and updated_row['query_params']:
            query_params_value = json.loads(updated_row['query_params'])
    except (json.JSONDecodeError, TypeError):
        query_params_value = None
    
    assertions_value = None
    try:
        if 'assertions' in updated_row.keys() and updated_row['assertions']:
            assertions_value = json.loads(updated_row['assertions'])
    except (json.JSONDecodeError, TypeError):
        assertions_value = None
    
    return TestCase(
        id=updated_row['id'],
        api_id=updated_row['api_id'],
        type=updated_row['type'],
        name=updated_row['name'],
        description=updated_row['description'],
        test_url=updated_row['test_url'],
        test_method=updated_row['test_method'],
        test_headers=json.loads(updated_row['test_headers']) if updated_row['test_headers'] else {},
        query_params=query_params_value,
        test_body=json.loads(updated_row['test_body']) if updated_row['test_body'] else None,
        expected_status=updated_row['expected_status'],
        assertions=assertions_value,
        created_at=datetime.fromisoformat(updated_row['created_at'])
    )


# Get test cases for an API
@api_router.get("/apis/{api_id}/testcases", response_model=List[TestCase])
async def get_test_cases(api_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM test_cases WHERE api_id = ?', (api_id,)) as cursor:
            rows = await cursor.fetchall()
    
    test_cases = []
    for row in rows:
        # Safely get query_params with error handling
        query_params_value = None
        try:
            if 'query_params' in row.keys() and row['query_params']:
                query_params_value = json.loads(row['query_params'])
        except (json.JSONDecodeError, TypeError):
            query_params_value = None
        
        # Safely get assertions
        assertions_value = None
        try:
            if 'assertions' in row.keys() and row['assertions']:
                assertions_value = json.loads(row['assertions'])
        except (json.JSONDecodeError, TypeError):
            assertions_value = None
        
        test_cases.append(TestCase(
            id=row['id'],
            api_id=row['api_id'],
            type=row['type'],
            name=row['name'],
            description=row['description'],
            test_url=row['test_url'],
            test_method=row['test_method'],
            test_headers=json.loads(row['test_headers']) if row['test_headers'] else {},
            query_params=query_params_value,
            test_body=json.loads(row['test_body']) if row['test_body'] else None,
            expected_status=row['expected_status'],
            assertions=assertions_value,
            created_at=datetime.fromisoformat(row['created_at'])
        ))
    
    return test_cases


# Run tests
@api_router.post("/run-tests")
async def run_tests(request: RunTestsRequest):
    # Get test cases
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if request.test_case_ids:
            placeholders = ','.join('?' * len(request.test_case_ids))
            query = f'SELECT * FROM test_cases WHERE api_id = ? AND id IN ({placeholders})'
            params = [request.api_id] + request.test_case_ids
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute('SELECT * FROM test_cases WHERE api_id = ?', (request.api_id,)) as cursor:
                rows = await cursor.fetchall()
    
    if not rows:
        raise HTTPException(status_code=404, detail="No test cases found")
    
    test_cases = []
    for row in rows:
        # Safely get query_params with error handling
        query_params_value = None
        try:
            if 'query_params' in row.keys() and row['query_params']:
                query_params_value = json.loads(row['query_params'])
        except (json.JSONDecodeError, TypeError):
            query_params_value = None
        
        # Safely get assertions
        assertions_value = None
        try:
            if 'assertions' in row.keys() and row['assertions']:
                assertions_value = json.loads(row['assertions'])
        except (json.JSONDecodeError, TypeError):
            assertions_value = None
        
        test_cases.append({
            'id': row['id'],
            'type': row['type'],
            'test_url': row['test_url'],
            'test_method': row['test_method'],
            'test_headers': json.loads(row['test_headers']) if row['test_headers'] else {},
            'query_params': query_params_value,
            'test_body': json.loads(row['test_body']) if row['test_body'] else None,
            'expected_status': row['expected_status'],
            'assertions': assertions_value
        })

    results = []

    for tc in test_cases:
        try:
            # Execute the request
            start_time = datetime.now(timezone.utc)

            # Construct URL with query params
            url = tc['test_url']
            if tc.get('query_params'):
                from urllib.parse import urlencode
                query_string = urlencode(tc['query_params'])
                if '?' in url:
                    url += '&' + query_string
                else:
                    url += '?' + query_string

            request_kwargs = {
                'method': tc['test_method'],
                'url': url,
                'headers': tc.get('test_headers', {}),
                'timeout': 10
            }

            if tc.get('test_body'):
                headers = tc.get('test_headers', {})
                content_type = headers.get('Content-Type') or headers.get('content-type', '')
                if 'application/json' in content_type.lower():
                    request_kwargs['json'] = tc['test_body']
                else:
                    request_kwargs['data'] = tc['test_body']

            response = requests.request(**request_kwargs)
            end_time = datetime.now(timezone.utc)
            response_time = (end_time - start_time).total_seconds()

            # Try to parse response as JSON
            try:
                response_body = response.json()
            except:
                response_body = response.text

            # Validate assertions
            failures = []
            if tc.get('assertions'):
                failures = validate_assertions(response, response_time, tc['assertions'])
            
            # Check if test passed (no failures)
            passed = len(failures) == 0

            test_result = TestResult(
                test_case_id=tc['id'],
                api_id=request.api_id,
                type=tc['type'],
                request_url=url,
                request_method=tc['test_method'],
                request_headers=tc.get('test_headers', {}),
                query_params=tc.get('query_params'),
                request_body=tc.get('test_body'),
                response_status=response.status_code,
                response_body=response_body,
                response_headers=dict(response.headers),
                response_time=response_time,
                passed=passed,
                failures=failures if failures else None,
                error=None
            )

        except Exception as e:
            test_result = TestResult(
                test_case_id=tc['id'],
                api_id=request.api_id,
                type=tc['type'],
                request_url=tc['test_url'],
                request_method=tc['test_method'],
                request_headers=tc.get('test_headers', {}),
                query_params=tc.get('query_params'),
                request_body=tc.get('test_body'),
                response_status=None,
                response_body=None,
                response_headers=None,
                response_time=None,
                passed=False,
                failures=[{
                    'assertion_type': 'execution_error',
                    'expected': 'Successful execution',
                    'actual': 'Exception occurred',
                    'message': str(e)
                }],
                error=str(e)
            )

        # Save or update result in database (UPSERT)
        async with aiosqlite.connect(DB_PATH) as db:
            # Check if result exists for this test case
            async with db.execute('SELECT id FROM test_results WHERE test_case_id = ?', (tc['id'],)) as cursor:
                existing = await cursor.fetchone()
            
            if existing:
                # Update existing result
                await db.execute(
                    '''UPDATE test_results SET 
                    type = ?, request_url = ?, request_method = ?, request_headers = ?, 
                    request_body = ?, response_status = ?, response_body = ?, response_headers = ?, 
                    response_time = ?, error = ?, passed = ?, failures = ?, executed_at = ?, query_params = ?
                    WHERE test_case_id = ?''',
                    (test_result.type, test_result.request_url, test_result.request_method,
                     json.dumps(test_result.request_headers), json.dumps(test_result.request_body) if test_result.request_body else None,
                     test_result.response_status, json.dumps(test_result.response_body) if test_result.response_body else None,
                     json.dumps(test_result.response_headers) if test_result.response_headers else None,
                     test_result.response_time, test_result.error, 1 if test_result.passed else 0,
                     json.dumps(test_result.failures) if test_result.failures else None,
                     test_result.executed_at.isoformat(),
                     json.dumps(test_result.query_params) if test_result.query_params else None,
                     tc['id'])
                )
                test_result.id = existing[0]  # Use existing ID
            else:
                # Insert new result
                await db.execute(
                    'INSERT INTO test_results (id, test_case_id, api_id, type, request_url, request_method, request_headers, request_body, response_status, response_body, response_headers, response_time, error, passed, failures, executed_at, query_params) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (test_result.id, test_result.test_case_id, test_result.api_id, test_result.type,
                     test_result.request_url, test_result.request_method,
                     json.dumps(test_result.request_headers), json.dumps(test_result.request_body) if test_result.request_body else None,
                     test_result.response_status, json.dumps(test_result.response_body) if test_result.response_body else None,
                     json.dumps(test_result.response_headers) if test_result.response_headers else None,
                     test_result.response_time, test_result.error, 1 if test_result.passed else 0,
                     json.dumps(test_result.failures) if test_result.failures else None,
                     test_result.executed_at.isoformat(),
                     json.dumps(test_result.query_params) if test_result.query_params else None)
                )
            await db.commit()

        results.append(test_result)

    return {
        "message": f"Executed {len(results)} tests",
        "results": results
    }


# Get test results
@api_router.get("/apis/{api_id}/results", response_model=List[TestResult])
async def get_test_results(api_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM test_results WHERE api_id = ? ORDER BY executed_at DESC', (api_id,)) as cursor:
            rows = await cursor.fetchall()
    
    results = []
    for row in rows:
        # Safely get query_params with error handling
        query_params_value = None
        try:
            if 'query_params' in row.keys() and row['query_params']:
                query_params_value = json.loads(row['query_params'])
        except (json.JSONDecodeError, TypeError):
            query_params_value = None
        
        # Safely get failures
        failures_value = None
        try:
            if 'failures' in row.keys() and row['failures']:
                failures_value = json.loads(row['failures'])
        except (json.JSONDecodeError, TypeError):
            failures_value = None
        
        # Handle type field - check if it exists in the row
        test_type = row['type'] if 'type' in row.keys() else 'positive'
        
        results.append(TestResult(
            id=row['id'],
            test_case_id=row['test_case_id'],
            api_id=row['api_id'],
            type=test_type,
            request_url=row['request_url'],
            request_method=row['request_method'],
            request_headers=json.loads(row['request_headers']) if row['request_headers'] else {},
            query_params=query_params_value,
            request_body=json.loads(row['request_body']) if row['request_body'] else None,
            response_status=row['response_status'],
            response_body=json.loads(row['response_body']) if row['response_body'] and row['response_body'].startswith(('{', '[')) else row['response_body'],
            response_headers=json.loads(row['response_headers']) if row['response_headers'] else None,
            response_time=row['response_time'],
            error=row['error'],
            passed=bool(row['passed']),
            failures=failures_value,
            executed_at=datetime.fromisoformat(row['executed_at'])
        ))
    
    # Sort results by type order: positive, negative, symmetric, security
    type_order = {'positive': 0, 'negative': 1, 'symmetric': 2, 'security': 3}
    results.sort(key=lambda x: (type_order.get(x.type, 999), x.executed_at), reverse=True)
    
    return results


# ============= COLLECTIONS ENDPOINTS =============

# Collection Variables CRUD
@api_router.get("/collections/{collection_id}/variables")
async def get_collection_variables(collection_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM collection_variables WHERE collection_id = ? ORDER BY scope, key',
            (collection_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    
    variables = []
    for row in rows:
        variables.append({
            'id': row['id'],
            'collection_id': row['collection_id'],
            'scope': row['scope'],
            'key': row['key'],
            'value': row['value'],
            'description': row['description'],
            'is_secret': bool(row['is_secret']),
            'enabled': bool(row['enabled']),
            'created_at': row['created_at']
        })
    
    return variables


@api_router.post("/collections/{collection_id}/variables")
async def create_collection_variable(collection_id: str, data: CollectionVariableCreate):
    variable = CollectionVariable(
        collection_id=collection_id,
        scope=data.scope,
        key=data.key,
        value=data.value,
        description=data.description,
        is_secret=data.is_secret,
        enabled=data.enabled
    )
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                '''INSERT INTO collection_variables 
                   (id, collection_id, scope, key, value, description, is_secret, enabled, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (variable.id, variable.collection_id, variable.scope, variable.key, variable.value,
                 variable.description, 1 if variable.is_secret else 0, 1 if variable.enabled else 0,
                 variable.created_at.isoformat())
            )
            await db.commit()
        return variable
    except Exception as e:
        if 'UNIQUE constraint failed' in str(e):
            raise HTTPException(status_code=400, detail=f"Variable '{data.key}' already exists in scope '{data.scope}'")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/collections/{collection_id}/variables/{variable_id}")
async def update_collection_variable(collection_id: str, variable_id: str, data: CollectionVariableUpdate):
    update_fields = []
    params = []
    
    if data.value is not None:
        update_fields.append('value = ?')
        params.append(data.value)
    if data.description is not None:
        update_fields.append('description = ?')
        params.append(data.description)
    if data.is_secret is not None:
        update_fields.append('is_secret = ?')
        params.append(1 if data.is_secret else 0)
    if data.enabled is not None:
        update_fields.append('enabled = ?')
        params.append(1 if data.enabled else 0)
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.extend([variable_id, collection_id])
    query = f"UPDATE collection_variables SET {', '.join(update_fields)} WHERE id = ? AND collection_id = ?"
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, params)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Variable not found")
        await db.commit()
    
    return {"message": "Variable updated successfully"}


@api_router.delete("/collections/{collection_id}/variables/{variable_id}")
async def delete_collection_variable(collection_id: str, variable_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'DELETE FROM collection_variables WHERE id = ? AND collection_id = ?',
            (variable_id, collection_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Variable not found")
        await db.commit()
    
    return {"message": "Variable deleted successfully"}


@api_router.get("/collections/{collection_id}/variables/{variable_id}/usage")
async def get_variable_usage(collection_id: str, variable_id: str):
    """Get usage count of a variable in test cases"""
    # Get the variable
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM collection_variables WHERE id = ? AND collection_id = ?',
            (variable_id, collection_id)
        ) as cursor:
            var_row = await cursor.fetchone()
    
    if not var_row:
        raise HTTPException(status_code=404, detail="Variable not found")
    
    variable = dict(var_row)
    scope = variable['scope']
    key = variable['key']
    
    # Get all APIs in collection
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT a.id FROM collection_apis ca 
               JOIN api_configs a ON ca.api_id = a.id 
               WHERE ca.collection_id = ?''',
            (collection_id,)
        ) as cursor:
            api_rows = await cursor.fetchall()
    
    api_ids = [row['id'] for row in api_rows]
    
    if not api_ids:
        return {"usage_count": 0, "test_cases": []}
    
    # Get all test cases for these APIs
    placeholders = ','.join('?' * len(api_ids))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f'SELECT * FROM test_cases WHERE api_id IN ({placeholders})',
            api_ids
        ) as cursor:
            test_case_rows = await cursor.fetchall()
    
    # Count usage based on scope
    usage_count = 0
    matching_test_cases = []
    
    for tc_row in test_case_rows:
        matched = False
        
        if scope == 'headers':
            headers = json.loads(tc_row['test_headers']) if tc_row['test_headers'] else {}
            if key in headers:
                matched = True
        
        elif scope == 'query_params':
            query_params = json.loads(tc_row['query_params']) if tc_row['query_params'] else {}
            if query_params and key in query_params:
                matched = True
        
        elif scope == 'body':
            body = json.loads(tc_row['test_body']) if tc_row['test_body'] else {}
            if body and isinstance(body, dict) and key in body:
                matched = True
        
        elif scope == 'url':
            # For URL scope, check if test_url has a base URL that can be replaced
            if key in ['baseUrl', 'fullUrl']:
                matched = True  # URL variables apply to all test cases
        
        if matched:
            usage_count += 1
            matching_test_cases.append({
                'id': tc_row['id'],
                'name': tc_row['name'],
                'api_id': tc_row['api_id']
            })
    
    return {
        "usage_count": usage_count,
        "test_cases": matching_test_cases
    }


# Get all collections
@api_router.get("/collections")
async def get_collections():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM collections ORDER BY created_at DESC') as cursor:
            rows = await cursor.fetchall()
    
    collections = []
    for row in rows:
        # Get API count for this collection
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute('SELECT COUNT(*) FROM collection_apis WHERE collection_id = ?', (row['id'],)) as cursor:
                api_count = (await cursor.fetchone())[0]
        
        collections.append({
            "id": row['id'],
            "name": row['name'],
            "description": row['description'],
            "created_at": row['created_at'],
            "api_count": api_count
        })
    
    return collections


# Create collection
@api_router.post("/collections")
async def create_collection(data: CollectionCreate):
    collection = Collection(name=data.name, description=data.description)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'INSERT INTO collections (id, name, description, created_at) VALUES (?, ?, ?, ?)',
            (collection.id, collection.name, collection.description, collection.created_at.isoformat())
        )
        
        # Add APIs to collection
        for idx, api_id in enumerate(data.api_ids):
            await db.execute(
                'INSERT INTO collection_apis (id, collection_id, api_id, order_index) VALUES (?, ?, ?, ?)',
                (str(uuid.uuid4()), collection.id, api_id, idx)
            )
        
        await db.commit()
    
    return collection


# Get collection details
@api_router.get("/collections/{collection_id}")
async def get_collection(collection_id: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM collections WHERE id = ?', (collection_id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Get APIs in collection
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT ca.order_index, a.* 
                   FROM collection_apis ca 
                   JOIN api_configs a ON ca.api_id = a.id 
                   WHERE ca.collection_id = ? 
                   ORDER BY ca.order_index''',
                (collection_id,)
            ) as cursor:
                api_rows = await cursor.fetchall()
        
        apis = []
        for api_row in api_rows:
            # Get test case count for each API
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute('SELECT COUNT(*) FROM test_cases WHERE api_id = ?', (api_row['id'],)) as cursor:
                    test_count = (await cursor.fetchone())[0]
            
            apis.append({
                "id": api_row['id'],
                "name": api_row['name'],
                "url": api_row['url'],
                "method": api_row['method'],
                "description": api_row['description'],
                "test_count": test_count
            })
        
        # Get collection stats
        total_runs = 0
        latest_run = None
        
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            # Total runs
            async with db.execute('SELECT COUNT(*) FROM collection_runs WHERE collection_id = ?', (collection_id,)) as cursor:
                total_runs = (await cursor.fetchone())[0]
            
            # Latest run stats
            async with db.execute(
                'SELECT * FROM collection_runs WHERE collection_id = ? ORDER BY executed_at DESC LIMIT 1',
                (collection_id,)
            ) as cursor:
                latest_row = await cursor.fetchone()
                if latest_row:
                    latest_run = {
                        "total_tests": latest_row['total_tests'],
                        "passed_tests": latest_row['passed_tests'],
                        "failed_tests": latest_row['failed_tests'],
                        "executed_at": latest_row['executed_at']
                    }
        
        return {
            "id": row['id'],
            "name": row['name'],
            "description": row['description'],
            "created_at": row['created_at'],
            "apis": apis,
            "total_runs": total_runs,
            "latest_run": latest_run
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_collection: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


# Delete collection
@api_router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('DELETE FROM collections WHERE id = ?', (collection_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Get all run IDs for this collection
        async with db.execute('SELECT id FROM collection_runs WHERE collection_id = ?', (collection_id,)) as cursor:
            run_ids = [row[0] for row in await cursor.fetchall()]
        
        # Delete collection_run_results for all runs
        if run_ids:
            placeholders = ','.join('?' * len(run_ids))
            await db.execute(f'DELETE FROM collection_run_results WHERE collection_run_id IN ({placeholders})', run_ids)
        
        await db.execute('DELETE FROM collection_apis WHERE collection_id = ?', (collection_id,))
        await db.execute('DELETE FROM collection_runs WHERE collection_id = ?', (collection_id,))
        await db.commit()
    
    return {"message": "Collection deleted successfully"}


# Add API to collection
@api_router.post("/collections/{collection_id}/apis/{api_id}")
async def add_api_to_collection(collection_id: str, api_id: str):
    # Get current max order
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT COALESCE(MAX(order_index), -1) FROM collection_apis WHERE collection_id = ?',
            (collection_id,)
        ) as cursor:
            max_order = (await cursor.fetchone())[0]
        
        await db.execute(
            'INSERT INTO collection_apis (id, collection_id, api_id, order_index) VALUES (?, ?, ?, ?)',
            (str(uuid.uuid4()), collection_id, api_id, max_order + 1)
        )
        await db.commit()
    
    return {"message": "API added to collection"}


# Remove API from collection
@api_router.delete("/collections/{collection_id}/apis/{api_id}")
async def remove_api_from_collection(collection_id: str, api_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'DELETE FROM collection_apis WHERE collection_id = ? AND api_id = ?',
            (collection_id, api_id)
        )
        await db.commit()
    
    return {"message": "API removed from collection"}


# Run collection tests
@api_router.post("/collections/{collection_id}/run")
async def run_collection(collection_id: str):
    start_time = datetime.now(timezone.utc)
    
    # Get collection variables
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM collection_variables WHERE collection_id = ? AND enabled = 1',
            (collection_id,)
        ) as cursor:
            var_rows = await cursor.fetchall()
    
    collection_variables = [{k: row[k] for k in row.keys()} for row in var_rows]
    logger.info(f"Loaded {len(collection_variables)} enabled collection variables")
    
    # Get all APIs in collection
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT a.* FROM collection_apis ca 
               JOIN api_configs a ON ca.api_id = a.id 
               WHERE ca.collection_id = ? 
               ORDER BY ca.order_index''',
            (collection_id,)
        ) as cursor:
            api_rows = await cursor.fetchall()
    
    if not api_rows:
        raise HTTPException(status_code=404, detail="No APIs in collection")
    
    all_results = []
    total_apis = len(api_rows)
    variables_applied_count = 0
    
    # Run tests for each API with variables applied
    for api_row in api_rows:
        api_id = api_row['id']
        try:
            # Get test cases for this API
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('SELECT * FROM test_cases WHERE api_id = ?', (api_id,)) as cursor:
                    test_case_rows = await cursor.fetchall()
            
            if not test_case_rows:
                logger.warning(f"No test cases found for API {api_id}")
                continue
            
            # Process each test case
            for tc_row in test_case_rows:
                try:
                    # Parse test case data
                    test_url = tc_row['test_url']
                    test_method = tc_row['test_method']
                    test_headers = json.loads(tc_row['test_headers']) if tc_row['test_headers'] else {}
                    test_body = json.loads(tc_row['test_body']) if tc_row['test_body'] else None
                    query_params = json.loads(tc_row['query_params']) if tc_row['query_params'] else None
                    expected_status = tc_row['expected_status']
                    assertions = json.loads(tc_row['assertions']) if ('assertions' in tc_row.keys() and tc_row['assertions']) else None
                    
                    # Apply collection variables if any
                    if collection_variables:
                        test_config = {
                            'url': test_url,
                            'method': test_method,
                            'headers': test_headers,
                            'query_params': query_params,
                            'body': test_body
                        }
                        
                        resolved_config, replacements = apply_collection_variables(test_config, collection_variables)
                        
                        if replacements:
                            logger.info(f"Applied {len(replacements)} variables to test case {tc_row['id']}")
                            variables_applied_count += len(replacements)
                            
                            # Use resolved values
                            test_url = resolved_config['url']
                            test_headers = resolved_config['headers']
                            query_params = resolved_config['query_params']
                            test_body = resolved_config['body']
                    
                    # Execute the test
                    start_test_time = datetime.now(timezone.utc)
                    
                    # Construct URL with query params
                    url = test_url
                    if query_params:
                        from urllib.parse import urlencode
                        query_string = urlencode(query_params)
                        if '?' in url:
                            url += '&' + query_string
                        else:
                            url += '?' + query_string
                    
                    request_kwargs = {
                        'method': test_method,
                        'url': url,
                        'headers': test_headers,
                        'timeout': 10
                    }
                    
                    if test_body:
                        content_type = test_headers.get('Content-Type') or test_headers.get('content-type', '')
                        if 'application/json' in content_type.lower():
                            request_kwargs['json'] = test_body
                        else:
                            request_kwargs['data'] = test_body
                    
                    response = requests.request(**request_kwargs)
                    end_test_time = datetime.now(timezone.utc)
                    response_time = (end_test_time - start_test_time).total_seconds()
                    
                    # Parse response
                    try:
                        response_body = response.json()
                    except:
                        response_body = response.text
                    
                    # Validate assertions
                    failures = []
                    if assertions:
                        failures = validate_assertions(response, response_time, assertions)
                    
                    # Check if test passed
                    passed = len(failures) == 0
                    
                    test_result = TestResult(
                        test_case_id=tc_row['id'],
                        api_id=api_id,
                        type=tc_row['type'],
                        request_url=url,
                        request_method=test_method,
                        request_headers=test_headers,
                        query_params=query_params,
                        request_body=test_body,
                        response_status=response.status_code,
                        response_body=response_body,
                        response_headers=dict(response.headers),
                        response_time=response_time,
                        passed=passed,
                        failures=failures if failures else None,
                        error=None
                    )
                    
                except Exception as e:
                    test_result = TestResult(
                        test_case_id=tc_row['id'],
                        api_id=api_id,
                        type=tc_row['type'],
                        request_url=test_url,
                        request_method=test_method,
                        request_headers=test_headers,
                        query_params=query_params,
                        request_body=test_body,
                        response_status=None,
                        response_body=None,
                        response_headers=None,
                        response_time=None,
                        passed=False,
                        failures=[{
                            'assertion_type': 'execution_error',
                            'expected': 'Successful execution',
                            'actual': 'Exception occurred',
                            'message': str(e)
                        }],
                        error=str(e)
                    )
                
                # Save result
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute('SELECT id FROM test_results WHERE test_case_id = ?', (tc_row['id'],)) as cursor:
                        existing = await cursor.fetchone()
                    
                    if existing:
                        await db.execute(
                            '''UPDATE test_results SET 
                            type = ?, request_url = ?, request_method = ?, request_headers = ?, 
                            request_body = ?, response_status = ?, response_body = ?, response_headers = ?, 
                            response_time = ?, error = ?, passed = ?, failures = ?, executed_at = ?, query_params = ?
                            WHERE test_case_id = ?''',
                            (test_result.type, test_result.request_url, test_result.request_method,
                             json.dumps(test_result.request_headers), json.dumps(test_result.request_body) if test_result.request_body else None,
                             test_result.response_status, json.dumps(test_result.response_body) if test_result.response_body else None,
                             json.dumps(test_result.response_headers) if test_result.response_headers else None,
                             test_result.response_time, test_result.error, 1 if test_result.passed else 0,
                             json.dumps(test_result.failures) if test_result.failures else None,
                             test_result.executed_at.isoformat(),
                             json.dumps(test_result.query_params) if test_result.query_params else None,
                             tc_row['id'])
                        )
                        test_result.id = existing[0]
                    else:
                        await db.execute(
                            'INSERT INTO test_results (id, test_case_id, api_id, type, request_url, request_method, request_headers, request_body, response_status, response_body, response_headers, response_time, error, passed, failures, executed_at, query_params) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            (test_result.id, test_result.test_case_id, test_result.api_id, test_result.type,
                             test_result.request_url, test_result.request_method,
                             json.dumps(test_result.request_headers), json.dumps(test_result.request_body) if test_result.request_body else None,
                             test_result.response_status, json.dumps(test_result.response_body) if test_result.response_body else None,
                             json.dumps(test_result.response_headers) if test_result.response_headers else None,
                             test_result.response_time, test_result.error, 1 if test_result.passed else 0,
                             json.dumps(test_result.failures) if test_result.failures else None,
                             test_result.executed_at.isoformat(),
                             json.dumps(test_result.query_params) if test_result.query_params else None)
                        )
                    await db.commit()
                
                all_results.append(test_result)
                
        except Exception as e:
            logger.error(f"Error running tests for API {api_id}: {str(e)}")
    
    end_time = datetime.now(timezone.utc)
    total_time = (end_time - start_time).total_seconds()
    
    # Calculate stats
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r.passed)
    failed_tests = total_tests - passed_tests
    
    logger.info(f"Collection run complete: {total_tests} tests, {passed_tests} passed, {failed_tests} failed")
    logger.info(f"Total variable replacements applied: {variables_applied_count}")
    
    # Save collection run
    run_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''INSERT INTO collection_runs 
               (id, collection_id, executed_at, total_apis, total_tests, passed_tests, failed_tests, total_time) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (run_id, collection_id, end_time.isoformat(), total_apis, total_tests, passed_tests, failed_tests, total_time)
        )
        
        # Save individual test results for this collection run
        for result in all_results:
            await db.execute(
                '''INSERT INTO collection_run_results 
                   (id, collection_run_id, test_result_id, api_id, test_case_id, passed) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (str(uuid.uuid4()), run_id, result.id, result.api_id, result.test_case_id, 1 if result.passed else 0)
            )
        
        await db.commit()
    
    return {
        "run_id": run_id,
        "collection_id": collection_id,
        "total_apis": total_apis,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "total_time": total_time,
        "variables_applied": len(collection_variables),
        "total_replacements": variables_applied_count,
        "results": all_results
    }


# Get collection run history
@api_router.get("/collections/{collection_id}/runs")
async def get_collection_runs(collection_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM collection_runs WHERE collection_id = ? ORDER BY executed_at DESC LIMIT 10',
            (collection_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    
    return [{
        "id": row['id'],
        "executed_at": row['executed_at'],
        "total_apis": row['total_apis'],
        "total_tests": row['total_tests'],
        "passed_tests": row['passed_tests'],
        "failed_tests": row['failed_tests'],
        "total_time": row['total_time']
    } for row in rows]


# Download HTML report for API tests
@api_router.get("/apis/{api_id}/report/download")
async def download_api_report(api_id: str):
    """Generate and download HTML report for API test results"""
    # Get API details
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM api_configs WHERE id = ?', (api_id,)) as cursor:
            api_row = await cursor.fetchone()
    
    if not api_row:
        raise HTTPException(status_code=404, detail="API not found")
    
    # Get test results
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT tr.*, tc.name as test_name, tc.type, tc.description as test_description, tc.assertions as test_assertions
               FROM test_results tr
               JOIN test_cases tc ON tr.test_case_id = tc.id
               WHERE tr.api_id = ?
               ORDER BY tc.type, tr.executed_at DESC''',
            (api_id,)
        ) as cursor:
            result_rows = await cursor.fetchall()
    
    if not result_rows:
        raise HTTPException(status_code=404, detail="No test results found. Please run tests first.")
    
    # Parse results
    results = []
    total_time = 0
    for row in result_rows:
        # Safely get query_params
        query_params_value = None
        try:
            if 'query_params' in row.keys() and row['query_params']:
                query_params_value = json.loads(row['query_params'])
        except (json.JSONDecodeError, TypeError):
            query_params_value = None
        
        # Safely get failures
        failures_value = None
        try:
            if 'failures' in row.keys() and row['failures']:
                failures_value = json.loads(row['failures'])
        except (json.JSONDecodeError, TypeError):
            failures_value = None
        
        # Safely get assertions
        assertions_value = None
        try:
            if 'assertions' in row.keys() and row['assertions']:
                assertions_value = json.loads(row['assertions'])
        except (json.JSONDecodeError, TypeError):
            assertions_value = None
        
        # Safely get assertions from test case
        assertions_value = None
        try:
            if 'test_assertions' in row.keys() and row['test_assertions']:
                assertions_value = json.loads(row['test_assertions'])
        except (json.JSONDecodeError, TypeError):
            assertions_value = None
        
        result_data = {
            'test_name': row['test_name'],
            'type': row['type'],
            'test_description': row['test_description'],
            'passed': bool(row['passed']),
            'request_url': row['request_url'],
            'request_method': row['request_method'],
            'request_headers': json.loads(row['request_headers']) if row['request_headers'] else {},
            'request_body': json.loads(row['request_body']) if row['request_body'] else None,
            'query_params': query_params_value,
            'response_status': row['response_status'],
            'response_body': json.loads(row['response_body']) if row['response_body'] and row['response_body'].startswith(('{', '[')) else row['response_body'],
            'response_headers': json.loads(row['response_headers']) if row['response_headers'] else {},
            'response_time': row['response_time'] or 0,
            'error': row['error'],
            'failures': failures_value,
            'assertions': assertions_value
        }
        results.append(result_data)
        total_time += result_data['response_time']
    
    # Generate report
    report_data = {
        'title': f"API Test Report: {api_row['name']}",
        'subtitle': f"{api_row['method']} {api_row['url']}",
        'results': results,
        'total_time': total_time
    }
    
    html_content = generate_html_report(report_data, report_type="api")
    
    return HTMLResponse(
        content=html_content,
        headers={
            'Content-Disposition': f'attachment; filename="api_test_report_{api_row["name"].replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html"'
        }
    )


# Download HTML report for collection tests
@api_router.get("/collections/{collection_id}/report/download")
async def download_collection_report(collection_id: str):
    """Generate and download HTML report for collection test results"""
    # Get collection details
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM collections WHERE id = ?', (collection_id,)) as cursor:
            collection_row = await cursor.fetchone()
    
    if not collection_row:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    # Get latest run
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM collection_runs WHERE collection_id = ? ORDER BY executed_at DESC LIMIT 1',
            (collection_id,)
        ) as cursor:
            run_row = await cursor.fetchone()
    
    if not run_row:
        raise HTTPException(status_code=404, detail="No test runs found. Please run collection tests first.")
    
    # Get all test results for this run
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT crr.*, tr.*, tc.name as test_name, tc.type, 
                      tc.description as test_description, tc.assertions as test_assertions, a.name as api_name
               FROM collection_run_results crr
               JOIN test_results tr ON crr.test_result_id = tr.id
               JOIN test_cases tc ON crr.test_case_id = tc.id
               JOIN api_configs a ON crr.api_id = a.id
               WHERE crr.collection_run_id = ?
               ORDER BY a.name, tc.type''',
            (run_row['id'],)
        ) as cursor:
            result_rows = await cursor.fetchall()
    
    # Parse results
    results = []
    for row in result_rows:
        # Safely get query_params
        query_params_value = None
        try:
            if 'query_params' in row.keys() and row['query_params']:
                query_params_value = json.loads(row['query_params'])
        except (json.JSONDecodeError, TypeError):
            query_params_value = None
        
        # Safely get failures
        failures_value = None
        try:
            if 'failures' in row.keys() and row['failures']:
                failures_value = json.loads(row['failures'])
        except (json.JSONDecodeError, TypeError):
            failures_value = None
        
        # Safely get assertions
        assertions_value = None
        try:
            if 'assertions' in row.keys() and row['assertions']:
                assertions_value = json.loads(row['assertions'])
        except (json.JSONDecodeError, TypeError):
            assertions_value = None
        
        # Safely get assertions from test case
        assertions_value = None
        try:
            if 'test_assertions' in row.keys() and row['test_assertions']:
                assertions_value = json.loads(row['test_assertions'])
        except (json.JSONDecodeError, TypeError):
            assertions_value = None
        
        result_data = {
            'test_name': f"{row['api_name']} - {row['test_name']}",
            'type': row['type'],
            'test_description': row['test_description'],
            'passed': bool(row['passed']),
            'request_url': row['request_url'],
            'request_method': row['request_method'],
            'request_headers': json.loads(row['request_headers']) if row['request_headers'] else {},
            'request_body': json.loads(row['request_body']) if row['request_body'] else None,
            'query_params': query_params_value,
            'response_status': row['response_status'],
            'response_body': json.loads(row['response_body']) if row['response_body'] and row['response_body'].startswith(('{', '[')) else row['response_body'],
            'response_headers': json.loads(row['response_headers']) if row['response_headers'] else {},
            'response_time': row['response_time'] or 0,
            'error': row['error'],
            'failures': failures_value,
            'assertions': assertions_value
        }
        results.append(result_data)
    
    # Generate report
    report_data = {
        'title': f"Collection Test Report: {collection_row['name']}",
        'subtitle': f"{run_row['total_apis']} APIs, {run_row['total_tests']} Tests",
        'results': results,
        'total_time': run_row['total_time']
    }
    
    html_content = generate_html_report(report_data, report_type="collection")
    
    return HTMLResponse(
        content=html_content,
        headers={
            'Content-Disposition': f'attachment; filename="collection_report_{collection_row["name"].replace(" ", "_")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html"'
        }
    )


# Get detailed results for a specific collection run
@api_router.get("/collections/{collection_id}/runs/{run_id}")
async def get_collection_run_details(collection_id: str, run_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Get run summary
        async with db.execute('SELECT * FROM collection_runs WHERE id = ?', (run_id,)) as cursor:
            run_row = await cursor.fetchone()
        
        if not run_row:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Get all test results for this run with full details
        async with db.execute(
            '''SELECT crr.*, tr.id as tr_id, tr.test_case_id, tr.api_id as tr_api_id, tr.type as tr_type,
                      tr.request_url, tr.request_method, tr.request_headers, tr.request_body,
                      tr.response_status, tr.response_body, tr.response_headers, tr.response_time,
                      tr.error, tr.passed, tr.failures, tr.executed_at, tr.query_params,
                      tc.name as test_name, tc.type as test_type, 
                      tc.description as test_description, a.name as api_name
               FROM collection_run_results crr
               JOIN test_results tr ON crr.test_result_id = tr.id
               JOIN test_cases tc ON crr.test_case_id = tc.id
               JOIN api_configs a ON crr.api_id = a.id
               WHERE crr.collection_run_id = ?
               ORDER BY a.name, tc.type''',
            (run_id,)
        ) as cursor:
            result_rows = await cursor.fetchall()
        
        results = []
        for row in result_rows:
            # Parse JSON fields
            request_headers = json.loads(row['request_headers']) if row['request_headers'] else {}
            request_body = json.loads(row['request_body']) if row['request_body'] else None
            response_headers = json.loads(row['response_headers']) if row['response_headers'] else None
            
            # Safely get query_params
            query_params = None
            try:
                if 'query_params' in row.keys() and row['query_params']:
                    query_params = json.loads(row['query_params'])
            except (json.JSONDecodeError, TypeError):
                query_params = None
            
            # Parse response body
            response_body = None
            try:
                if 'response_body' in row.keys() and row['response_body']:
                    if isinstance(row['response_body'], str) and row['response_body'].startswith(('{', '[')):
                        response_body = json.loads(row['response_body'])
                    else:
                        response_body = row['response_body']
            except (json.JSONDecodeError, TypeError):
                response_body = None
            
            # Safely get failures
            failures = None
            try:
                if 'failures' in row.keys() and row['failures']:
                    failures = json.loads(row['failures'])
            except (json.JSONDecodeError, TypeError):
                failures = None
            
            results.append({
                "test_name": row['test_name'],
                "test_type": row['test_type'],
                "test_description": row['test_description'],
                "api_name": row['api_name'],
                "passed": bool(row['passed']),
                "request_url": row['request_url'],
                "request_method": row['request_method'],
                "request_headers": request_headers,
                "request_body": request_body,
                "query_params": query_params,
                "response_status": row['response_status'],
                "response_body": response_body,
                "response_headers": response_headers,
                "response_time": row['response_time'],
                "error": row['error'],
                "failures": failures
            })
        
        return {
            "id": run_row['id'],
            "executed_at": run_row['executed_at'],
            "total_apis": run_row['total_apis'],
            "total_tests": run_row['total_tests'],
            "passed_tests": run_row['passed_tests'],
            "failed_tests": run_row['failed_tests'],
            "total_time": run_row['total_time'],
            "results": results
        }


# ============= CONTRACT TESTING ENDPOINTS =============

# Upload swagger file
@api_router.post("/contract-tests/upload")
async def upload_swagger(name: str, base_url: str = "", file: UploadFile = File(...)):
    try:
        # Read file content
        content = await file.read()
        swagger_json = json.loads(content.decode('utf-8'))
        
        # Parse swagger
        parsed_info = swagger_parser.parse_swagger_file(swagger_json)
        
        # Use provided base_url or extracted one
        final_base_url = base_url or parsed_info['base_url']
        
        # Create contract test record
        contract_id = str(uuid.uuid4())
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                '''INSERT INTO contract_tests 
                   (id, name, swagger_json, base_url, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (contract_id, name, json.dumps(swagger_json), final_base_url, 
                 'uploaded', datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
            )
            await db.commit()
        
        return {
            "id": contract_id,
            "name": name,
            "base_url": final_base_url,
            "version": parsed_info['version'],
            "message": "Swagger file uploaded successfully"
        }
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        logger.error(f"Error uploading swagger: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Parse swagger and extract endpoints
@api_router.post("/contract-tests/{contract_id}/parse")
async def parse_swagger(contract_id: str):
    try:
        # Get contract test
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM contract_tests WHERE id = ?', (contract_id,)) as cursor:
                row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Contract test not found")
        
        swagger_json = json.loads(row['swagger_json'])
        
        # Extract endpoints
        endpoints = swagger_parser.extract_endpoints(swagger_json)
        
        # Save endpoints to database
        async with aiosqlite.connect(DB_PATH) as db:
            for endpoint in endpoints:
                endpoint_id = str(uuid.uuid4())
                await db.execute(
                    '''INSERT INTO contract_test_endpoints
                       (id, contract_test_id, endpoint_path, http_method, request_schema, 
                        response_schema, auth_required, parameters, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        endpoint_id,
                        contract_id,
                        endpoint['path'],
                        endpoint['method'],
                        json.dumps(endpoint.get('request_schema')),
                        json.dumps(endpoint.get('response_schemas')),
                        1 if endpoint['auth_required'] else 0,
                        json.dumps(endpoint.get('parameters')),
                        datetime.now(timezone.utc).isoformat()
                    )
                )
            
            # Update contract test status
            await db.execute(
                'UPDATE contract_tests SET status = ?, updated_at = ? WHERE id = ?',
                ('parsed', datetime.now(timezone.utc).isoformat(), contract_id)
            )
            await db.commit()
        
        return {
            "message": f"Parsed {len(endpoints)} endpoints",
            "endpoints_count": len(endpoints),
            "endpoints": endpoints
        }
    
    except Exception as e:
        logger.error(f"Error parsing swagger: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Generate test cases using AI
@api_router.post("/contract-tests/{contract_id}/generate-requests")
async def generate_contract_requests(contract_id: str):
    try:
        # Get contract test for base URL
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT base_url FROM contract_tests WHERE id = ?', (contract_id,)) as cursor:
                contract_row = await cursor.fetchone()
        
        if not contract_row:
            raise HTTPException(status_code=404, detail="Contract test not found")
        
        base_url = contract_row['base_url']
        
        # Get all endpoints
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM contract_test_endpoints WHERE contract_test_id = ?',
                (contract_id,)
            ) as cursor:
                endpoints = await cursor.fetchall()
        
        if not endpoints:
            raise HTTPException(status_code=404, detail="No endpoints found. Please parse swagger first.")
        
        total_test_cases = 0
        
        # Generate test cases for each endpoint
        async with aiosqlite.connect(DB_PATH) as db:
            for endpoint in endpoints:
                endpoint_data = {
                    'path': endpoint['endpoint_path'],
                    'method': endpoint['http_method'],
                    'summary': endpoint['endpoint_path'],  # Use path as summary
                    'request_schema': json.loads(endpoint['request_schema']) if endpoint['request_schema'] else None,
                    'response_schemas': json.loads(endpoint['response_schema']) if endpoint['response_schema'] else {},
                    'parameters': json.loads(endpoint['parameters']) if endpoint['parameters'] else {}
                }
                
                # Generate scenarios
                try:
                    scenarios = contract_ai_generator.generate_multiple_scenarios(endpoint_data)
                except Exception as e:
                    logger.warning(f"Failed to generate scenarios for {endpoint['endpoint_path']}: {str(e)}")
                    scenarios = []
                
                # Save test cases with base URL
                for scenario in scenarios:
                    test_case_id = str(uuid.uuid4())
                    
                    # Add base URL to request
                    request_with_base = scenario['request'].copy()
                    request_with_base['base_url'] = base_url
                    
                    # Get expected response schema for status code
                    expected_status = scenario.get('expected_status', 200)
                    logger.info(f"Test case {test_case_id}: expected_status from scenario = {expected_status}")
                    response_schemas = endpoint_data.get('response_schemas', {})
                    expected_schema = response_schemas.get(str(expected_status), {}).get('schema', {})
                    
                    await db.execute(
                        '''INSERT INTO contract_test_cases
                           (id, contract_test_id, endpoint_id, test_name, generated_request, 
                            expected_response_schema, expected_status, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            test_case_id,
                            contract_id,
                            endpoint['id'],
                            scenario['name'],
                            json.dumps(request_with_base),
                            json.dumps(expected_schema),
                            expected_status,
                            'generated',
                            datetime.now(timezone.utc).isoformat()
                        )
                    )
                    total_test_cases += 1
            
            # Update contract test status
            await db.execute(
                'UPDATE contract_tests SET status = ?, updated_at = ? WHERE id = ?',
                ('generated', datetime.now(timezone.utc).isoformat(), contract_id)
            )
            await db.commit()
        
        return {
            "message": f"Generated {total_test_cases} test cases",
            "total_test_cases": total_test_cases
        }
    
    except Exception as e:
        logger.error(f"Error generating requests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Execute all tests
@api_router.post("/contract-tests/{contract_id}/execute")
async def execute_contract_tests(contract_id: str):
    try:
        # Get contract test
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM contract_tests WHERE id = ?', (contract_id,)) as cursor:
                contract = await cursor.fetchone()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract test not found")
        
        base_url = contract['base_url']
        auth_config = json.loads(contract['auth_config']) if contract['auth_config'] else None
        
        # Get all test cases with endpoint info
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT tc.*, e.endpoint_path, e.http_method 
                   FROM contract_test_cases tc
                   JOIN contract_test_endpoints e ON tc.endpoint_id = e.id
                   WHERE tc.contract_test_id = ?''',
                (contract_id,)
            ) as cursor:
                test_cases = await cursor.fetchall()
        
        if not test_cases:
            raise HTTPException(status_code=404, detail="No test cases found. Please generate requests first.")
        
        # Prepare test cases for execution
        test_cases_list = []
        for tc in test_cases:
            request_data = json.loads(tc['generated_request'])
            expected_schema = json.loads(tc['expected_response_schema']) if tc['expected_response_schema'] else None
            
            test_cases_list.append({
                'id': tc['id'],
                'test_name': tc['test_name'],
                'endpoint_path': tc['endpoint_path'],
                'method': tc['http_method'],
                'path_params': request_data.get('path_params', {}),
                'query_params': request_data.get('query_params', {}),
                'headers': request_data.get('headers', {}),
                'body': request_data.get('body'),
                'expected_response_schema': expected_schema,
                'expected_status': tc['expected_status'] if 'expected_status' in tc.keys() and tc['expected_status'] else 200
            })
        
        # Execute tests
        async with aiosqlite.connect(DB_PATH) as db:
            results = await contract_test_executor.execute_all_tests(
                contract_id, test_cases_list, base_url, auth_config, db
            )
        
        # Update contract test status
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                'UPDATE contract_tests SET status = ?, updated_at = ? WHERE id = ?',
                ('completed', datetime.now(timezone.utc).isoformat(), contract_id)
            )
            await db.commit()
        
        return results
    
    except Exception as e:
        logger.error(f"Error executing tests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get test results
@api_router.get("/contract-tests/{contract_id}/results")
async def get_contract_results(contract_id: str):
    try:
        # Get contract test
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM contract_tests WHERE id = ?', (contract_id,)) as cursor:
                contract = await cursor.fetchone()
        
        if not contract:
            raise HTTPException(status_code=404, detail="Contract test not found")
        
        # Get all results with request data and expected status from test cases
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT r.*, tc.test_name, tc.generated_request, tc.expected_status, e.endpoint_path, e.http_method
                   FROM contract_test_results r
                   JOIN contract_test_cases tc ON r.contract_test_case_id = tc.id
                   JOIN contract_test_endpoints e ON tc.endpoint_id = e.id
                   WHERE tc.contract_test_id = ?
                   ORDER BY r.executed_at DESC''',
                (contract_id,)
            ) as cursor:
                results = await cursor.fetchall()
        
        # Calculate summary
        total = len(results)
        passed = sum(1 for r in results if r['schema_validation_result'] == 'pass' and r['actual_status_code'] == r['expected_status'])
        failed = total - passed
        
        results_list = []
        for r in results:
            # Parse generated request
            generated_req = json.loads(r['generated_request']) if r['generated_request'] else {}
            
            results_list.append({
                'test_name': r['test_name'],
                'endpoint': f"{r['http_method']} {r['endpoint_path']}",
                'actual_status': r['actual_status_code'],
                'expected_status': r['expected_status'],
                'schema_validation': r['schema_validation_result'],
                'response_time': r['response_time'],
                'error': r['error_message'],
                'executed_at': r['executed_at'],
                'request_url': r['request_url'] if 'request_url' in r.keys() else None,
                'request_method': r['request_method'] if 'request_method' in r.keys() else r['http_method'],
                'request_body': json.loads(r['request_body']) if ('request_body' in r.keys() and r['request_body']) else generated_req.get('body'),
                'response_body': json.loads(r['response_body']) if r['response_body'] else None
            })
        
        return {
            'summary': {
                'total': total,
                'passed': passed,
                'failed': failed,
                'success_rate': round((passed / total * 100) if total > 0 else 0, 2)
            },
            'results': results_list
        }
    
    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Get all contract tests
@api_router.get("/contract-tests")
async def get_contract_tests():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM contract_tests ORDER BY created_at DESC') as cursor:
            rows = await cursor.fetchall()
    
    tests = []
    for row in rows:
        # Get endpoint count
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                'SELECT COUNT(*) FROM contract_test_endpoints WHERE contract_test_id = ?',
                (row['id'],)
            ) as cursor:
                endpoint_count = (await cursor.fetchone())[0]
        
        tests.append({
            'id': row['id'],
            'name': row['name'],
            'base_url': row['base_url'],
            'status': row['status'],
            'endpoint_count': endpoint_count,
            'created_at': row['created_at']
        })
    
    return tests

# Get endpoints for a contract test
@api_router.get("/contract-tests/{contract_id}/endpoints")
async def get_contract_endpoints(contract_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM contract_test_endpoints WHERE contract_test_id = ?',
            (contract_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    
    endpoints = []
    for row in rows:
        endpoints.append({
            'id': row['id'],
            'endpoint_path': row['endpoint_path'],
            'http_method': row['http_method'],
            'request_schema': json.loads(row['request_schema']) if row['request_schema'] else None,
            'response_schema': json.loads(row['response_schema']) if row['response_schema'] else None,
            'auth_required': bool(row['auth_required']),
            'parameters': json.loads(row['parameters']) if row['parameters'] else None
        })
    
    return endpoints

# Get test cases for a contract test
@api_router.get("/contract-tests/{contract_id}/test-cases")
async def get_contract_test_cases(contract_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''SELECT tc.*, e.endpoint_path, e.http_method
               FROM contract_test_cases tc
               JOIN contract_test_endpoints e ON tc.endpoint_id = e.id
               WHERE tc.contract_test_id = ?
               ORDER BY e.endpoint_path, tc.test_name''',
            (contract_id,)
        ) as cursor:
            rows = await cursor.fetchall()
    
    test_cases = []
    for row in rows:
        test_cases.append({
            'id': row['id'],
            'test_name': row['test_name'],
            'endpoint_path': row['endpoint_path'],
            'http_method': row['http_method'],
            'generated_request': json.loads(row['generated_request']) if row['generated_request'] else None,
            'expected_response_schema': json.loads(row['expected_response_schema']) if row['expected_response_schema'] else None,
            'expected_status': row['expected_status'] if 'expected_status' in row.keys() else 200,
            'status': row['status']
        })
    
    return test_cases

# Delete contract test
@api_router.delete("/contract-tests/{contract_id}")
async def delete_contract_test(contract_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        # Enable foreign keys for this connection
        await db.execute('PRAGMA foreign_keys = ON')
        
        # Manually delete related records in correct order
        # First delete results (references test_cases)
        await db.execute(
            '''DELETE FROM contract_test_results 
               WHERE contract_test_case_id IN 
               (SELECT id FROM contract_test_cases WHERE contract_test_id = ?)''',
            (contract_id,)
        )
        
        # Then delete test cases (references endpoints)
        await db.execute(
            'DELETE FROM contract_test_cases WHERE contract_test_id = ?',
            (contract_id,)
        )
        
        # Then delete endpoints (references contract_tests)
        await db.execute(
            'DELETE FROM contract_test_endpoints WHERE contract_test_id = ?',
            (contract_id,)
        )
        
        # Finally delete the contract test
        cursor = await db.execute('DELETE FROM contract_tests WHERE id = ?', (contract_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contract test not found")
        
        await db.commit()
    
    return {"message": "Contract test deleted successfully"}


# JSON to Schema endpoint
class JSONToSchemaRequest(BaseModel):
    json_data: Dict[str, Any]

@api_router.post("/json-to-schema")
async def json_to_schema(request: JSONToSchemaRequest):
    """Convert JSON to JSON Schema using genson"""
    try:
        builder = SchemaBuilder()
        builder.add_object(request.json_data)
        schema = builder.to_schema()
        return {"schema": schema}
    except Exception as e:
        logger.error(f"Error converting JSON to schema: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


class JSONToSchemaAIRequest(BaseModel):
    json_data: Dict[str, Any]
    provider: Optional[str] = "openai"
    empty_response: Optional[str] = None
    data_response: Optional[str] = None
    requirements: Optional[str] = None


SCHEMA_SYSTEM_PROMPT = """
You are a JSON Schema expert. Generate a single unified JSON Schema that handles ALL provided response scenarios.

Rules:
- Use "anyOf" or "oneOf" at the top level if responses have different structures
- Mark fields as optional (remove from "required") if they don't appear in all scenarios
- Use nullable types (e.g., ["string", "null"]) for fields that can be null
- The schema must validate ALL provided example responses
- Return ONLY valid JSON Schema (draft-07), no explanation, no markdown
"""


@api_router.post("/json-to-schema-ai")
async def json_to_schema_ai(request: JSONToSchemaAIRequest):
    """Convert JSON to JSON Schema using AI with multi-scenario support"""
    # Build user prompt
    parts = [f"Primary JSON response:\n{json.dumps(request.json_data, indent=2)}"]
    if request.empty_response and request.empty_response.strip():
        parts.append(f"Empty/no-records response scenario:\n{request.empty_response.strip()}")
    if request.data_response and request.data_response.strip():
        parts.append(f"Data-present response scenario:\n{request.data_response.strip()}")
    if request.requirements and request.requirements.strip():
        parts.append(f"Additional requirements:\n{request.requirements.strip()}")
    user_prompt = "\n\n".join(parts) + "\n\nGenerate a single unified JSON Schema."

    provider = (request.provider or "openai").lower()

    try:
        if provider == "local":
            # Fallback: use genson on all provided JSONs
            builder = SchemaBuilder()
            builder.add_object(request.json_data)
            for scenario in [request.empty_response, request.data_response]:
                if scenario and scenario.strip():
                    try:
                        builder.add_object(json.loads(scenario))
                    except Exception:
                        pass
            schema = builder.to_schema()
            return {"schema": schema}

        elif provider == "gemini":
            gemini_key = os.environ.get('GEMINI_API_KEY')
            if not gemini_key:
                raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            try:
                all_models = [m.name for m in client.models.list()
                              if 'generateContent' in (m.supported_actions or [])]
                flash_models = [m for m in all_models if 'flash' in m.lower() and 'embed' not in m.lower()]
                models_to_try = flash_models if flash_models else all_models
            except Exception:
                models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash']
            content = None
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"{SCHEMA_SYSTEM_PROMPT}\n{user_prompt}"
                    )
                    content = response.text.strip()
                    break
                except Exception as e:
                    logger.warning(f"Gemini model {model_name} failed: {str(e)[:120]}")
            if content is None:
                raise HTTPException(status_code=500, detail="All Gemini models failed")
        else:
            openai_key = os.environ.get('OPENAI_API_KEY')
            if not openai_key:
                raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
            client = OpenAI(api_key=openai_key)
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SCHEMA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
            content = completion.choices[0].message.content.strip()

        # Strip markdown fences if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        schema = json.loads(content.strip())
        return {"schema": schema}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in AI schema generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Generate test cases from JSON Schema
class SchemaTestCasesRequest(BaseModel):
    schema: Dict[str, Any]
    provider: Optional[str] = "openai"
    business_rules: Optional[str] = None


SCHEMA_TESTCASE_PROMPT = """
You are an API testing expert. Given a JSON Schema, generate test cases.
Return ONLY a valid JSON array. Each item must have:
- name: string
- type: "positive" | "negative" | "security"
- description: string
- expected_status: integer
- assertions: object with keys: expected_status (int), response_not_empty (bool, optional), content_type (string, optional)

Generate at least 5 test cases covering: valid data, empty response, missing fields, wrong types, unauthorized access.
"""


@api_router.post("/generate-schema-testcases")
async def generate_schema_testcases(request: SchemaTestCasesRequest):
    """Generate test cases from a JSON Schema using AI"""
    user_prompt = f"JSON Schema:\n{json.dumps(request.schema, indent=2)}"
    if request.business_rules:
        user_prompt += f"\n\nBusiness Rules:\n{request.business_rules}"
    user_prompt += "\n\nGenerate test cases as a JSON array."

    provider = (request.provider or "openai").lower()

    try:
        if provider == "gemini":
            gemini_key = os.environ.get('GEMINI_API_KEY')
            if not gemini_key:
                raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            try:
                all_models = [m.name for m in client.models.list()
                              if 'generateContent' in (m.supported_actions or [])]
                flash_models = [m for m in all_models if 'flash' in m.lower() and 'embed' not in m.lower()]
                models_to_try = flash_models if flash_models else all_models
            except Exception:
                models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash']
            content = None
            for model_name in models_to_try:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"{SCHEMA_TESTCASE_PROMPT}\n{user_prompt}"
                    )
                    content = response.text.strip()
                    break
                except Exception as e:
                    logger.warning(f"Gemini model {model_name} failed: {str(e)[:120]}")
            if content is None:
                raise HTTPException(status_code=500, detail="All Gemini models failed")
        else:
            openai_key = os.environ.get('OPENAI_API_KEY')
            if not openai_key:
                raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
            client = OpenAI(api_key=openai_key)
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SCHEMA_TESTCASE_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
            content = completion.choices[0].message.content.strip()

        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        test_cases = json.loads(content.strip())
        return {"test_cases": test_cases}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating schema test cases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Response Validation endpoint
class ResponseValidationRequest(BaseModel):
    contract_json: Dict[str, Any]
    response_json: Dict[str, Any]
    provider: Optional[str] = "openai"

VALIDATION_SYSTEM_PROMPT = """
    You are a Senior API Contract Testing Architect. Validate Response against Contract using this comprehensive checklist:
    
    ### VALIDATION CHECKLIST (Execute in Order):
    
    1. ROOT-LEVEL PARAMETERS:
       - Check all root-level fields in contract exist in response
       - Check all root-level fields in response exist in contract
    
    2. REQUIRED PARAMETERS:
       - Report if contract field is missing in response: "Field '[field]' is present in contract but not present in response"
       - Report if response has extra field: "Field '[field]' is present in response but not in contract"
    
    3. FIELD NAME VALIDATION:
       - Check exact field name matches (case-sensitive)
       - Report case mismatches: "Field '[field]' case mismatch: contract has '[ContractName]' but response has '[ResponseName]'"
    
    4. DATA TYPE VALIDATION:
       - JSON has only these types: string, number, boolean, array, object, null
       - In JSON, integers and floats are BOTH "number" type (99 and 1.0 are both numbers)
       - ONLY report if types are DIFFERENT (e.g., number vs string, boolean vs number, string vs array)
       - DO NOT report if both are numbers (even if one is integer and one is float)
       - DO NOT report if both are same type with different values
       - Example of VALID report: "Field 'age' type mismatch: contract has number but response has string"
       - Example of INVALID report: Contract has 99, response has 1.0 - both are numbers, DO NOT report
       - Example of INVALID report: Both are boolean - DO NOT report
       - Example of INVALID report: Both are string - DO NOT report
    
    5. FORMAT VALIDATION:
       - Check string formats (date, email, URL, UUID) if contract specifies format
       - Report format issues: "Field '[field]' format mismatch: contract expects [format] but response has invalid format"
    
    6. CONSTRAINT VALIDATION:
       - Check value constraints (min/max length, min/max value, patterns)
       - Report constraint violations if contract defines them
    
    7. ENUM VALIDATION:
       - If contract defines enum values, check response value is in allowed list
       - Report: "Field '[field]' value '[value]' not in contract enum [allowed values]"
    
    8. NULLABILITY VALIDATION:
       - ONLY report if one is null and the other is NOT null
       - Report if contract has non-null value but response has null: "Field '[field]' is null in response but contract expects value"
       - Report if contract has null but response has non-null value: "Field '[field]' has value in response but contract expects null"
       - DO NOT report if both are null
       - DO NOT report if both have values (even if values are different)
    
    9. NESTED OBJECT VALIDATION:
       - Recursively validate all nested objects using dot notation (e.g., 'data.header')
       - Apply all validation rules to nested fields
    
    10. ARRAY ITEM VALIDATION:
        - Check array structure matches
        - Validate array item types and nested properties
        - Check array length constraints if defined
    
    11. CONDITIONAL VALIDATION:
        - If contract defines conditional rules (if field X exists, then field Y required), validate them
        - Report conditional violations if defined
    
    ### OUTPUT REQUIREMENTS:
    - NO INTRODUCTORY TEXT
    - If 100% valid: Return ONLY "congratulations your contract and response contact verified"
    - If NOT valid: Return JSON with explicit discrepancies
    
    ### JSON STRUCTURE FOR ERRORS:
    {
        "is_valid": false,
        "discrepancies": [
            "Field 'status' is present in contract but not present in response",
            "Field 'success' is present in response but not in contract"
        ]
    }
    
    CRITICAL: Check BOTH directions - contract→response AND response→contract
    """


def _parse_validation_content(content: str) -> dict:
    if "congratulations" in content.lower() and "verified" in content.lower():
        return {"is_valid": True, "message": content}
    try:
        return json.loads(content)
    except:
        return {"is_valid": False, "discrepancies": [content]}


@api_router.post("/validate-response")
async def validate_response(request: ResponseValidationRequest):
    """Validate API response against contract using OpenAI or Gemini"""
    user_prompt = f"""
    CONTRACT:
    {json.dumps(request.contract_json, indent=2)}

    RESPONSE:
    {json.dumps(request.response_json, indent=2)}
    """

    provider = (request.provider or "openai").lower()

    try:
        if provider == "gemini":
            gemini_key = os.environ.get('GEMINI_API_KEY')
            if not gemini_key:
                raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
            from google import genai as google_genai
            client = google_genai.Client(api_key=gemini_key)
            # Discover available models dynamically
            try:
                all_models = [m.name for m in client.models.list()
                              if 'generateContent' in (m.supported_actions or [])]
                # Prefer flash models, filter out vision/embedding/etc
                flash_models = [m for m in all_models if 'flash' in m.lower() and 'embed' not in m.lower()]
                models_to_try = flash_models if flash_models else all_models
                logger.info(f"Available Gemini models: {models_to_try}")
            except Exception:
                models_to_try = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-2.5-flash']
            last_error = None
            content = None
            for model_name in models_to_try:
                try:
                    logger.info(f"Trying Gemini model for validation: {model_name}")
                    response = client.models.generate_content(
                        model=model_name,
                        contents=f"{VALIDATION_SYSTEM_PROMPT}\n{user_prompt}"
                    )
                    content = response.text.strip()
                    logger.info(f"Gemini validation succeeded with model: {model_name}")
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(f"Gemini model {model_name} failed: {str(e)[:120]}")
                    continue
            if content is None:
                raise Exception(f"All Gemini models failed. Last error: {last_error}")
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return _parse_validation_content(content.strip())
        else:
            openai_key = os.environ.get('OPENAI_API_KEY')
            if not openai_key:
                raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
            client = OpenAI(api_key=openai_key)
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
            content = completion.choices[0].message.content.strip()
            return _parse_validation_content(content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating response: {str(e)}")
        return {"is_valid": False, "discrepancies": [f"Architectural Analysis Error: {str(e)}"]}



# Include the router in the main app
app.include_router(api_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API Testing Platform is running"}

@app.on_event("startup")
async def startup_db():
    logger.info("Starting up the application...")
    await init_db()
    logger.info("Database initialized successfully")

if __name__ == "__main__":
    logger.info("Starting server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
