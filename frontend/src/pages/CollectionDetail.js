import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import { ArrowLeft, Play, CheckCircle, XCircle, Clock, Layers, ExternalLink, Download } from "lucide-react";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import CollectionVariables from "../components/CollectionVariables";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Component to show detailed run results
const RunDetails = ({ runId, collectionId }) => {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const response = await axios.get(`${API}/collections/${collectionId}/runs/${runId}`);
        setDetails(response.data);
      } catch (error) {
        toast.error("Failed to load run details");
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [runId, collectionId]);

  const syntaxHighlight = (json) => {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, null, 2);
    }
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/(".+?")(:?)|(\btrue\b|\bfalse\b|\bnull\b)|(-?\d+\.?\d*)/g, function (match, p1, p2, p3, p4) {
      let cls = 'text-slate-700';
      if (p1 && p2) {
        cls = 'text-blue-600 font-medium';
      } else if (p1) {
        cls = 'text-green-600';
      } else if (p3) {
        cls = 'text-purple-600 font-medium';
      } else if (p4) {
        cls = 'text-orange-600';
      }
      return `<span class="${cls}">${match}</span>`;
    });
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

  const getTypeColor = (type) => {
    const colors = {
      positive: "bg-green-500/10 text-green-700 border-green-500/20",
      negative: "bg-red-500/10 text-red-700 border-red-500/20",
      symmetric: "bg-blue-500/10 text-blue-700 border-blue-500/20",
      security: "bg-purple-500/10 text-purple-700 border-purple-500/20"
    };
    return colors[type] || "bg-gray-500/10 text-gray-700";
  };

  if (loading) {
    return <div className="text-center py-4 text-slate-500">Loading details...</div>;
  }

  if (!details || !details.results) {
    return <div className="text-center py-4 text-slate-500">No details available</div>;
  }

  // Group by test type
  const groupedResults = details.results.reduce((acc, result) => {
    if (!acc[result.test_type]) {
      acc[result.test_type] = [];
    }
    acc[result.test_type].push(result);
    return acc;
  }, {});

  return (
    <div className="space-y-4 pt-4">
      {["positive", "negative", "symmetric", "security"].map(type => {
        const resultsOfType = groupedResults[type] || [];
        if (resultsOfType.length === 0) return null;

        return (
          <Card key={type} className="border-l-4" style={{
            borderLeftColor: type === 'positive' ? '#16a34a' : 
                           type === 'negative' ? '#dc2626' : 
                           type === 'symmetric' ? '#2563eb' : '#9333ea'
          }}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Badge className={getTypeColor(type)}>{type.toUpperCase()}</Badge>
                <span className="text-sm font-normal text-slate-500">
                  ({resultsOfType.length} test{resultsOfType.length !== 1 ? 's' : ''})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Accordion type="single" collapsible>
                {resultsOfType.map((result, idx) => (
                  <AccordionItem key={idx} value={`${type}-${idx}`}>
                    <AccordionTrigger>
                      <div className="flex items-center gap-2 w-full">
                        {result.passed ? (
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-600" />
                        )}
                        <div className="flex-1 text-left">
                          <div className="font-medium">{result.test_name}</div>
                          <div className="text-xs text-slate-500">API: {result.api_name}</div>
                        </div>
                        <Badge variant={result.passed ? "default" : "destructive"}>
                          {result.response_status || "Error"}
                        </Badge>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="space-y-4 pt-2">
                        <div className="flex items-center gap-4 text-sm">
                          <span className="font-semibold">Method:</span>
                          <Badge className={getMethodColor(result.request_method)}>
                            {result.request_method}
                          </Badge>
                          <span className="font-semibold">Time:</span>
                          <span>{result.response_time ? `${(result.response_time * 1000).toFixed(0)}ms` : "N/A"}</span>
                        </div>

                        {result.error && (
                          <div className="bg-red-50 border border-red-200 p-3 rounded">
                            <span className="font-semibold text-red-600">Error:</span>
                            <p className="text-sm text-red-600 mt-1">{result.error}</p>
                          </div>
                        )}

                        {/* Request Details */}
                        <div>
                          <h4 className="font-semibold mb-2">Request</h4>
                          <div className="bg-slate-50 p-3 rounded space-y-3">
                            <div>
                              <span className="text-sm font-semibold">URL:</span>
                              <div className="font-mono text-xs break-all mt-1 bg-white p-2 rounded border">
                                {result.request_url}
                              </div>
                            </div>
                            {result.request_headers && Object.keys(result.request_headers).length > 0 && (
                              <div>
                                <span className="text-sm font-semibold">Headers:</span>
                                <div className="bg-white border rounded p-3 mt-1">
                                  <pre 
                                    className="text-xs font-mono leading-relaxed overflow-auto"
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
                                <div className="bg-white border rounded p-3 mt-1">
                                  <pre 
                                    className="text-xs font-mono leading-relaxed overflow-auto"
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
                                <div className="bg-white border rounded p-3 mt-1">
                                  <pre 
                                    className="text-xs font-mono leading-relaxed overflow-auto"
                                    dangerouslySetInnerHTML={{
                                      __html: syntaxHighlight(result.request_body)
                                    }}
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Response Details */}
                        <div>
                          <h4 className="font-semibold mb-2">Response</h4>
                          {result.response_body && (
                            <div className="bg-white border rounded p-4 overflow-auto max-h-60">
                              <pre 
                                className="text-xs font-mono leading-relaxed"
                                dangerouslySetInnerHTML={{
                                  __html: syntaxHighlight(
                                    typeof result.response_body === 'string' 
                                      ? result.response_body 
                                      : result.response_body
                                  )
                                }}
                              />
                            </div>
                          )}
                        </div>
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
  );
};

const CollectionDetail = () => {
  const { collectionId } = useParams();
  const navigate = useNavigate();
  const [collection, setCollection] = useState(null);
  const [runHistory, setRunHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState(null);

  useEffect(() => {
    fetchCollectionDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionId]);

  const fetchCollectionDetails = async () => {
    try {
      const [collectionRes, historyRes] = await Promise.all([
        axios.get(`${API}/collections/${collectionId}`),
        axios.get(`${API}/collections/${collectionId}/runs`)
      ]);
      setCollection(collectionRes.data);
      setRunHistory(historyRes.data);
    } catch (error) {
      toast.error("Failed to fetch collection details");
      navigate("/collections");
    } finally {
      setLoading(false);
    }
  };

  const handleRunCollection = async () => {
    setRunning(true);
    try {
      const response = await axios.post(`${API}/collections/${collectionId}/run`);
      toast.success(`Collection executed: ${response.data.passed_tests}/${response.data.total_tests} tests passed`);
      // Refresh collection details and history
      await fetchCollectionDetails();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to run collection");
    } finally {
      setRunning(false);
    }
  };

  const handleDownloadReport = () => {
    if (!collection.latest_run) {
      toast.error("No test results available. Please run collection tests first.");
      return;
    }
    window.open(`${API}/collections/${collectionId}/report/download`, '_blank');
    toast.success("Downloading HTML report...");
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

  const getTypeColor = (type) => {
    const colors = {
      positive: "bg-green-500/10 text-green-700 border-green-500/20",
      negative: "bg-red-500/10 text-red-700 border-red-500/20",
      symmetric: "bg-blue-500/10 text-blue-700 border-blue-500/20",
      security: "bg-purple-500/10 text-purple-700 border-purple-500/20"
    };
    return colors[type] || "bg-gray-500/10 text-gray-700";
  };

  const syntaxHighlight = (json) => {
    if (typeof json !== 'string') {
      json = JSON.stringify(json, null, 2);
    }
    json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return json.replace(/(".+?")(:?)|(\\btrue\\b|\\bfalse\\b|\\bnull\\b)|(-?\\d+\\.?\\d*)/g, function (match, p1, p2, p3, p4) {
      let cls = 'text-slate-700';
      if (p1 && p2) {
        cls = 'text-blue-600 font-medium';
      } else if (p1) {
        cls = 'text-green-600';
      } else if (p3) {
        cls = 'text-purple-600 font-medium';
      } else if (p4) {
        cls = 'text-orange-600';
      }
      return `<span class="${cls}">${match}</span>`;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <Button 
          variant="outline" 
          onClick={() => navigate("/collections")} 
          className="mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Collections
        </Button>

        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-2">
            {collection.name}
          </h1>
          <p className="text-slate-600">{collection.description || "No description"}</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
          <Card className="border-l-4 border-l-blue-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">APIs in Collection</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-blue-600">{collection.apis.length}</p>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-purple-500">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Total Runs</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-purple-600">{collection.total_runs || 0}</p>
            </CardContent>
          </Card>

          {collection.latest_run ? (
            <>
              <Card className="border-l-4 border-l-slate-500">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Latest: Total Tests</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-slate-600">{collection.latest_run.total_tests}</p>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-green-500">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Latest: Passed</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-green-600">{collection.latest_run.passed_tests}</p>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-red-500">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Latest: Failed</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-2xl font-bold text-red-600">{collection.latest_run.failed_tests}</p>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card className="col-span-3 border-l-4 border-l-slate-300">
              <CardContent className="flex items-center justify-center py-6">
                <p className="text-slate-500 text-sm">No runs yet - Click "Run All Tests" to start</p>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Run Button */}
        <div className="mb-6 flex gap-4">
          <Button 
            onClick={handleRunCollection}
            disabled={running || collection.apis.length === 0}
            className="bg-green-600 hover:bg-green-700"
            size="lg"
          >
            {running ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Running Tests...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Run All Tests in Collection
              </>
            )}
          </Button>

          <Button 
            onClick={handleDownloadReport}
            disabled={!collection.latest_run}
            variant="outline"
            className="border-orange-600 text-orange-600 hover:bg-orange-50"
            size="lg"
          >
            <Download className="w-4 h-4 mr-2" />
            Download HTML Report
          </Button>
        </div>

        {/* Collection Variables Section */}
        <div className="mb-6">
          <CollectionVariables collectionId={collectionId} onUpdate={fetchCollectionDetails} />
        </div>

        {/* APIs in Collection */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>APIs in this Collection</CardTitle>
            <CardDescription>
              {collection.apis.length} API{collection.apis.length !== 1 ? 's' : ''} will be tested
            </CardDescription>
          </CardHeader>
          <CardContent>
            {collection.apis.length === 0 ? (
              <p className="text-slate-500 text-center py-8">No APIs in this collection</p>
            ) : (
              <div className="space-y-3">
                {collection.apis.map((api, index) => (
                  <div 
                    key={api.id} 
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-slate-500 font-mono text-sm">#{index + 1}</span>
                        <h3 className="font-semibold">{api.name}</h3>
                        <Badge className={getMethodColor(api.method)}>{api.method}</Badge>
                      </div>
                      <p className="text-sm text-slate-600 font-mono">{api.url}</p>
                      <p className="text-xs text-slate-500 mt-1">{api.test_count} test case{api.test_count !== 1 ? 's' : ''}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate(`/api/${api.id}?from=collection&collectionId=${collectionId}`)}
                    >
                      <ExternalLink className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Run History */}
        {runHistory.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Run History</CardTitle>
              <CardDescription>Last 10 collection runs - Click to see details</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {runHistory.map((run) => (
                  <Accordion key={run.id} type="single" collapsible>
                    <AccordionItem value={run.id}>
                      <AccordionTrigger>
                        <div className="flex items-center justify-between w-full pr-4">
                          <div className="flex items-center gap-4">
                            <Clock className="w-4 h-4 text-slate-400" />
                            <div>
                              <p className="text-sm font-medium">
                                {new Date(run.executed_at).toLocaleString()}
                              </p>
                              <p className="text-xs text-slate-500">
                                {run.total_apis} APIs • {run.total_tests} tests • {run.total_time.toFixed(2)}s
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-green-600 border-green-600">
                              ✓ {run.passed_tests}
                            </Badge>
                            <Badge variant="outline" className="text-red-600 border-red-600">
                              ✗ {run.failed_tests}
                            </Badge>
                          </div>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <RunDetails runId={run.id} collectionId={collectionId} />
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default CollectionDetail;
