"""
HTML Report Generator for API Test Results
Generates world-class HTML reports with charts, detailed results, and cURL commands
"""

import json
from datetime import datetime
from typing import List, Dict, Any
import html


def generate_curl_command(test_data: Dict[str, Any]) -> str:
    """Generate cURL command from test data"""
    method = test_data.get('request_method', 'GET')
    url = test_data.get('request_url', '')
    headers = test_data.get('request_headers', {})
    body = test_data.get('request_body')
    
    curl_parts = [f"curl -X {method}"]
    
    # Add headers
    for key, value in headers.items():
        curl_parts.append(f"-H '{key}: {value}'")
    
    # Add body
    if body:
        body_str = json.dumps(body) if isinstance(body, dict) else str(body)
        body_str = body_str.replace("'", "\\'")
        curl_parts.append(f"-d '{body_str}'")
    
    curl_parts.append(f"'{url}'")
    
    return " \\\n  ".join(curl_parts)


def generate_failures_html(failures: List[Dict[str, Any]]) -> str:
    """Generate HTML for assertion failures"""
    if not failures:
        return ''
    
    html_parts = ['<h6>Assertion Failures:</h6>']
    html_parts.append('<div class="alert alert-danger" style="font-size: 0.8rem;">')
    
    for failure in failures:
        assertion_type = html.escape(failure.get('assertion_type', 'Unknown'))
        message = html.escape(failure.get('message', ''))
        expected = html.escape(str(failure.get('expected', '')))
        actual = html.escape(str(failure.get('actual', '')))
        
        html_parts.append(f'<div class="mb-2" style="border-left: 3px solid #dc3545; padding-left: 10px;">')
        html_parts.append(f'<strong>❌ {assertion_type}</strong><br>')
        html_parts.append(f'<small>{message}</small><br>')
        html_parts.append(f'<small><strong>Expected:</strong> {expected} | <strong>Actual:</strong> {actual}</small>')
        html_parts.append('</div>')
    
    html_parts.append('</div>')
    return ''.join(html_parts)


def generate_assertions_html(assertions: Dict[str, Any], passed: bool) -> str:
    """Generate HTML for assertions (passed or failed)"""
    if not assertions:
        return ''
    
    html_parts = ['<h6>Assertions:</h6>']
    html_parts.append(f'<div class="alert alert-{"success" if passed else "info"}" style="font-size: 0.8rem;">')
    
    if assertions.get('expected_status'):
        html_parts.append(f'<div>✓ Status Code: {assertions["expected_status"]}</div>')
    
    if assertions.get('max_response_time'):
        html_parts.append(f'<div>✓ Response Time: &lt; {assertions["max_response_time"]}s</div>')
    
    if assertions.get('content_type'):
        html_parts.append(f'<div>✓ Content-Type: {html.escape(assertions["content_type"])}</div>')
    
    if assertions.get('response_not_empty'):
        html_parts.append('<div>✓ Response Not Empty</div>')
    
    if assertions.get('response_schema', {}).get('required_fields'):
        fields = ', '.join(assertions['response_schema']['required_fields'])
        html_parts.append(f'<div>✓ Required Fields: {html.escape(fields)}</div>')
    
    html_parts.append('</div>')
    return ''.join(html_parts)


def generate_assertions_tab_html(assertions: Dict[str, Any], failures: List[Dict[str, Any]], passed: bool) -> str:
    """Generate HTML for Assertions tab with pass/fail indicators"""
    if not assertions and not failures:
        return '<div class="alert alert-secondary" style="font-size: 0.8rem;">No assertions configured</div>'
    
    html_parts = []
    
    # Show assertions with pass/fail indicators
    if assertions:
        html_parts.append('<h6>Assertions Checked:</h6>')
        html_parts.append('<div class="alert alert-info" style="font-size: 0.8rem;">')
        
        # Create a set of failed assertion types for quick lookup
        failed_types = {f.get('assertion_type') for f in (failures or [])}
        
        if assertions.get('expected_status'):
            icon = '❌' if 'status_code' in failed_types else '✓'
            color = 'red' if 'status_code' in failed_types else 'green'
            html_parts.append(f'<div style="color: {color};">{icon} Status Code: {assertions["expected_status"]}</div>')
        
        if assertions.get('max_response_time'):
            icon = '❌' if 'response_time' in failed_types else '✓'
            color = 'red' if 'response_time' in failed_types else 'green'
            html_parts.append(f'<div style="color: {color};">{icon} Response Time: &lt; {assertions["max_response_time"]}s</div>')
        
        if assertions.get('content_type'):
            icon = '❌' if 'content_type' in failed_types else '✓'
            color = 'red' if 'content_type' in failed_types else 'green'
            html_parts.append(f'<div style="color: {color};">{icon} Content-Type: {html.escape(assertions["content_type"])}</div>')
        
        if assertions.get('response_not_empty'):
            icon = '❌' if 'response_not_empty' in failed_types else '✓'
            color = 'red' if 'response_not_empty' in failed_types else 'green'
            html_parts.append(f'<div style="color: {color};">{icon} Response Not Empty</div>')
        
        if assertions.get('response_schema', {}).get('required_fields'):
            icon = '❌' if 'required_field' in failed_types else '✓'
            color = 'red' if 'required_field' in failed_types else 'green'
            fields = ', '.join(assertions['response_schema']['required_fields'])
            html_parts.append(f'<div style="color: {color};">{icon} Required Fields: {html.escape(fields)}</div>')
        
        html_parts.append('</div>')
    
    # Show detailed failures
    if failures:
        html_parts.append('<h6 style="margin-top: 15px;">Assertion Failures:</h6>')
        html_parts.append('<div class="alert alert-danger" style="font-size: 0.8rem;">')
        
        for failure in failures:
            assertion_type = html.escape(failure.get('assertion_type', 'Unknown'))
            message = html.escape(failure.get('message', ''))
            expected = html.escape(str(failure.get('expected', '')))
            actual = html.escape(str(failure.get('actual', '')))
            
            html_parts.append(f'<div class="mb-2" style="border-left: 3px solid #dc3545; padding-left: 10px;">')
            html_parts.append(f'<strong>❌ {assertion_type}</strong><br>')
            html_parts.append(f'<small>{message}</small><br>')
            html_parts.append(f'<small><strong>Expected:</strong> {expected} | <strong>Actual:</strong> {actual}</small>')
            html_parts.append('</div>')
        
        html_parts.append('</div>')
    
    return ''.join(html_parts)


def generate_html_report(
    report_data: Dict[str, Any],
    report_type: str = "api"
) -> str:
    """Generate comprehensive HTML report"""
    
    results = report_data.get('results', [])
    
    # Sort results by type order: positive, negative, symmetric, security
    type_order = {'positive': 0, 'negative': 1, 'symmetric': 2, 'security': 3}
    results = sorted(results, key=lambda x: type_order.get(x.get('type', 'unknown'), 999))
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.get('passed'))
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    total_time = report_data.get('total_time', 0)
    
    # Calculate stats by type
    type_stats = {}
    for result in results:
        test_type = result.get('type', 'unknown')
        if test_type not in type_stats:
            type_stats[test_type] = {'total': 0, 'passed': 0, 'failed': 0}
        type_stats[test_type]['total'] += 1
        if result.get('passed'):
            type_stats[test_type]['passed'] += 1
        else:
            type_stats[test_type]['failed'] += 1
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Test Report - {report_data.get('title', 'Test Results')}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/components/prism-json.min.js"></script>
    <style>
        :root {{
            --primary: #0d6efd;
            --success: #198754;
            --danger: #dc3545;
            --warning: #ffc107;
            --info: #0dcaf0;
            --dark: #212529;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f8f9fa;
            padding: 15px;
            font-size: 13px;
        }}
        .report-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }}
        .report-header h1 {{
            font-size: 1.75rem;
            margin-bottom: 8px;
        }}
        .report-header p {{
            font-size: 0.85rem;
            margin-bottom: 4px;
        }}
        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        }}
        .stat-card h4, .stat-card h5 {{
            font-size: 1rem;
            margin-bottom: 10px;
        }}
        .stat-number {{
            font-size: 2rem;
            font-weight: bold;
            margin: 8px 0;
        }}
        .stat-card .text-muted {{
            font-size: 0.8rem;
        }}
        .progress-custom {{
            height: 24px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .test-card {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 12px;
            border-left: 4px solid;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
            font-size: 13px;
        }}
        .test-card.passed {{
            border-left-color: var(--success);
        }}
        .test-card.failed {{
            border-left-color: var(--danger);
        }}
        .test-card h5 {{
            font-size: 0.95rem;
            margin-bottom: 6px;
        }}
        .test-card h6 {{
            font-size: 0.85rem;
            margin-bottom: 6px;
        }}
        .test-card p {{
            font-size: 0.8rem;
            margin-bottom: 6px;
        }}
        .badge-type {{
            font-size: 0.7rem;
            padding: 4px 10px;
            border-radius: 12px;
        }}
        .code-block {{
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 10px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 0.75rem;
            margin: 8px 0;
            line-height: 1.4;
        }}
        .curl-command {{
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 12px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 0.7rem;
            overflow-x: auto;
            position: relative;
            line-height: 1.5;
        }}
        .copy-btn {{
            position: absolute;
            top: 8px;
            right: 8px;
            padding: 4px 8px;
            font-size: 0.7rem;
        }}
        .collapsible {{
            cursor: pointer;
            user-select: none;
            font-size: 0.8rem;
        }}
        .collapsible:hover {{
            background: #f8f9fa;
        }}
        .chart-container {{
            position: relative;
            height: 250px;
            margin: 15px 0;
        }}
        .status-badge {{
            font-size: 1rem;
            padding: 8px 16px;
        }}
        .metric-icon {{
            font-size: 2rem;
            opacity: 0.3;
        }}
        .search-box {{
            margin: 15px 0;
        }}
        .search-box input, .search-box select {{
            font-size: 0.85rem;
            padding: 8px 12px;
        }}
        .nav-tabs .nav-link {{
            font-size: 0.8rem;
            padding: 8px 12px;
        }}
        .tab-content {{
            font-size: 0.8rem;
        }}
        @media print {{
            .no-print {{
                display: none;
            }}
            .test-card {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container-fluid">
        <!-- Header -->
        <div class="report-header">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h1><i class="bi bi-clipboard-data"></i> {report_data.get('title', 'API Test Report')}</h1>
                    <p class="mb-0"><i class="bi bi-calendar"></i> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    {f'<p class="mb-0"><i class="bi bi-folder"></i> {report_data.get("subtitle", "")}</p>' if report_data.get('subtitle') else ''}
                </div>
                <div class="col-md-4 text-end">
                    <span class="status-badge badge bg-{'success' if success_rate >= 80 else 'warning' if success_rate >= 50 else 'danger'}">
                        {'PASSED' if success_rate >= 80 else 'PARTIAL' if success_rate >= 50 else 'FAILED'}
                    </span>
                </div>
            </div>
        </div>

        <!-- Summary Stats -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="stat-card text-center">
                    <i class="bi bi-list-check metric-icon text-primary"></i>
                    <div class="stat-number text-primary">{total_tests}</div>
                    <div class="text-muted">Total Tests</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card text-center">
                    <i class="bi bi-check-circle metric-icon text-success"></i>
                    <div class="stat-number text-success">{passed_tests}</div>
                    <div class="text-muted">Passed</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card text-center">
                    <i class="bi bi-x-circle metric-icon text-danger"></i>
                    <div class="stat-number text-danger">{failed_tests}</div>
                    <div class="text-muted">Failed</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card text-center">
                    <i class="bi bi-clock metric-icon text-info"></i>
                    <div class="stat-number text-info">{total_time:.2f}s</div>
                    <div class="text-muted">Total Time</div>
                </div>
            </div>
        </div>

        <!-- Success Rate -->
        <div class="stat-card mb-4">
            <h5 class="mb-3"><i class="bi bi-graph-up"></i> Success Rate</h5>
            <div class="progress progress-custom">
                <div class="progress-bar bg-{'success' if success_rate >= 80 else 'warning' if success_rate >= 50 else 'danger'}" 
                     style="width: {success_rate}%">
                    {success_rate:.1f}%
                </div>
            </div>
        </div>

        <!-- Charts -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="stat-card">
                    <h5 class="mb-3"><i class="bi bi-pie-chart"></i> Test Distribution</h5>
                    <div class="chart-container">
                        <canvas id="distributionChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="stat-card">
                    <h5 class="mb-3"><i class="bi bi-bar-chart"></i> Results by Type</h5>
                    <div class="chart-container">
                        <canvas id="resultsChart"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- Search and Filter -->
        <div class="stat-card search-box no-print">
            <div class="row">
                <div class="col-md-6">
                    <input type="text" id="searchInput" class="form-control" placeholder="🔍 Search tests...">
                </div>
                <div class="col-md-3">
                    <select id="typeFilter" class="form-select">
                        <option value="">All Types</option>
                        <option value="positive">Positive</option>
                        <option value="negative">Negative</option>
                        <option value="symmetric">Symmetric</option>
                        <option value="security">Security</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <select id="statusFilter" class="form-select">
                        <option value="">All Status</option>
                        <option value="passed">Passed</option>
                        <option value="failed">Failed</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Test Results -->
        <div class="stat-card">
            <h4 class="mb-4"><i class="bi bi-clipboard-check"></i> Detailed Test Results</h4>
            <div id="testResults">
"""

    # Generate test result cards
    for idx, result in enumerate(results):
        test_name = result.get('test_name', result.get('name', f'Test {idx + 1}'))
        test_type = result.get('type', 'unknown')
        test_desc = result.get('test_description', result.get('description', ''))
        passed = result.get('passed', False)
        
        type_colors = {
            'positive': 'success',
            'negative': 'warning',
            'symmetric': 'info',
            'security': 'danger'
        }
        type_color = type_colors.get(test_type, 'secondary')
        
        status_icon = '✓' if passed else '✗'
        status_class = 'passed' if passed else 'failed'
        
        request_method = result.get('request_method', 'GET')
        request_url = result.get('request_url', '')
        response_status = result.get('response_status', 'N/A')
        response_time = result.get('response_time', 0)
        error = result.get('error')
        
        # Generate cURL command
        curl_cmd = generate_curl_command(result)
        curl_id = f"curl_{idx}"
        
        html_content += f"""
                <div class="test-card {status_class}" data-type="{test_type}" data-status="{'passed' if passed else 'failed'}">
                    <div class="row align-items-center">
                        <div class="col-md-8">
                            <h5>
                                <span class="badge bg-{'success' if passed else 'danger'} me-2">{status_icon}</span>
                                {html.escape(test_name)}
                                <span class="badge badge-type bg-{type_color} ms-2">{test_type.upper()}</span>
                            </h5>
                            <p class="text-muted mb-2">{html.escape(test_desc)}</p>
                            <div>
                                <span class="badge bg-primary">{request_method}</span>
                                <code class="ms-2">{html.escape(request_url)}</code>
                            </div>
                        </div>
                        <div class="col-md-4 text-end">
                            <div class="mb-2">
                                <span class="badge bg-{'success' if response_status and 200 <= response_status < 300 else 'danger' if response_status else 'secondary'}">
                                    Status: {response_status}
                                </span>
                            </div>
                            <div>
                                <i class="bi bi-clock"></i> {response_time:.3f}s
                            </div>
                        </div>
                    </div>
                    
                    <!-- Collapsible Details -->
                    <div class="mt-3">
                        <button class="btn btn-sm btn-outline-primary collapsible" data-bs-toggle="collapse" data-bs-target="#details_{idx}">
                            <i class="bi bi-chevron-down"></i> View Details
                        </button>
                        <div id="details_{idx}" class="collapse mt-3">
                            <ul class="nav nav-tabs" role="tablist">
                                <li class="nav-item">
                                    <a class="nav-link active" data-bs-toggle="tab" href="#request_{idx}">Request</a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" data-bs-toggle="tab" href="#response_{idx}">Response</a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" data-bs-toggle="tab" href="#curl_{idx}">cURL</a>
                                </li>
                                <li class="nav-item">
                                    <a class="nav-link" data-bs-toggle="tab" href="#assertions_{idx}">Assertions</a>
                                </li>
                            </ul>
                            <div class="tab-content p-3 border border-top-0">
                                <!-- Request Tab -->
                                <div id="request_{idx}" class="tab-pane fade show active">
                                    <h6>Headers:</h6>
                                    <pre class="code-block"><code class="language-json">{json.dumps(result.get('request_headers', {}), indent=2)}</code></pre>
                                    {f'<h6>Query Parameters:</h6><pre class="code-block"><code class="language-json">{json.dumps(result.get("query_params", {}), indent=2)}</code></pre>' if result.get('query_params') else ''}
                                    {f'<h6>Body:</h6><pre class="code-block"><code class="language-json">{json.dumps(result.get("request_body", {}), indent=2)}</code></pre>' if result.get('request_body') else ''}
                                </div>
                                
                                <!-- Response Tab -->
                                <div id="response_{idx}" class="tab-pane fade">
                                    <h6>Status: <span class="badge bg-{'success' if response_status and 200 <= response_status < 300 else 'danger'}">{response_status}</span></h6>
                                    <h6>Response Time: {response_time:.3f}s</h6>
                                    {f'<h6>Error:</h6><div class="alert alert-danger">{html.escape(error)}</div>' if error else ''}
                                    <h6>Headers:</h6>
                                    <pre class="code-block"><code class="language-json">{json.dumps(result.get('response_headers', {}), indent=2)}</code></pre>
                                    <h6>Body:</h6>
                                    <pre class="code-block"><code class="language-json">{json.dumps(result.get('response_body', {}), indent=2) if result.get('response_body') else 'No response body'}</code></pre>
                                </div>
                                
                                <!-- cURL Tab -->
                                <div id="{curl_id}" class="tab-pane fade">
                                    <div class="curl-command">
                                        <button class="btn btn-sm btn-light copy-btn" onclick="copyCurl('{curl_id}_code')">
                                            <i class="bi bi-clipboard"></i> Copy
                                        </button>
                                        <pre id="{curl_id}_code" style="margin: 0;">{html.escape(curl_cmd)}</pre>
                                    </div>
                                </div>
                                
                                <!-- Assertions Tab -->
                                <div id="assertions_{idx}" class="tab-pane fade">
                                    {generate_assertions_tab_html(result.get('assertions', {}), result.get('failures'), passed)}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
"""

    # Close HTML and add scripts
    html_content += f"""
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Chart Data
        const typeStats = {json.dumps(type_stats)};
        
        // Distribution Chart
        const distributionCtx = document.getElementById('distributionChart').getContext('2d');
        new Chart(distributionCtx, {{
            type: 'pie',
            data: {{
                labels: Object.keys(typeStats).map(k => k.toUpperCase()),
                datasets: [{{
                    data: Object.values(typeStats).map(v => v.total),
                    backgroundColor: ['#198754', '#ffc107', '#0dcaf0', '#dc3545']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
        
        // Results Chart
        const resultsCtx = document.getElementById('resultsChart').getContext('2d');
        new Chart(resultsCtx, {{
            type: 'bar',
            data: {{
                labels: Object.keys(typeStats).map(k => k.toUpperCase()),
                datasets: [
                    {{
                        label: 'Passed',
                        data: Object.values(typeStats).map(v => v.passed),
                        backgroundColor: '#198754'
                    }},
                    {{
                        label: 'Failed',
                        data: Object.values(typeStats).map(v => v.failed),
                        backgroundColor: '#dc3545'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
        
        // Copy cURL function
        function copyCurl(elementId) {{
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text).then(() => {{
                alert('cURL command copied to clipboard!');
            }});
        }}
        
        // Search and Filter
        const searchInput = document.getElementById('searchInput');
        const typeFilter = document.getElementById('typeFilter');
        const statusFilter = document.getElementById('statusFilter');
        
        function filterTests() {{
            const searchTerm = searchInput.value.toLowerCase();
            const typeValue = typeFilter.value;
            const statusValue = statusFilter.value;
            
            document.querySelectorAll('.test-card').forEach(card => {{
                const text = card.textContent.toLowerCase();
                const type = card.dataset.type;
                const status = card.dataset.status;
                
                const matchSearch = text.includes(searchTerm);
                const matchType = !typeValue || type === typeValue;
                const matchStatus = !statusValue || status === statusValue;
                
                card.style.display = (matchSearch && matchType && matchStatus) ? 'block' : 'none';
            }});
        }}
        
        searchInput.addEventListener('input', filterTests);
        typeFilter.addEventListener('change', filterTests);
        statusFilter.addEventListener('change', filterTests);
    </script>
</body>
</html>
"""
    
    return html_content
