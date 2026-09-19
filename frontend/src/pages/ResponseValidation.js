import { useState } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, CheckCircle, XCircle, Copy, Sparkles, ChevronDown } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ResponseValidation = () => {
  const navigate = useNavigate();
  const [contractJson, setContractJson] = useState("");
  const [responseJson, setResponseJson] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [provider, setProvider] = useState("openai");

  const beautifyJson = (text, setter) => {
    try {
      const parsed = JSON.parse(text);
      setter(JSON.stringify(parsed, null, 2));
      toast.success("JSON beautified successfully");
    } catch (error) {
      toast.error("Invalid JSON format");
    }
  };

  const handleValidate = async () => {
    if (!contractJson.trim() || !responseJson.trim()) {
      toast.error("Both Contract and Response JSON are required");
      return;
    }

    try {
      const contract = JSON.parse(contractJson);
      const response = JSON.parse(responseJson);

      setLoading(true);
      const res = await axios.post(`${API}/validate-response`, {
        contract_json: contract,
        response_json: response,
        provider,
      });

      setResult(res.data);
      toast.success("Validation completed");
    } catch (error) {
      if (error instanceof SyntaxError) {
        toast.error("Invalid JSON format in one of the inputs");
      } else {
        toast.error(error.response?.data?.detail || "Validation failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (!result) return;

    const output = result.is_valid
      ? result.message
      : `Validation Failed:\n\n${result.discrepancies.map((d, i) => `${i + 1}. ${d}`).join("\n")}`;

    navigator.clipboard.writeText(output);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-6">
          <Button
            variant="outline"
            onClick={() => navigate("/")}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>

          <div className="text-center mb-6">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-2">
              Response Validation
            </h1>
            <p className="text-slate-600">
              Validate API responses against contract specifications using AI
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Contract JSON Input */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Contract JSON</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => beautifyJson(contractJson, setContractJson)}
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Beautify
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={contractJson}
                onChange={(e) => setContractJson(e.target.value)}
                placeholder='{"name": "string", "age": "number", "email": "string"}'
                className="font-mono text-sm min-h-[400px] resize-none"
              />
            </CardContent>
          </Card>

          {/* Response JSON Input */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Actual Response JSON</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => beautifyJson(responseJson, setResponseJson)}
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  Beautify
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Textarea
                value={responseJson}
                onChange={(e) => setResponseJson(e.target.value)}
                placeholder='{"name": "John Doe", "age": 30, "email": "john@example.com"}'
                className="font-mono text-sm min-h-[400px] resize-none"
              />
            </CardContent>
          </Card>
        </div>

        {/* Verify Button */}
        <div className="flex justify-center items-center gap-3 mb-6">
          <div className="relative">
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="appearance-none border border-slate-300 rounded-lg px-4 py-3 pr-10 text-sm font-medium bg-white text-slate-700 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="openai">OpenAI GPT-4</option>
              <option value="gemini">Google Gemini</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
          </div>
          <Button
            onClick={handleValidate}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 px-8 py-3 text-lg"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2"></div>
                Validating...
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5 mr-2" />
                Verify Contract
              </>
            )}
          </Button>
        </div>

        {/* Results */}
        {result && (
          <Card className={`border-2 ${result.is_valid ? "border-green-500" : "border-red-500"}`}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span className="flex items-center gap-2">
                  {result.is_valid ? (
                    <>
                      <CheckCircle className="w-6 h-6 text-green-600" />
                      <span className="text-green-600">Validation Passed</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-6 h-6 text-red-600" />
                      <span className="text-red-600">Validation Failed</span>
                    </>
                  )}
                </span>
                <Button size="sm" variant="outline" onClick={copyToClipboard}>
                  <Copy className="w-4 h-4 mr-2" />
                  Copy Output
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {result.is_valid ? (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <p className="text-green-800 font-medium">{result.message}</p>
                </div>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <h3 className="font-semibold text-red-800 mb-3">
                    Contract Discrepancies Found:
                  </h3>
                  <ul className="space-y-2">
                    {result.discrepancies.map((discrepancy, index) => (
                      <li
                        key={index}
                        className="flex items-start gap-2 text-red-700"
                      >
                        <span className="font-bold mt-0.5">{index + 1}.</span>
                        <span>{discrepancy}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default ResponseValidation;
