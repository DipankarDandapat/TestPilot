import { useState } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Copy, FileJson, RotateCcw, Sparkles } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const JSONViewer = ({ data }) => {
  const syntaxHighlight = (json) => {
    json = JSON.stringify(json, null, 2);
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(
      /(\"(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\"\\])*\"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      (match) => {
        let cls = 'text-orange-600';
        if (/^\"/.test(match)) {
          if (/:$/.test(match)) {
            cls = 'text-blue-600 font-semibold';
          } else {
            cls = 'text-green-600';
          }
        } else if (/true|false/.test(match)) {
          cls = 'text-purple-600';
        } else if (/null/.test(match)) {
          cls = 'text-red-600';
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
  };

  return (
    <pre
      className="font-mono text-sm p-4 bg-slate-50 rounded-lg overflow-auto min-h-[400px] border"
      dangerouslySetInnerHTML={{ __html: syntaxHighlight(data) }}
    />
  );
};

const JSONSchemaGenerator = () => {
  const navigate = useNavigate();
  const [jsonInput, setJsonInput] = useState("");
  const [jsonObject, setJsonObject] = useState(null);
  const [schemaObject, setSchemaObject] = useState(null);
  const [schema, setSchema] = useState("");
  const [loading, setLoading] = useState(false);

  // Generate Schema popup state
  const [showSchemaDialog, setShowSchemaDialog] = useState(false);
  const [schemaProvider, setSchemaProvider] = useState("local");
  const [emptyResponse, setEmptyResponse] = useState("");
  const [dataResponse, setDataResponse] = useState("");
  const [schemaRequirements, setSchemaRequirements] = useState("");

  // Generate Test Cases popup state
  const [showTestCasesDialog, setShowTestCasesDialog] = useState(false);
  const [testProvider, setTestProvider] = useState("local");
  const [testBusinessRules, setTestBusinessRules] = useState("");
  const [generatingTests, setGeneratingTests] = useState(false);
  const [testCases, setTestCases] = useState(null);

  const validateJSON = (text) => {
    try { JSON.parse(text); return true; } catch { return false; }
  };

  const beautifyJSON = () => {
    if (!jsonInput.trim()) { toast.error("Please enter JSON data"); return; }
    try {
      const parsed = JSON.parse(jsonInput);
      setJsonInput(JSON.stringify(parsed, null, 2));
      setJsonObject(parsed);
      toast.success("JSON beautified successfully");
    } catch {
      toast.error("Invalid JSON format");
    }
  };

  const handleGenerateSchemaClick = () => {
    if (!jsonInput.trim()) { toast.error("Please enter JSON data"); return; }
    if (!validateJSON(jsonInput)) { toast.error("Invalid JSON format. Please check your input."); return; }
    setShowSchemaDialog(true);
  };

  const handleGenerateSchema = async (useAI) => {
    setShowSchemaDialog(false);
    setLoading(true);
    try {
      const jsonData = JSON.parse(jsonInput);
      let response;
      if (useAI) {
        response = await axios.post(`${API}/json-to-schema-ai`, {
          json_data: jsonData,
          provider: schemaProvider,
          empty_response: emptyResponse || undefined,
          data_response: dataResponse || undefined,
          requirements: schemaRequirements || undefined,
        });
      } else {
        response = await axios.post(`${API}/json-to-schema`, { json_data: jsonData });
      }
      setSchema(JSON.stringify(response.data.schema, null, 2));
      setSchemaObject(response.data.schema);
      toast.success("Schema generated successfully");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to generate schema");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateTestCases = async () => {
    if (!schemaObject) { toast.error("Please generate a schema first"); return; }
    setShowTestCasesDialog(false);
    setGeneratingTests(true);
    try {
      const schemaStr = JSON.stringify(schemaObject, null, 2);
      const businessContext = testBusinessRules.trim()
        ? `\n\nBusiness Rules:\n${testBusinessRules.trim()}`
        : "";

      const prompt = `Generate API test cases for an endpoint that returns the following JSON Schema:

${schemaStr}${businessContext}

Generate test cases covering:
1. Positive: valid request returning data
2. Negative: invalid inputs, missing fields, wrong types
3. Edge cases: empty response, boundary values
4. Security: unauthorized access, injection attempts

Return a JSON array of test cases with fields: name, type (positive/negative/security), description, expected_status, assertions (object with expected_status, response_not_empty, content_type).`;

      let testCasesData;

      if (testProvider === "local") {
        // Simple local generation based on schema
        testCasesData = generateLocalTestCases(schemaObject, testBusinessRules);
      } else if (testProvider === "gemini") {
        const geminiKey = process.env.REACT_APP_GEMINI_API_KEY;
        // Call backend for AI generation
        const response = await axios.post(`${API}/generate-schema-testcases`, {
          schema: schemaObject,
          business_rules: testBusinessRules || undefined,
          provider: testProvider,
        });
        testCasesData = response.data.test_cases;
      } else {
        const response = await axios.post(`${API}/generate-schema-testcases`, {
          schema: schemaObject,
          business_rules: testBusinessRules || undefined,
          provider: testProvider,
        });
        testCasesData = response.data.test_cases;
      }

      setTestCases(testCasesData);
      toast.success(`Generated ${testCasesData.length} test cases`);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to generate test cases");
    } finally {
      setGeneratingTests(false);
    }
  };

  const generateLocalTestCases = (schema, rules) => {
    const fields = schema.properties ? Object.keys(schema.properties) : [];
    const cases = [
      {
        name: "Valid Request - Data Present",
        type: "positive",
        description: "Request returns data matching the schema",
        expected_status: 200,
        assertions: { expected_status: 200, response_not_empty: true, content_type: "application/json" }
      },
      {
        name: "Valid Request - Empty Response",
        type: "positive",
        description: "Request returns empty/no-records response",
        expected_status: 200,
        assertions: { expected_status: 200, content_type: "application/json" }
      },
      {
        name: "Unauthorized Access",
        type: "security",
        description: "Request without authentication token",
        expected_status: 401,
        assertions: { expected_status: 401 }
      },
      {
        name: "Invalid Input - Missing Required Fields",
        type: "negative",
        description: `Missing required fields: ${fields.slice(0, 3).join(", ") || "N/A"}`,
        expected_status: 400,
        assertions: { expected_status: 400 }
      },
      {
        name: "Resource Not Found",
        type: "negative",
        description: "Request for non-existent resource",
        expected_status: 404,
        assertions: { expected_status: 404 }
      },
    ];
    return cases;
  };

  const copyToClipboard = () => {
    if (!schema) { toast.error("No schema to copy"); return; }
    navigator.clipboard.writeText(schema);
    toast.success("Schema copied to clipboard");
  };

  const resetAll = () => {
    setJsonInput(""); setJsonObject(null); setSchema(""); setSchemaObject(null);
    setTestCases(null); setEmptyResponse(""); setDataResponse(""); setSchemaRequirements("");
    toast.success("Cleared all data");
  };

  const getTypeColor = (type) => {
    const colors = {
      positive: "bg-green-100 text-green-700 border border-green-300",
      negative: "bg-red-100 text-red-700 border border-red-300",
      security: "bg-purple-100 text-purple-700 border border-purple-300",
    };
    return colors[type] || "bg-gray-100 text-gray-700";
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-6">
          <Button variant="outline" onClick={() => navigate("/")} className="mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
          <div className="text-center mb-6">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-3">
              JSON Schema Generator
            </h1>
            <p className="text-slate-600 text-lg">Convert your JSON response to JSON Schema</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Input Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileJson className="w-5 h-5" />
                JSON Input
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {jsonObject ? (
                <div>
                  <JSONViewer data={jsonObject} />
                  <Button onClick={() => setJsonObject(null)} variant="outline" size="sm" className="mt-2">
                    Edit JSON
                  </Button>
                </div>
              ) : (
                <Textarea
                  value={jsonInput}
                  onChange={(e) => setJsonInput(e.target.value)}
                  placeholder={'Enter your JSON response here, e.g.:\n{\n  "id": 1,\n  "name": "John Doe",\n  "email": "john@example.com"\n}'}
                  className="font-mono text-sm min-h-[400px]"
                  rows={20}
                />
              )}
              <div className="flex gap-2">
                <Button onClick={beautifyJSON} variant="outline" className="flex-1">
                  Beautify JSON
                </Button>
                <Button
                  onClick={handleGenerateSchemaClick}
                  disabled={loading}
                  className="flex-1 bg-blue-600 hover:bg-blue-700"
                >
                  {loading ? "Generating..." : "Generate Schema"}
                </Button>
                <Button
                  onClick={resetAll}
                  variant="outline"
                  className="border-red-300 text-red-600 hover:bg-red-50"
                >
                  <RotateCcw className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Output Section */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <FileJson className="w-5 h-5" />
                  Generated Schema
                </span>
                <div className="flex gap-2">
                  {schema && (
                    <Button size="sm" variant="outline" onClick={copyToClipboard}>
                      <Copy className="w-4 h-4 mr-2" />
                      Copy
                    </Button>
                  )}
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {schemaObject ? (
                <JSONViewer data={schemaObject} />
              ) : (
                <div className="flex items-center justify-center h-[400px] border-2 border-dashed rounded-lg bg-slate-50">
                  <div className="text-center">
                    <FileJson className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                    <p className="text-slate-500">Generated schema will appear here</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Generated Test Cases */}
        {testCases && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-600" />
                Generated Test Cases ({testCases.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {testCases.map((tc, idx) => (
                  <div key={idx} className="border rounded-lg p-4 bg-white">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getTypeColor(tc.type)}`}>
                            {(tc.type || "positive").toUpperCase()}
                          </span>
                          <span className="font-semibold text-sm">{tc.name}</span>
                        </div>
                        <p className="text-sm text-slate-500">{tc.description}</p>
                      </div>
                      <div className="text-right text-sm">
                        <span className="font-semibold text-slate-600">Expected: </span>
                        <span className="font-mono text-blue-600">{tc.expected_status}</span>
                      </div>
                    </div>
                    {tc.assertions && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(tc.assertions).map(([k, v]) => (
                          <span key={k} className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                            {k}: {String(v)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Generate Schema Dialog */}
      <Dialog open={showSchemaDialog} onOpenChange={setShowSchemaDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Generate Schema with AI</DialogTitle>
            <DialogDescription>
              Choose an AI provider and optionally describe different response scenarios so the AI can generate a unified schema that handles all cases.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div>
              <Label className="mb-2 block font-semibold">AI Provider</Label>
              <Select value={schemaProvider} onValueChange={setSchemaProvider}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI (GPT-4)</SelectItem>
                  <SelectItem value="gemini">Google Gemini</SelectItem>
                  <SelectItem value="local">Local (Rule-based)</SelectItem>
                </SelectContent>
              </Select>
              {schemaProvider === "local" && (
                <p className="text-xs text-slate-500 mt-1">Uses built-in genson engine — no API key required.</p>
              )}
            </div>
            <div>
              <Label className="mb-2 block font-semibold">Empty / No Records Response (optional)</Label>
              <Textarea
                value={emptyResponse}
                onChange={(e) => setEmptyResponse(e.target.value)}
                rows={4}
                className="font-mono text-sm"
                placeholder={'e.g. {"data": [], "total": 0, "message": "No records found"}'}
              />
              <p className="text-xs text-slate-500 mt-1">Paste the response your API returns when there are no records.</p>
            </div>
            <div>
              <Label className="mb-2 block font-semibold">Data Present Response (optional)</Label>
              <Textarea
                value={dataResponse}
                onChange={(e) => setDataResponse(e.target.value)}
                rows={4}
                className="font-mono text-sm"
                placeholder={'e.g. {"data": [{"id": 1, "name": "Item"}], "total": 1}'}
              />
              <p className="text-xs text-slate-500 mt-1">Paste the response your API returns when data exists.</p>
            </div>
            <div>
              <Label className="mb-2 block font-semibold">Additional Requirements (optional)</Label>
              <Textarea
                value={schemaRequirements}
                onChange={(e) => setSchemaRequirements(e.target.value)}
                rows={3}
                className="font-mono text-sm"
                placeholder={"e.g.\n- id must be a positive integer\n- email must follow email format\n- status can only be 'active' or 'inactive'"}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSchemaDialog(false)}>
              Cancel
            </Button>
            <Button onClick={() => handleGenerateSchema(true)} className="bg-blue-600 hover:bg-blue-700">
              <Sparkles className="w-4 h-4 mr-2" />
              Generate Schema
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Generate Test Cases Dialog */}
      <Dialog open={showTestCasesDialog} onOpenChange={setShowTestCasesDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Generate Test Cases</DialogTitle>
            <DialogDescription>
              Choose an AI provider and optionally add business requirements to generate targeted test cases for this schema.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-4">
            <div>
              <Label className="mb-2 block font-semibold">AI Provider</Label>
              <Select value={testProvider} onValueChange={setTestProvider}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI (GPT-4)</SelectItem>
                  <SelectItem value="gemini">Google Gemini</SelectItem>
                  <SelectItem value="local">Local (Rule-based)</SelectItem>
                </SelectContent>
              </Select>
              {testProvider === "local" && (
                <p className="text-xs text-slate-500 mt-1">Uses built-in rule-based engine — no API key required.</p>
              )}
            </div>
            <div>
              <Label className="mb-2 block font-semibold">Business Requirements / Validation Rules</Label>
              <Textarea
                value={testBusinessRules}
                onChange={(e) => setTestBusinessRules(e.target.value)}
                rows={6}
                className="font-mono text-sm"
                placeholder={`Examples:\n- id must be a positive integer\n- name: 3-50 characters\n- status: only "active" or "inactive"\n- If no records, response must have empty array\n- Pagination: page and limit are required query params`}
              />
              <p className="text-xs text-slate-500 mt-1">
                Leave empty to generate generic test cases, or add your rules for targeted validation scenarios.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setTestBusinessRules(""); handleGenerateTestCases(); }}>
              Skip & Generate
            </Button>
            <Button onClick={handleGenerateTestCases} className="bg-purple-600 hover:bg-purple-700">
              <Sparkles className="w-4 h-4 mr-2" />
              Generate with Rules
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default JSONSchemaGenerator;
