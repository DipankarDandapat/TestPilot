import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { toast } from "sonner";
import { ArrowLeft, Sparkles, Play, CheckCircle, XCircle, Clock, AlertCircle, Edit, Send, Code, Download } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const APIDetail = () => {
  const { apiId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnPage = searchParams.get('page') || '1';
  const fromCollection = searchParams.get('from') === 'collection';
  const collectionId = searchParams.get('collectionId');
  const [api, setApi] = useState(null);
  const [testCases, setTestCases] = useState([]);
  const [testResults, setTestResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [running, setRunning] = useState(false);
  const [editingTestCase, setEditingTestCase] = useState(null);
  const [editFormData, setEditFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const [testingApi, setTestingApi] = useState(false);
  const [apiTestResult, setApiTestResult] = useState(null);
  const [apiTestHistory, setApiTestHistory] = useState([]);
  const [editingApi, setEditingApi] = useState(false);
  const [apiFormData, setApiFormData] = useState({});
  const [showBusinessRulesDialog, setShowBusinessRulesDialog] = useState(false);
  const [businessRules, setBusinessRules] = useState("");
  const [aiProvider, setAiProvider] = useState("openai");

  // JSON Syntax Highlighter
  const syntaxHighlight = (json) => {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, null, 2);
    }
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/(".+?")(:?)|(\btrue\b|\bfalse\b|\bnull\b)|(-?\d+\.?\d*)/g, function (match, p1, p2, p3, p4) {
      let cls = 'text-slate-700';
      if (p1 && p2) {
        cls = 'text-blue-600 font-medium'; // keys
      } else if (p1) {
        cls = 'text-green-600'; // string values
      } else if (p3) {
        cls = 'text-purple-600 font-medium'; // boolean/null
      } else if (p4) {
        cls = 'text-orange-600'; // numbers
      }
      return `<span class="${cls}">${match}</span>`;
    });
  };

  const fetchAPIDetails = useCallback(async () => {
    try {
      const [apiRes, testCasesRes, resultsRes, apiTestHistoryRes] = await Promise.all([
        axios.get(`${API}/apis/${apiId}`),
        axios.get(`${API}/apis/${apiId}/testcases`),
        axios.get(`${API}/apis/${apiId}/results`),
        axios.get(`${API}/apis/${apiId}/test-results`)
      ]);
      
      setApi(apiRes.data);
      setTestCases(testCasesRes.data);
      setTestResults(resultsRes.data);
      setApiTestHistory(apiTestHistoryRes.data);
      setApiFormData({
        url: apiRes.data.url,
        method: apiRes.data.method,
        headers: JSON.stringify(apiRes.data.headers || {}, null, 2),
        query_params: JSON.stringify(apiRes.data.query_params || {}, null, 2),
        body: apiRes.data.body ? JSON.stringify(apiRes.data.body, null, 2) : ''
      });
    } catch (error) {
      toast.error("Failed to fetch API details");
      navigate("/");
    } finally {
      setLoading(false);
    }
  }, [apiId, navigate]);

  useEffect(() => {
    fetchAPIDetails();
  }, [fetchAPIDetails]);

  const handleGenerateClick = () => {
    setShowBusinessRulesDialog(true);
  };

  const handleGenerateTestCases = async () => {
    setShowBusinessRulesDialog(false);
    setGenerating(true);
    try {
      const payload = { api_id: apiId, provider: aiProvider };
      if (businessRules.trim()) {
        payload.business_rules = businessRules.trim();
      }
      const response = await axios.post(`${API}/generate-testcases`, payload);
      toast.success(response.data.message);
      fetchAPIDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to generate test cases");
    } finally {
      setGenerating(false);
    }
  };

  const handleRunTests = async () => {
    setRunning(true);
    try {
      const response = await axios.post(`${API}/run-tests`, {
        api_id: apiId
      });
      toast.success(response.data.message);
      fetchAPIDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to run tests");
    } finally {
      setRunning(false);
    }
  };

  const handleDownloadReport = () => {
    if (testResults.length === 0) {
      toast.error("No test results available. Please run tests first.");
      return;
    }
    window.open(`${API}/apis/${apiId}/report/download`, '_blank');
    toast.success("Downloading HTML report...");
  };

  const handleEditTestCase = (testCase) => {
    setEditingTestCase(testCase);
    setEditFormData({
      name: testCase.name,
      description: testCase.description,
      test_url: testCase.test_url,
      test_method: testCase.test_method,
      test_headers: JSON.stringify(testCase.test_headers || {}, null, 2),
      query_params: JSON.stringify(testCase.query_params || {}, null, 2),
      test_body: testCase.test_body ? JSON.stringify(testCase.test_body, null, 2) : '',
      expected_status: testCase.expected_status || '',
      assertions: testCase.assertions ? JSON.stringify(testCase.assertions, null, 2) : ''
    });
  };

  const handleSaveTestCase = async () => {
    setSaving(true);
    try {
      // Parse assertions - allow empty/null
      let parsedAssertions = null;
      if (editFormData.assertions && editFormData.assertions.trim()) {
        try {
          parsedAssertions = JSON.parse(editFormData.assertions);
        } catch (e) {
          toast.error("Invalid JSON in assertions field");
          setSaving(false);
          return;
        }
      }

      const updateData = {
        name: editFormData.name,
        description: editFormData.description,
        test_url: editFormData.test_url,
        test_method: editFormData.test_method,
        test_headers: editFormData.test_headers ? JSON.parse(editFormData.test_headers) : {},
        query_params: editFormData.query_params ? JSON.parse(editFormData.query_params) : null,
        test_body: editFormData.test_body ? JSON.parse(editFormData.test_body) : null,
        expected_status: editFormData.expected_status ? parseInt(editFormData.expected_status) : null,
        assertions: parsedAssertions
      };

      await axios.put(`${API}/testcases/${editingTestCase.id}`, updateData);
      toast.success("Test case updated successfully");
      setEditingTestCase(null);
      fetchAPIDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update test case");
    } finally {
      setSaving(false);
    }
  };

  const handleTestAPI = async () => {
    setTestingApi(true);
    setApiTestResult(null);
    try {
      const response = await axios.post(`${API}/apis/${apiId}/test`);
      setApiTestResult(response.data);
      // Refresh history to include the new result
      const historyRes = await axios.get(`${API}/apis/${apiId}/test-results`);
      setApiTestHistory(historyRes.data);
      if (response.data.success) {
        toast.success(`API responded with status ${response.data.status_code}`);
      } else {
        toast.error("API test failed");
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to test API");
      setApiTestResult({ success: false, error: error.message });
    } finally {
      setTestingApi(false);
    }
  };

  const handleEditApi = () => {
    setEditingApi(true);
  };

  const handleSaveApi = async () => {
    try {
      let headers = {};
      let query_params = null;
      let body = null;

      if (apiFormData.headers.trim()) {
        headers = JSON.parse(apiFormData.headers);
      }
      if (apiFormData.query_params.trim() && apiFormData.query_params !== '{}') {
        query_params = JSON.parse(apiFormData.query_params);
      }
      if (apiFormData.body.trim()) {
        body = JSON.parse(apiFormData.body);
      }

      await axios.put(`${API}/apis/${apiId}`, {
        url: apiFormData.url,
        method: apiFormData.method,
        headers,
        query_params,
        body
      });

      toast.success("API updated successfully");
      setEditingApi(false);
      fetchAPIDetails();
    } catch (error) {
      if (error instanceof SyntaxError) {
        toast.error("Invalid JSON format. Please check your input.");
      } else {
        toast.error(error.response?.data?.detail || "Failed to update API");
      }
    }
  };

  const getTypeColor = (type) => {
    const colors = {
      positive: "bg-green-500/10 text-green-700 border-green-500/20",
      negative: "bg-red-500/10 text-red-700 border-red-500/20",
      symmetric: "bg-blue-500/10 text-blue-700 border-blue-500/20",
      security: "bg-purple-500/10 text-purple-700 border-purple-500/20"
    };
    return colors[type] || "bg-gray-500/10 text-gray-700";
  };

  const getMethodColor = (method) => {
    const colors = {
      GET: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
      POST: "bg-blue-500/10 text-blue-600 border-blue-500/20",
      PUT: "bg-amber-500/10 text-amber-600 border-amber-500/20",
      PATCH: "bg-purple-500/10 text-purple-600 border-purple-500/20",
      DELETE: "bg-rose-500/10 text-rose-600 border-rose-500/20"
    };
    return colors[method] || "bg-gray-500/10 text-gray-600";
  };

  // Calculate pass/fail counts
  const passedTests = testResults.filter(result => result.passed).length;
  const failedTests = testResults.filter(result => !result.passed).length;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="loading-indicator">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <Button 
          variant="outline" 
          onClick={() => {
            if (fromCollection && collectionId) {
              navigate(`/collections/${collectionId}`);
            } else {
              navigate(`/?page=${returnPage}`);
            }
          }}
          className="mb-4"
          data-testid="back-button"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {fromCollection ? 'Back to Collection' : 'Back to Dashboard'}
        </Button>

        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-2" data-testid="api-name">{api.name}</h1>
          <p className="text-slate-600" data-testid="api-description">{api.description || "No description"}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
          <Card data-testid="api-info-card" className="border-l-4 border-l-slate-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Code className="w-4 h-4 text-slate-600" />
                Method
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Badge className={getMethodColor(api.method)} data-testid="api-method">{api.method}</Badge>
            </CardContent>
          </Card>

          <Card data-testid="test-cases-count-card" className="border-l-4 border-l-purple-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-600" />
                AI Generated Test Cases
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-purple-600" data-testid="test-cases-count">{testCases.length}</p>
            </CardContent>
          </Card>

          <Card data-testid="test-runs-count-card" className="border-l-4 border-l-blue-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Play className="w-4 h-4 text-blue-600" />
                Test Runs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-blue-600" data-testid="test-runs-count">{testResults.length}</p>
            </CardContent>
          </Card>

          <Card data-testid="passed-tests-card" className="border-l-4 border-l-green-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-600" />
                Passed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-green-600" data-testid="passed-tests-count">{passedTests}</p>
            </CardContent>
          </Card>

          <Card data-testid="failed-tests-card" className="border-l-4 border-l-red-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-600" />
                Failed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600" data-testid="failed-tests-count">{failedTests}</p>
            </CardContent>
          </Card>
        </div>

        <Card className="mb-6" data-testid="api-endpoint-card">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>API Configuration</CardTitle>
              {!editingApi ? (
                <Button variant="outline" size="sm" onClick={handleEditApi}>
                  <Edit className="w-4 h-4 mr-1" />
                  Edit
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button size="sm" onClick={handleSaveApi}>
                    Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => {
                    setEditingApi(false);
                    setApiFormData({
                      url: api.url,
                      method: api.method,
                      headers: JSON.stringify(api.headers || {}, null, 2),
                      query_params: JSON.stringify(api.query_params || {}, null, 2),
                      body: api.body ? JSON.stringify(api.body, null, 2) : ''
                    });
                  }}>
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {editingApi ? (
              <div className="space-y-4">
                <div>
                  <Label className="mb-2 block font-semibold">Method</Label>
                  <Select
                    value={apiFormData.method}
                    onValueChange={(value) => setApiFormData({ ...apiFormData, method: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="GET">GET</SelectItem>
                      <SelectItem value="POST">POST</SelectItem>
                      <SelectItem value="PUT">PUT</SelectItem>
                      <SelectItem value="PATCH">PATCH</SelectItem>
                      <SelectItem value="DELETE">DELETE</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="mb-2 block font-semibold">URL</Label>
                  <Input
                    value={apiFormData.url}
                    onChange={(e) => setApiFormData({ ...apiFormData, url: e.target.value })}
                    className="font-mono text-sm"
                  />
                </div>
                <div>
                  <Label className="mb-2 block font-semibold">Headers (JSON)</Label>
                  <Textarea
                    value={apiFormData.headers}
                    onChange={(e) => setApiFormData({ ...apiFormData, headers: e.target.value })}
                    rows={4}
                    className="font-mono text-sm"
                  />
                </div>
                <div>
                  <Label className="mb-2 block font-semibold">Query Parameters (JSON)</Label>
                  <Textarea
                    value={apiFormData.query_params}
                    onChange={(e) => setApiFormData({ ...apiFormData, query_params: e.target.value })}
                    rows={3}
                    className="font-mono text-sm"
                  />
                </div>
                <div>
                  <Label className="mb-2 block font-semibold">Body (JSON)</Label>
                  <Textarea
                    value={apiFormData.body}
                    onChange={(e) => setApiFormData({ ...apiFormData, body: e.target.value })}
                    rows={6}
                    className="font-mono text-sm"
                    disabled={apiFormData.method === 'GET' || apiFormData.method === 'DELETE'}
                  />
                  {(apiFormData.method === 'GET' || apiFormData.method === 'DELETE') && (
                    <p className="text-xs text-slate-500 mt-1">Body is not allowed for {apiFormData.method} requests</p>
                  )}
                </div>
              </div>
            ) : (
              <>
                <div className="bg-white border border-slate-200 p-4 rounded font-mono text-sm break-all" data-testid="api-endpoint">
                  {api.url}
                </div>
                {api.headers && Object.keys(api.headers).length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-semibold mb-2">Headers:</h4>
                    <div className="bg-white border border-slate-200 rounded p-4">
                      <pre 
                        className="text-sm font-mono leading-relaxed overflow-auto"
                        data-testid="api-headers"
                        dangerouslySetInnerHTML={{
                          __html: syntaxHighlight(api.headers)
                        }}
                      />
                    </div>
                  </div>
                )}
                {api.query_params && Object.keys(api.query_params).length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-semibold mb-2">Query Parameters:</h4>
                    <div className="bg-white border border-slate-200 rounded p-4">
                      <pre 
                        className="text-sm font-mono leading-relaxed overflow-auto"
                        data-testid="api-query-params"
                        dangerouslySetInnerHTML={{
                          __html: syntaxHighlight(api.query_params)
                        }}
                      />
                    </div>
                  </div>
                )}
                {api.body && (
                  <div className="mt-4">
                    <h4 className="font-semibold mb-2">Body:</h4>
                    <div className="bg-white border border-slate-200 rounded p-4">
                      <pre 
                        className="text-sm font-mono leading-relaxed overflow-auto"
                        data-testid="api-body"
                        dangerouslySetInnerHTML={{
                          __html: syntaxHighlight(api.body)
                        }}
                      />
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <div className="flex gap-4 mb-6">
          <Button 
            onClick={handleTestAPI}
            disabled={testingApi}
            variant="outline"
            className="border-blue-600 text-blue-600 hover:bg-blue-50"
            data-testid="test-api-button"
          >
            {testingApi ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                Testing...
              </>
            ) : (
              <>
                <Send className="w-4 h-4 mr-2" />
                Test API
              </>
            )}
          </Button>

          <Button 
            onClick={handleGenerateClick}
            disabled={generating}
            className="bg-purple-600 hover:bg-purple-700"
            data-testid="generate-testcases-button"
          >
            {generating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Generate Test Cases
              </>
            )}
          </Button>

          <Button 
            onClick={handleRunTests}
            disabled={running || testCases.length === 0}
            className="bg-green-600 hover:bg-green-700"
            data-testid="run-tests-button"
          >
            {running ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Running...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Run All Generated Tests
              </>
            )}
          </Button>

          <Button 
            onClick={handleDownloadReport}
            disabled={testResults.length === 0}
            variant="outline"
            className="border-orange-600 text-orange-600 hover:bg-orange-50"
            data-testid="download-report-button"
          >
            <Download className="w-4 h-4 mr-2" />
            Download HTML Report
          </Button>
        </div>

        <Tabs defaultValue="api-test-result" className="w-full">
          <TabsList data-testid="tabs-list">
            <TabsTrigger value="api-test-result" data-testid="api-test-result-tab">API Test Result</TabsTrigger>
            <TabsTrigger value="testcases" data-testid="testcases-tab">Test Cases</TabsTrigger>
            <TabsTrigger value="results" data-testid="results-tab">Test Results</TabsTrigger>
          </TabsList>

          <TabsContent value="api-test-result" className="mt-6" data-testid="api-test-result-content">
            {apiTestHistory.length === 0 && !apiTestResult ? (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Send className="w-16 h-16 text-slate-300 mb-4" />
                  <h3 className="text-xl font-semibold text-slate-700 mb-2">No API test results yet</h3>
                  <p className="text-slate-500 mb-4">Click "Test API" to execute and see results here</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {apiTestHistory.map((result, index) => (
                  <Card key={result.id || index} className={`border-l-4 ${result.success ? 'border-l-green-500' : 'border-l-red-500'}`}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2">
                          {result.success ? (
                            <CheckCircle className="w-5 h-5 text-green-600" />
                          ) : (
                            <XCircle className="w-5 h-5 text-red-600" />
                          )}
                          API Test Result
                        </CardTitle>
                        <div className="flex items-center gap-3 text-sm text-slate-500">
                          {result.status_code && (
                            <Badge variant={result.status_code < 400 ? "default" : "destructive"}>
                              {result.status_code}
                            </Badge>
                          )}
                          {result.response_time && (
                            <span>{(result.response_time * 1000).toFixed(0)}ms</span>
                          )}
                          {result.executed_at && (
                            <span>{new Date(result.executed_at).toLocaleString()}</span>
                          )}
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {result.success ? (
                        <div className="space-y-4">
                          <div>
                            <span className="font-semibold text-sm">Request:</span>
                            <Badge className={`ml-2 ${getMethodColor(result.request_method)}`}>{result.request_method}</Badge>
                            <div className="bg-slate-50 p-2 rounded mt-1 text-sm font-mono break-all">
                              {result.request_url}
                            </div>
                          </div>
                          {result.request_headers && Object.keys(result.request_headers).length > 0 && (
                            <div>
                              <span className="font-semibold text-sm">Request Headers:</span>
                              <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                <pre className="text-sm font-mono leading-relaxed overflow-auto"
                                  dangerouslySetInnerHTML={{ __html: syntaxHighlight(result.request_headers) }}
                                />
                              </div>
                            </div>
                          )}
                          {result.request_body && (
                            <div>
                              <span className="font-semibold text-sm">Request Body:</span>
                              <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                <pre className="text-sm font-mono leading-relaxed overflow-auto"
                                  dangerouslySetInnerHTML={{ __html: syntaxHighlight(result.request_body) }}
                                />
                              </div>
                            </div>
                          )}
                          {/* Response section with tabs */}
                          <div>
                            <span className="font-semibold text-sm">Response:</span>
                            <Tabs defaultValue="resp-body" className="w-full mt-2">
                              <TabsList className="grid w-full grid-cols-3">
                                <TabsTrigger value="resp-body">Body</TabsTrigger>
                                <TabsTrigger value="resp-headers">Headers</TabsTrigger>
                                <TabsTrigger value="resp-cookies">Cookies</TabsTrigger>
                              </TabsList>
                              <TabsContent value="resp-body" className="mt-3">
                                {result.response_body ? (
                                  <div className="bg-white border border-slate-200 rounded-lg p-4 overflow-auto max-h-96">
                                    <pre className="text-sm font-mono leading-relaxed"
                                      dangerouslySetInnerHTML={{ __html: syntaxHighlight(
                                        typeof result.response_body === 'string' ? result.response_body : result.response_body
                                      ) }}
                                    />
                                  </div>
                                ) : (
                                  <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                    No response body
                                  </div>
                                )}
                              </TabsContent>
                              <TabsContent value="resp-headers" className="mt-3">
                                {result.response_headers && Object.keys(result.response_headers).length > 0 ? (
                                  <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden">
                                    <div className="divide-y divide-slate-200">
                                      {Object.entries(result.response_headers).map(([key, value]) => (
                                        <div key={key} className="grid grid-cols-3 gap-4 p-3 hover:bg-slate-100">
                                          <div className="font-semibold text-sm text-slate-700">{key}:</div>
                                          <div className="col-span-2 text-sm text-slate-600 break-all">{value}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ) : (
                                  <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                    No response headers
                                  </div>
                                )}
                              </TabsContent>
                              <TabsContent value="resp-cookies" className="mt-3">
                                {result.response_cookies && Object.keys(result.response_cookies).length > 0 ? (
                                  <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden">
                                    <div className="divide-y divide-slate-200">
                                      {Object.entries(result.response_cookies).map(([key, value]) => (
                                        <div key={key} className="grid grid-cols-3 gap-4 p-3 hover:bg-slate-100">
                                          <div className="font-semibold text-sm text-slate-700">{key}:</div>
                                          <div className="col-span-2 text-sm text-slate-600 break-all">{value}</div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                ) : result.response_headers && result.response_headers['set-cookie'] ? (
                                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                                    <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap break-all">
                                      {result.response_headers['set-cookie']}
                                    </pre>
                                  </div>
                                ) : (
                                  <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                    No cookies set
                                  </div>
                                )}
                              </TabsContent>
                            </Tabs>
                          </div>
                        </div>
                      ) : (
                        <div className="text-red-600">
                          <span className="font-semibold">Error:</span> {result.error}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          <TabsContent value="testcases" className="mt-6" data-testid="testcases-content">
            {testCases.length === 0 ? (
              <Card data-testid="no-testcases">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <AlertCircle className="w-16 h-16 text-slate-300 mb-4" />
                  <h3 className="text-xl font-semibold text-slate-700 mb-2">No test cases yet</h3>
                  <p className="text-slate-500 mb-4">Generate AI-powered test cases to get started</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {["positive", "negative", "symmetric", "security"].map(type => {
                  const casesOfType = testCases.filter(tc => tc.type === type);
                  if (casesOfType.length === 0) return null;
                  
                  return (
                    <Card key={type} data-testid={`testcase-group-${type}`}>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Badge className={getTypeColor(type)}>{type.toUpperCase()}</Badge>
                          <span className="text-sm font-normal text-slate-500">
                            ({casesOfType.length} test{casesOfType.length !== 1 ? 's' : ''})
                          </span>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <Accordion type="single" collapsible>
                          {casesOfType.map((tc) => (
                            <AccordionItem key={tc.id} value={tc.id} data-testid={`testcase-${tc.id}`}>
                              <AccordionTrigger className="text-left">
                                <div className="flex items-center justify-between w-full pr-4">
                                  <div>
                                    <div className="font-semibold">{tc.name}</div>
                                    <div className="text-sm text-slate-500">{tc.description}</div>
                                  </div>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleEditTestCase(tc);
                                    }}
                                    className="ml-2"
                                  >
                                    <Edit className="w-4 h-4" />
                                  </Button>
                                </div>
                              </AccordionTrigger>
                              <AccordionContent>
                                <div className="space-y-3 pt-2">
                                  <div>
                                    <span className="font-semibold text-sm">Method:</span>
                                    <Badge className={`ml-2 ${getMethodColor(tc.test_method)}`}>
                                      {tc.test_method}
                                    </Badge>
                                  </div>
                                  <div>
                                    <span className="font-semibold text-sm">URL:</span>
                                    <div className="bg-white border border-slate-200 p-2 rounded mt-1 text-sm font-mono break-all">
                                      {tc.test_url}
                                    </div>
                                  </div>
                                  {tc.test_headers && Object.keys(tc.test_headers).length > 0 && (
                                    <div>
                                      <span className="font-semibold text-sm">Headers:</span>
                                      <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                        <pre 
                                          className="text-sm font-mono leading-relaxed overflow-auto"
                                          dangerouslySetInnerHTML={{
                                            __html: syntaxHighlight(tc.test_headers)
                                          }}
                                        />
                                      </div>
                                    </div>
                                  )}
                                  {tc.query_params && Object.keys(tc.query_params).length > 0 && (
                                    <div>
                                      <span className="font-semibold text-sm">Query Parameters:</span>
                                      <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                        <pre 
                                          className="text-sm font-mono leading-relaxed overflow-auto"
                                          dangerouslySetInnerHTML={{
                                            __html: syntaxHighlight(tc.query_params)
                                          }}
                                        />
                                      </div>
                                    </div>
                                  )}
                                  {tc.test_body && (
                                    <div>
                                      <span className="font-semibold text-sm">Body:</span>
                                      <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                        <pre 
                                          className="text-sm font-mono leading-relaxed overflow-auto"
                                          dangerouslySetInnerHTML={{
                                            __html: syntaxHighlight(tc.test_body)
                                          }}
                                        />
                                      </div>
                                    </div>
                                  )}
                                  {tc.expected_status && (
                                    <div>
                                      <span className="font-semibold text-sm">Expected Status:</span>
                                      <span className="ml-2 text-sm">{tc.expected_status}</span>
                                    </div>
                                  )}
                                  {tc.assertions && (
                                    <div>
                                      <span className="font-semibold text-sm">Assertions:</span>
                                      <div className="bg-blue-50 border border-blue-200 rounded p-3 mt-1">
                                        <div className="space-y-1 text-sm">
                                          {tc.assertions.expected_status && (
                                            <div>✓ Status Code: {tc.assertions.expected_status}</div>
                                          )}
                                          {tc.assertions.max_response_time && (
                                            <div>✓ Response Time: &lt; {tc.assertions.max_response_time}s</div>
                                          )}
                                          {tc.assertions.content_type && (
                                            <div>✓ Content-Type: {tc.assertions.content_type}</div>
                                          )}
                                          {tc.assertions.response_not_empty && (
                                            <div>✓ Response Not Empty</div>
                                          )}
                                          {tc.assertions.response_schema?.required_fields && (
                                            <div>✓ Required Fields: {tc.assertions.response_schema.required_fields.join(', ')}</div>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </AccordionContent>
                            </AccordionItem>
                          ))}
                        </Accordion>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </TabsContent>

          <TabsContent value="results" className="mt-6" data-testid="results-content">
            {testResults.length === 0 ? (
              <Card data-testid="no-results">
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <Clock className="w-16 h-16 text-slate-300 mb-4" />
                  <h3 className="text-xl font-semibold text-slate-700 mb-2">No test results yet</h3>
                  <p className="text-slate-500 mb-4">Run tests to see results here</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-4">
                {["positive", "negative", "symmetric", "security"].map(type => {
                  const resultsOfType = testResults.filter(result => result.type === type);
                  if (resultsOfType.length === 0) return null;
                  
                  return (
                    <Card key={type} data-testid={`result-group-${type}`}>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Badge className={getTypeColor(type)}>{type.toUpperCase()}</Badge>
                          <span className="text-sm font-normal text-slate-500">
                            ({resultsOfType.length} result{resultsOfType.length !== 1 ? 's' : ''})
                          </span>
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-4">
                          {resultsOfType.map((result) => {
                            const testCase = testCases.find(tc => tc.id === result.test_case_id);
                            return (
                              <Card key={result.id} data-testid={`result-${result.id}`} className="border-l-4" style={{
                                borderLeftColor: result.passed ? '#16a34a' : '#dc2626'
                              }}>
                                <CardHeader>
                                  <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                      <CardTitle className="text-base flex items-center gap-2">
                                        {result.passed ? (
                                          <CheckCircle className="w-5 h-5 text-green-600" data-testid="result-passed-icon" />
                                        ) : (
                                          <XCircle className="w-5 h-5 text-red-600" data-testid="result-failed-icon" />
                                        )}
                                        {testCase?.name || "Unknown Test"}
                                      </CardTitle>
                                      <CardDescription className="mt-1">
                                        {testCase?.description || ""}
                                      </CardDescription>
                                      
                                      {/* Display Failures - Only show messages */}
                                      {result.failures && result.failures.length > 0 && (
                                        <div className="mt-3">
                                          <div className="text-sm font-semibold text-red-600 mb-1">Assertion Failures:</div>
                                          {result.failures.map((failure, idx) => (
                                            <div key={idx} className="text-sm text-red-600">
                                              • {failure.message}
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                    <div className="flex flex-col items-end gap-2 text-sm ml-4">
                                      <div className="flex items-center gap-2">
                                        <span className="font-semibold text-slate-600">Response Status:</span>
                                        {result.response_status ? (
                                          <Badge variant={result.passed ? "default" : "destructive"}>
                                            {result.response_status}
                                          </Badge>
                                        ) : (
                                          <span className="text-slate-500">N/A</span>
                                        )}
                                      </div>
                                      <div className="flex items-center gap-2">
                                        <span className="font-semibold text-slate-600">Response Time:</span>
                                        <span className={`font-medium ${
                                          result.response_time && result.response_time > 2 
                                            ? 'text-red-600' 
                                            : 'text-slate-700'
                                        }`}>
                                          {result.response_time ? `${(result.response_time * 1000).toFixed(0)}ms` : "N/A"}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </CardHeader>
                                <CardContent>
                                  <Accordion type="single" collapsible>
                                    <AccordionItem value="details">
                                      <AccordionTrigger>View Request & Response</AccordionTrigger>
                                      <AccordionContent>
                                        <div className="space-y-4">
                                          <div>
                                            <h4 className="font-semibold mb-2 flex items-center gap-2">
                                              Request
                                              <Badge className={getMethodColor(result.request_method)}>
                                                {result.request_method}
                                              </Badge>
                                            </h4>
                                            <div className="bg-slate-50 p-3 rounded space-y-3">
                                              <div>
                                                <span className="text-sm font-semibold">URL:</span>
                                                <div className="font-mono text-xs break-all mt-1 bg-white p-2 rounded border border-slate-200">
                                                  {result.request_url}
                                                </div>
                                              </div>
                                              {result.request_headers && Object.keys(result.request_headers).length > 0 && (
                                                <div>
                                                  <span className="text-sm font-semibold">Headers:</span>
                                                  <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                                    <pre 
                                                      className="text-sm font-mono leading-relaxed overflow-auto"
                                                      dangerouslySetInnerHTML={{
                                                        __html: syntaxHighlight(result.request_headers)
                                                      }}
                                                    />
                                                  </div>
                                                </div>
                                              )}
                                              {result.query_params && Object.keys(result.query_params).length > 0 && (
                                                <div>
                                                  <span className="text-sm font-semibold">Query Parameters:</span>
                                                  <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                                    <pre 
                                                      className="text-sm font-mono leading-relaxed overflow-auto"
                                                      dangerouslySetInnerHTML={{
                                                        __html: syntaxHighlight(result.query_params)
                                                      }}
                                                    />
                                                  </div>
                                                </div>
                                              )}
                                              {result.request_body && (
                                                <div>
                                                  <span className="text-sm font-semibold">Body:</span>
                                                  <div className="bg-white border border-slate-200 rounded p-3 mt-1">
                                                    <pre 
                                                      className="text-sm font-mono leading-relaxed overflow-auto"
                                                      dangerouslySetInnerHTML={{
                                                        __html: syntaxHighlight(result.request_body)
                                                      }}
                                                    />
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          </div>

                                          <div>
                                            <h4 className="font-semibold mb-3 flex items-center gap-2">
                                              Response
                                              {result.response_status && (
                                                <Badge variant={result.passed ? "default" : "destructive"}>
                                                  {result.response_status}
                                                </Badge>
                                              )}
                                            </h4>
                                            {result.error ? (
                                              <div className="bg-red-50 border border-red-200 p-3 rounded">
                                                <div className="text-red-600 text-sm">
                                                  <span className="font-semibold">Error:</span> {result.error}
                                                </div>
                                              </div>
                                            ) : (
                                              <Tabs defaultValue="body" className="w-full">
                                                <TabsList className="grid w-full grid-cols-4">
                                                  <TabsTrigger value="body">Body</TabsTrigger>
                                                  <TabsTrigger value="headers">Headers</TabsTrigger>
                                                  <TabsTrigger value="cookies">Cookies</TabsTrigger>
                                                  <TabsTrigger value="assertions">Assertions</TabsTrigger>
                                                </TabsList>
                                                
                                                <TabsContent value="body" className="mt-3">
                                                  {result.response_body ? (
                                                    <div className="bg-white border border-slate-200 rounded-lg p-4 overflow-auto max-h-96">
                                                      <pre 
                                                        className="text-sm font-mono leading-relaxed"
                                                        dangerouslySetInnerHTML={{
                                                          __html: syntaxHighlight(
                                                            typeof result.response_body === 'string' 
                                                              ? result.response_body 
                                                              : result.response_body
                                                          )
                                                        }}
                                                      />
                                                    </div>
                                                  ) : (
                                                    <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                                      No response body
                                                    </div>
                                                  )}
                                                </TabsContent>
                                                
                                                <TabsContent value="headers" className="mt-3">
                                                  {result.response_headers && Object.keys(result.response_headers).length > 0 ? (
                                                    <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden">
                                                      <div className="divide-y divide-slate-200">
                                                        {Object.entries(result.response_headers).map(([key, value]) => (
                                                          <div key={key} className="grid grid-cols-3 gap-4 p-3 hover:bg-slate-100">
                                                            <div className="font-semibold text-sm text-slate-700">{key}:</div>
                                                            <div className="col-span-2 text-sm text-slate-600 break-all">{value}</div>
                                                          </div>
                                                        ))}
                                                      </div>
                                                    </div>
                                                  ) : (
                                                    <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                                      No response headers
                                                    </div>
                                                  )}
                                                </TabsContent>
                                                
                                                <TabsContent value="cookies" className="mt-3">
                                                  {result.response_headers && result.response_headers['Set-Cookie'] ? (
                                                    <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                                                      <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap break-all">
                                                        {result.response_headers['Set-Cookie']}
                                                      </pre>
                                                    </div>
                                                  ) : (
                                                    <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                                      No cookies set
                                                    </div>
                                                  )}
                                                </TabsContent>
                                                
                                                <TabsContent value="assertions" className="mt-3">
                                                  <div className="space-y-3">
                                                    {/* Show what was checked */}
                                                    {testCase?.assertions && (
                                                      <div>
                                                        <div className="text-sm font-semibold mb-2">Assertions Checked:</div>
                                                        <div className="bg-blue-50 border border-blue-200 rounded p-3">
                                                          <div className="space-y-1 text-sm">
                                                            {testCase.assertions.expected_status && (
                                                              <div className="flex items-center gap-2">
                                                                {result.failures?.some(f => f.assertion_type === 'status_code') ? (
                                                                  <XCircle className="w-4 h-4 text-red-600" />
                                                                ) : (
                                                                  <CheckCircle className="w-4 h-4 text-green-600" />
                                                                )}
                                                                Status Code: {testCase.assertions.expected_status}
                                                              </div>
                                                            )}
                                                            {testCase.assertions.max_response_time && (
                                                              <div className="flex items-center gap-2">
                                                                {result.failures?.some(f => f.assertion_type === 'response_time') ? (
                                                                  <XCircle className="w-4 h-4 text-red-600" />
                                                                ) : (
                                                                  <CheckCircle className="w-4 h-4 text-green-600" />
                                                                )}
                                                                Response Time: &lt; {testCase.assertions.max_response_time}s
                                                              </div>
                                                            )}
                                                            {testCase.assertions.content_type && (
                                                              <div className="flex items-center gap-2">
                                                                {result.failures?.some(f => f.assertion_type === 'content_type') ? (
                                                                  <XCircle className="w-4 h-4 text-red-600" />
                                                                ) : (
                                                                  <CheckCircle className="w-4 h-4 text-green-600" />
                                                                )}
                                                                Content-Type: {testCase.assertions.content_type}
                                                              </div>
                                                            )}
                                                            {testCase.assertions.response_not_empty && (
                                                              <div className="flex items-center gap-2">
                                                                {result.failures?.some(f => f.assertion_type === 'response_not_empty') ? (
                                                                  <XCircle className="w-4 h-4 text-red-600" />
                                                                ) : (
                                                                  <CheckCircle className="w-4 h-4 text-green-600" />
                                                                )}
                                                                Response Not Empty
                                                              </div>
                                                            )}
                                                            {testCase.assertions.response_schema?.required_fields && (
                                                              <div className="flex items-center gap-2">
                                                                {result.failures?.some(f => f.assertion_type === 'required_field') ? (
                                                                  <XCircle className="w-4 h-4 text-red-600" />
                                                                ) : (
                                                                  <CheckCircle className="w-4 h-4 text-green-600" />
                                                                )}
                                                                Required Fields: {testCase.assertions.response_schema.required_fields.join(', ')}
                                                              </div>
                                                            )}
                                                          </div>
                                                        </div>
                                                      </div>
                                                    )}
                                                    
                                                    {/* Show failures with details */}
                                                    {result.failures && result.failures.length > 0 && (
                                                      <div>
                                                        <div className="text-sm font-semibold mb-2 text-red-600">Assertion Failures:</div>
                                                        <div className="space-y-2">
                                                          {result.failures.map((failure, idx) => (
                                                            <div key={idx} className="bg-red-50 border border-red-200 rounded p-3">
                                                              <div className="flex items-start gap-2">
                                                                <XCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                                                                <div className="flex-1">
                                                                  <div className="font-semibold text-red-700 text-sm">{failure.assertion_type}</div>
                                                                  <div className="text-red-600 text-sm mt-1">{failure.message}</div>
                                                                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                                                                    <div>
                                                                      <span className="font-semibold">Expected:</span> {JSON.stringify(failure.expected)}
                                                                    </div>
                                                                    <div>
                                                                      <span className="font-semibold">Actual:</span> {JSON.stringify(failure.actual)}
                                                                    </div>
                                                                  </div>
                                                                </div>
                                                              </div>
                                                            </div>
                                                          ))}
                                                        </div>
                                                      </div>
                                                    )}
                                                    
                                                    {!testCase?.assertions && !result.failures && (
                                                      <div className="bg-slate-50 p-4 rounded text-center text-slate-500 text-sm">
                                                        No assertions configured
                                                      </div>
                                                    )}
                                                  </div>
                                                </TabsContent>
                                              </Tabs>
                                            )}
                                          </div>
                                        </div>
                                      </AccordionContent>
                                    </AccordionItem>
                                  </Accordion>
                                </CardContent>
                              </Card>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </TabsContent>
        </Tabs>
        <Dialog open={showBusinessRulesDialog} onOpenChange={setShowBusinessRulesDialog}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Generate Test Cases</DialogTitle>
              <DialogDescription>
                Choose an AI provider and optionally add business requirements to generate more targeted test cases.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div>
                <Label className="mb-2 block font-semibold">AI Provider</Label>
                <Select value={aiProvider} onValueChange={setAiProvider}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="openai">OpenAI (GPT-4)</SelectItem>
                    <SelectItem value="gemini">Google Gemini</SelectItem>
                    <SelectItem value="local">Local (Rule-based)</SelectItem>
                  </SelectContent>
                </Select>
                {aiProvider === "local" && (
                  <p className="text-xs text-slate-500 mt-1">Uses built-in rule-based engine — no API key required.</p>
                )}
              </div>
              <div>
                <Label className="mb-2 block font-semibold">Business Requirements / Validation Rules</Label>
                <Textarea
                  value={businessRules}
                  onChange={(e) => setBusinessRules(e.target.value)}
                  rows={6}
                  className="font-mono text-sm"
                  placeholder={`Examples:\n- Username: 3-20 characters, alphanumeric only, must be unique\n- Email: valid email format, must be unique\n- Age: must be between 18-120\n- Password: min 8 chars, must contain uppercase, lowercase, number\n- Role: only allowed values are "admin", "user", "moderator"\n- If country is "US", then state field is required\n- Only admin users can delete records`}
                />
                <p className="text-xs text-slate-500 mt-1">
                  Leave empty to generate generic test cases, or add your rules for targeted validation scenarios.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => { setBusinessRules(""); handleGenerateTestCases(); }}>
                Skip & Generate
              </Button>
              <Button onClick={handleGenerateTestCases} className="bg-purple-600 hover:bg-purple-700">
                <Sparkles className="w-4 h-4 mr-2" />
                Generate with Rules
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Test Case Dialog */}
        <Dialog open={!!editingTestCase} onOpenChange={(open) => !open && setEditingTestCase(null)}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Edit Test Case</DialogTitle>
              <DialogDescription>
                Modify the test case details below and save your changes.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">Test Name</Label>
                <Input
                  id="name"
                  value={editFormData.name || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={editFormData.description || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="test_method">HTTP Method</Label>
                <Select
                  value={editFormData.test_method || 'GET'}
                  onValueChange={(value) => setEditFormData({ ...editFormData, test_method: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                    <SelectItem value="PUT">PUT</SelectItem>
                    <SelectItem value="PATCH">PATCH</SelectItem>
                    <SelectItem value="DELETE">DELETE</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="test_url">URL</Label>
                <Input
                  id="test_url"
                  value={editFormData.test_url || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, test_url: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="test_headers">Headers (JSON)</Label>
                <Textarea
                  id="test_headers"
                  value={editFormData.test_headers || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, test_headers: e.target.value })}
                  rows={4}
                  className="font-mono text-sm"
                  placeholder='{"Content-Type": "application/json"}'
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="query_params">Query Parameters (JSON)</Label>
                <Textarea
                  id="query_params"
                  value={editFormData.query_params || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, query_params: e.target.value })}
                  rows={3}
                  className="font-mono text-sm"
                  placeholder='{"key": "value"}'
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="test_body">Request Body (JSON)</Label>
                <Textarea
                  id="test_body"
                  value={editFormData.test_body || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, test_body: e.target.value })}
                  rows={6}
                  className="font-mono text-sm"
                  placeholder='{"key": "value"}'
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expected_status">Expected Status Code</Label>
                <Input
                  id="expected_status"
                  type="number"
                  value={editFormData.expected_status || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, expected_status: e.target.value })}
                  placeholder="200"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="assertions">Assertions (JSON) - Optional</Label>
                <Textarea
                  id="assertions"
                  value={editFormData.assertions || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, assertions: e.target.value })}
                  rows={8}
                  className="font-mono text-sm"
                  placeholder={JSON.stringify({
                    expected_status: 200,
                    max_response_time: 2.0,
                    content_type: "application/json",
                    response_not_empty: true
                  }, null, 2)}
                />
                <p className="text-xs text-slate-500">
                  Define validation rules (optional). Leave empty to skip assertions. Fields: expected_status, max_response_time, content_type, response_not_empty
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditingTestCase(null)} disabled={saving}>
                Cancel
              </Button>
              <Button onClick={handleSaveTestCase} disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
};

export default APIDetail;
