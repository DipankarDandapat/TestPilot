import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../components/ui/accordion';
import { Upload, FileJson, Play, CheckCircle, XCircle, Loader2, Trash2, Eye, Code, List, ArrowLeft } from 'lucide-react';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export default function ContractTesting() {
  const navigate = useNavigate();
  const [contractTests, setContractTests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState(null);
  const [testName, setTestName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const [selectedTestId, setSelectedTestId] = useState(null);
  const [endpoints, setEndpoints] = useState([]);
  const [testCases, setTestCases] = useState([]);

  useEffect(() => {
    fetchContractTests();
  }, []);

  const fetchContractTests = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests`);
      const data = await response.json();
      setContractTests(data);
    } catch (err) {
      console.error('Error fetching contract tests:', err);
    }
  };

  const fetchEndpoints = async (contractId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests/${contractId}/endpoints`);
      const data = await response.json();
      setEndpoints(data);
    } catch (err) {
      console.error('Error fetching endpoints:', err);
    }
  };

  const fetchTestCases = async (contractId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests/${contractId}/test-cases`);
      const data = await response.json();
      setTestCases(data);
    } catch (err) {
      console.error('Error fetching test cases:', err);
    }
  };

  const handleViewDetails = async (test) => {
    setSelectedTestId(test.id);
    setEndpoints([]);
    setTestCases([]);
    setResults(null);
    
    if (test.status === 'parsed' || test.status === 'generated' || test.status === 'completed') {
      await fetchEndpoints(test.id);
    }
    if (test.status === 'generated' || test.status === 'completed') {
      await fetchTestCases(test.id);
    }
    if (test.status === 'completed') {
      await fetchResults(test.id);
    }
  };

  const fetchResults = async (contractId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests/${contractId}/results`);
      const data = await response.json();
      setResults(data);
    } catch (err) {
      console.error('Error fetching results:', err);
    }
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file && file.type === 'application/json') {
      setSelectedFile(file);
      setError('');
    } else {
      setError('Please select a valid JSON file');
      setSelectedFile(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !testName) {
      setError('Please provide test name and select a file');
      return;
    }

    setLoading(true);
    setError('');
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch(
        `${API_BASE_URL}/contract-tests/upload?name=${encodeURIComponent(testName)}&base_url=${encodeURIComponent(baseUrl)}`,
        {
          method: 'POST',
          body: formData
        }
      );

      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      setUploadProgress(50);
      
      // Auto-parse after upload
      await handleParse(data.id);
      
      setSelectedFile(null);
      setTestName('');
      setBaseUrl('');
      setUploadProgress(100);
      fetchContractTests();
      
      // Auto-select the uploaded test
      setTimeout(() => handleViewDetails({ id: data.id, status: 'parsed' }), 500);
    } catch (err) {
      setError('Failed to upload swagger file: ' + err.message);
    } finally {
      setLoading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  };

  const handleParse = async (contractId) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests/${contractId}/parse`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Parse failed');

      const data = await response.json();
      fetchContractTests();
      return data;
    } catch (err) {
      setError('Failed to parse swagger: ' + err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateRequests = async (contractId) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests/${contractId}/generate-requests`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Generation failed');

      const data = await response.json();
      alert(`✅ Generated ${data.total_test_cases} test cases successfully!`);
      fetchContractTests();
      await fetchTestCases(contractId);
    } catch (err) {
      setError('Failed to generate requests: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async (contractId) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/contract-tests/${contractId}/execute`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Execution failed');

      // Fetch detailed results
      await fetchResults(contractId);
      fetchContractTests();
    } catch (err) {
      setError('Failed to execute tests: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (contractId) => {
    if (!window.confirm('Are you sure you want to delete this contract test? This will also delete all related endpoints, test cases, and results.')) return;

    try {
      await fetch(`${API_BASE_URL}/contract-tests/${contractId}`, {
        method: 'DELETE'
      });
      fetchContractTests();
      if (selectedTestId === contractId) {
        setSelectedTestId(null);
        setEndpoints([]);
        setTestCases([]);
        setResults(null);
      }
    } catch (err) {
      setError('Failed to delete contract test: ' + err.message);
    }
  };

  const getStatusBadge = (status) => {
    const variants = {
      uploaded: 'secondary',
      parsed: 'default',
      generated: 'default',
      completed: 'default',
      pending: 'outline'
    };

    return <Badge variant={variants[status] || 'outline'}>{status}</Badge>;
  };

  const getMethodColor = (method) => {
    const colors = {
      GET: 'bg-green-100 text-green-700',
      POST: 'bg-blue-100 text-blue-700',
      PUT: 'bg-yellow-100 text-yellow-700',
      PATCH: 'bg-purple-100 text-purple-700',
      DELETE: 'bg-red-100 text-red-700'
    };
    return colors[method] || 'bg-gray-100 text-gray-700';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl space-y-6">
        <div className="mb-6">
          <Button
            variant="outline"
            onClick={() => navigate('/')}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>

          <div className="text-center mb-6">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-2">
              Contract Testing
            </h1>
            <p className="text-slate-600">Swagger-based API testing automation</p>
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Upload Section */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="w-5 h-5" />
              Upload Swagger File
            </CardTitle>
            <CardDescription>
              Upload your Swagger/OpenAPI JSON file to automatically generate and execute tests
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="testName">Test Suite Name *</Label>
                <Input
                  id="testName"
                  placeholder="e.g., User API Tests"
                  value={testName}
                  onChange={(e) => setTestName(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="baseUrl">Base URL (optional)</Label>
                <Input
                  id="baseUrl"
                  placeholder="e.g., https://api.example.com"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="swaggerFile">Swagger JSON File *</Label>
              <Input
                id="swaggerFile"
                type="file"
                accept=".json"
                onChange={handleFileSelect}
              />
              {selectedFile && (
                <p className="text-sm text-green-600 mt-1 flex items-center gap-1">
                  <FileJson className="w-4 h-4" />
                  {selectedFile.name}
                </p>
              )}
            </div>

            {uploadProgress > 0 && (
              <Progress value={uploadProgress} className="w-full" />
            )}

            <Button
              onClick={handleUpload}
              disabled={!selectedFile || !testName || loading}
              className="w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Upload & Parse Swagger
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Contract Tests List */}
        <Card>
          <CardHeader>
            <CardTitle>Contract Tests</CardTitle>
            <CardDescription>Manage your swagger-based contract tests</CardDescription>
          </CardHeader>
          <CardContent>
            {contractTests.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FileJson className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No contract tests yet. Upload a swagger file to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {contractTests.map((test) => (
                  <div
                    key={test.id}
                    className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold">{test.name}</h3>
                          {getStatusBadge(test.status)}
                        </div>
                        <p className="text-sm text-gray-600">{test.base_url}</p>
                        <p className="text-xs text-gray-500 mt-1">
                          {test.endpoint_count} endpoints • Created {new Date(test.created_at).toLocaleDateString()}
                        </p>
                      </div>

                      <div className="flex gap-2">
                        {(test.status === 'parsed' || test.status === 'generated' || test.status === 'completed') && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleViewDetails(test)}
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            View
                          </Button>
                        )}

                        {test.status === 'parsed' && (
                          <Button
                            size="sm"
                            onClick={() => handleGenerateRequests(test.id)}
                            disabled={loading}
                          >
                            Generate Tests
                          </Button>
                        )}

                        {(test.status === 'generated' || test.status === 'completed') && (
                          <Button
                            size="sm"
                            onClick={() => handleExecute(test.id)}
                            disabled={loading}
                          >
                            <Play className="w-4 h-4 mr-1" />
                            Execute
                          </Button>
                        )}

                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDelete(test.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Endpoints and Test Cases View */}
        {selectedTestId && (endpoints.length > 0 || testCases.length > 0) && (
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
              <CardDescription>Parsed endpoints and generated test cases</CardDescription>
            </CardHeader>
            <CardContent>
            <Tabs defaultValue="endpoints">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="endpoints">
                  <List className="w-4 h-4 mr-2" />
                  Endpoints ({endpoints.length})
                </TabsTrigger>
                <TabsTrigger value="testcases">
                  <Code className="w-4 h-4 mr-2" />
                  Test Cases ({testCases.length})
                </TabsTrigger>
                <TabsTrigger value="results">
                  <Play className="w-4 h-4 mr-2" />
                  Test Results
                </TabsTrigger>
              </TabsList>

              <TabsContent value="endpoints" className="space-y-2 mt-4">
                {endpoints.length === 0 ? (
                  <p className="text-center text-gray-500 py-4">No endpoints parsed yet</p>
                ) : (
                  <Accordion type="single" collapsible className="w-full">
                    {endpoints.map((endpoint, idx) => (
                      <AccordionItem key={endpoint.id} value={`endpoint-${idx}`}>
                        <AccordionTrigger>
                          <div className="flex items-center gap-2">
                            <Badge className={getMethodColor(endpoint.http_method)}>
                              {endpoint.http_method}
                            </Badge>
                            <span className="font-mono text-sm">{endpoint.endpoint_path}</span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="space-y-3 pl-4">
                            {endpoint.auth_required && (
                              <div className="text-sm">
                                <span className="font-semibold">Auth Required:</span> Yes
                              </div>
                            )}
                            
                            {endpoint.parameters && Object.keys(endpoint.parameters).some(key => endpoint.parameters[key]?.length > 0) && (
                              <div>
                                <span className="font-semibold text-sm">Parameters:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto">
                                  {JSON.stringify(endpoint.parameters, null, 2)}
                                </pre>
                              </div>
                            )}
                            
                            {endpoint.request_schema && (
                              <div>
                                <span className="font-semibold text-sm">Request Schema:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                  {JSON.stringify(endpoint.request_schema, null, 2)}
                                </pre>
                              </div>
                            )}
                            
                            {endpoint.response_schema && (
                              <div>
                                <span className="font-semibold text-sm">Response Schema:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                  {JSON.stringify(endpoint.response_schema, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                )}
              </TabsContent>

              <TabsContent value="testcases" className="space-y-2 mt-4">
                {testCases.length === 0 ? (
                  <p className="text-center text-gray-500 py-4">No test cases generated yet</p>
                ) : (
                  <Accordion type="single" collapsible className="w-full">
                    {testCases.map((testCase, idx) => (
                      <AccordionItem key={testCase.id} value={`testcase-${idx}`}>
                        <AccordionTrigger>
                          <div className="flex items-center gap-2">
                            <Badge className={getMethodColor(testCase.http_method)}>
                              {testCase.http_method}
                            </Badge>
                            <span className="text-sm">{testCase.test_name}</span>
                            <Badge variant={testCase.status === 'passed' ? 'default' : 'secondary'}>
                              {testCase.status}
                            </Badge>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="space-y-3 pl-4">
                            {testCase.generated_request?.base_url && (
                              <div className="text-sm">
                                <span className="font-semibold">Base URL:</span> {testCase.generated_request.base_url}
                              </div>
                            )}
                            
                            <div className="text-sm">
                              <span className="font-semibold">Endpoint:</span> {testCase.endpoint_path}
                            </div>
                            
                            {testCase.generated_request && (
                              <div>
                                <span className="font-semibold text-sm">Generated Request:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                  {JSON.stringify({
                                    path_params: testCase.generated_request.path_params,
                                    query_params: testCase.generated_request.query_params,
                                    headers: testCase.generated_request.headers,
                                    body: testCase.generated_request.body
                                  }, null, 2)}
                                </pre>
                              </div>
                            )}
                            
                            {testCase.expected_response_schema && (
                              <div>
                                <span className="font-semibold text-sm">Expected Response Schema:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                  {JSON.stringify(testCase.expected_response_schema, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                  </Accordion>
                )}
              </TabsContent>

              <TabsContent value="results" className="space-y-2 mt-4">
                {results && results.results && results.results.length > 0 ? (
                  <>
                    <div className="grid grid-cols-4 gap-4 mb-6">
                      <div className="text-center p-4 bg-blue-50 rounded-lg">
                        <div className="text-2xl font-bold text-blue-600">{results.summary.total}</div>
                        <div className="text-sm text-gray-600">Total Tests</div>
                      </div>
                      <div className="text-center p-4 bg-green-50 rounded-lg">
                        <div className="text-2xl font-bold text-green-600">{results.summary.passed}</div>
                        <div className="text-sm text-gray-600">Passed</div>
                      </div>
                      <div className="text-center p-4 bg-red-50 rounded-lg">
                        <div className="text-2xl font-bold text-red-600">{results.summary.failed}</div>
                        <div className="text-sm text-gray-600">Failed</div>
                      </div>
                      <div className="text-center p-4 bg-purple-50 rounded-lg">
                        <div className="text-2xl font-bold text-purple-600">{results.summary.success_rate}%</div>
                        <div className="text-sm text-gray-600">Success Rate</div>
                      </div>
                    </div>
                    <Accordion type="single" collapsible className="w-full">
                    {results.results.map((result, idx) => (
                      <AccordionItem key={idx} value={`result-${idx}`}>
                        <AccordionTrigger>
                          <div className="flex items-center gap-2">
                            {result.schema_validation === 'pass' && result.actual_status === result.expected_status ? (
                              <CheckCircle className="w-4 h-4 text-green-600" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-600" />
                            )}
                            <span className="text-sm">{result.test_name}</span>
                            <Badge variant={result.actual_status === result.expected_status ? 'default' : 'destructive'}>
                              {result.actual_status}
                            </Badge>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="space-y-3 pl-4">
                            <div className="text-sm">
                              <span className="font-semibold">Endpoint:</span> {result.endpoint}
                            </div>
                            
                            <div className="text-sm">
                              <span className="font-semibold">Status:</span> {result.actual_status} (expected {result.expected_status})
                            </div>
                            
                            <div className="text-sm">
                              <span className="font-semibold">Schema Validation:</span>{' '}
                              <Badge variant={result.schema_validation === 'pass' ? 'default' : 'destructive'}>
                                {result.schema_validation}
                              </Badge>
                            </div>
                            
                            <div className="text-sm">
                              <span className="font-semibold">Response Time:</span> {result.response_time ? `${(result.response_time * 1000).toFixed(0)}ms` : 'N/A'}
                            </div>
                            
                            {result.error && (
                              <div>
                                <span className="font-semibold text-sm text-red-600">Error:</span>
                                <pre className="mt-1 p-2 bg-red-50 rounded text-xs overflow-auto">
                                  {result.error}
                                </pre>
                              </div>
                            )}
                            
                            {result.request_url && (
                              <div>
                                <span className="font-semibold text-sm">Request URL:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto">
                                  {result.request_method} {result.request_url}
                                </pre>
                              </div>
                            )}
                            
                            {result.request_body && (
                              <div>
                                <span className="font-semibold text-sm">Request Body:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                  {JSON.stringify(result.request_body, null, 2)}
                                </pre>
                              </div>
                            )}
                            
                            {result.response_body && (
                              <div>
                                <span className="font-semibold text-sm">Response Body:</span>
                                <pre className="mt-1 p-2 bg-gray-50 rounded text-xs overflow-auto max-h-40">
                                  {JSON.stringify(result.response_body, null, 2)}
                                </pre>
                              </div>
                            )}
                            
                            <div className="text-sm">
                              <span className="font-semibold">Executed At:</span> {new Date(result.executed_at).toLocaleString()}
                            </div>
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    ))}
                    </Accordion>
                  </>
                ) : (
                  <p className="text-center text-gray-500 py-4">No test results yet. Execute tests to see results.</p>
                )}
              </TabsContent>
            </Tabs>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
