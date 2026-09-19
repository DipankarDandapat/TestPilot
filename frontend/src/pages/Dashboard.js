import { useState, useEffect } from "react";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "../components/ui/alert-dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Eye, Trash2, ExternalLink, Server, CheckCircle, XCircle, Play, Sparkles, Terminal, ChevronLeft, ChevronRight, Layers, FileJson, ClipboardCheck, Code } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [apis, setApis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [curlCommand, setCurlCommand] = useState("");
  const [showCurlSection, setShowCurlSection] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [apiToDelete, setApiToDelete] = useState(null);
  const [stats, setStats] = useState(null);
  const [currentPage, setCurrentPage] = useState(parseInt(searchParams.get('page')) || 1);
  const [totalApis, setTotalApis] = useState(0);
  const [projects, setProjects] = useState([]);
  const [showProjectSuggestions, setShowProjectSuggestions] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const itemsPerPage = 10;
  const [formData, setFormData] = useState({
    name: "",
    url: "",
    method: "GET",
    headers: "",
    query_params: "",
    body: "",
    description: "",
    project_name: ""
  });

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    const pageFromUrl = parseInt(searchParams.get('page')) || 1;
    if (pageFromUrl !== currentPage) {
      setCurrentPage(pageFromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    setSearchParams({ page: currentPage.toString() }, { replace: true });
    fetchAPIs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentPage, searchQuery]);

  const fetchProjects = async () => {
    try {
      const res = await axios.get(`${API}/projects`);
      setProjects(res.data);
    } catch (error) {
      console.error("Failed to fetch projects");
    }
  };

  const fetchAPIs = async () => {
    try {
      let apiUrl = `${API}/apis?page=${currentPage}&limit=${itemsPerPage}`;
      let countUrl = `${API}/apis/count`;
      if (searchQuery) {
        apiUrl += `&search=${encodeURIComponent(searchQuery)}`;
        countUrl += `?search=${encodeURIComponent(searchQuery)}`;
      }
      const [apisRes, statsRes, countRes] = await Promise.all([
        axios.get(apiUrl),
        axios.get(`${API}/stats`),
        axios.get(countUrl)
      ]);
      setApis(apisRes.data);
      setStats(statsRes.data);
      setTotalApis(countRes.data.total);
    } catch (error) {
      toast.error("Failed to fetch APIs");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.project_name.trim()) {
      toast.error("Project Name is required");
      return;
    }

    try {
      let headers = {};
      let query_params = null;
      let body = null;

      // Validate and parse Headers
      if (formData.headers.trim()) {
        try {
          headers = JSON.parse(formData.headers);
          if (typeof headers !== 'object' || Array.isArray(headers)) {
            toast.error("Headers must be a valid JSON object");
            return;
          }
        } catch (err) {
          toast.error("Invalid JSON in Headers field. Please check your syntax.");
          return;
        }
      }

      // Validate and parse Query Parameters
      if (formData.query_params.trim()) {
        try {
          query_params = JSON.parse(formData.query_params);
          if (typeof query_params !== 'object' || Array.isArray(query_params)) {
            toast.error("Query Parameters must be a valid JSON object");
            return;
          }
        } catch (err) {
          toast.error("Invalid JSON in Query Parameters field. Please check your syntax.");
          return;
        }
      }

      // Validate and parse Body (only for POST, PUT, PATCH)
      if (formData.body.trim() && ['POST', 'PUT', 'PATCH'].includes(formData.method)) {
        try {
          body = JSON.parse(formData.body);
        } catch (err) {
          toast.error("Invalid JSON in Body field. Please check your syntax.");
          return;
        }
      }

      await axios.post(`${API}/apis`, {
        name: formData.name,
        url: formData.url,
        method: formData.method,
        headers,
        query_params,
        body,
        description: formData.description,
        project_name: formData.project_name
      });

      toast.success("API added successfully");
      setDialogOpen(false);
      setFormData({
        name: "",
        url: "",
        method: "GET",
        headers: "",
        query_params: "",
        body: "",
        description: "",
        project_name: ""
      });
      fetchProjects();
      setCurrentPage(1); // Go to first page to see the new API
      fetchAPIs();
    } catch (error) {
      console.error("Error adding API:", error);
      toast.error(error.response?.data?.detail || error.message || "Failed to add API");
    }
  };

  const handleDelete = async () => {
    if (!apiToDelete) return;

    try {
      await axios.delete(`${API}/apis/${apiToDelete.id}`);
      toast.success("API deleted successfully");
      setDeleteDialogOpen(false);
      setApiToDelete(null);
      // If current page becomes empty after delete, go to previous page
      if (apis.length === 1 && currentPage > 1) {
        setCurrentPage(currentPage - 1);
      } else {
        fetchAPIs();
      }
    } catch (error) {
      toast.error("Failed to delete API");
    }
  };

  const openDeleteDialog = (api, e) => {
    e.stopPropagation();
    setApiToDelete(api);
    setDeleteDialogOpen(true);
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

  // Auto-resize textarea
  const handleTextareaChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
  };

  const handleCurlImport = async () => {
    if (!curlCommand.trim()) {
      toast.error("Please enter a cURL command");
      return;
    }

    try {
      const response = await axios.post(`${API}/parse-curl`, {
        curl_command: curlCommand
      });

      const parsed = response.data;
      
      setFormData(prev => ({
        ...prev,
        url: parsed.url || "",
        method: parsed.method || "GET",
        headers: parsed.headers ? JSON.stringify(parsed.headers, null, 2) : "",
        query_params: parsed.query_params ? JSON.stringify(parsed.query_params, null, 2) : "",
        body: parsed.body ? JSON.stringify(parsed.body, null, 2) : "",
      }));

      setCurlCommand("");
      setShowCurlSection(false);
      toast.success("cURL command parsed successfully");
    } catch (error) {
      console.error("Error parsing cURL:", error);
      toast.error(error.response?.data?.detail || "Failed to parse cURL command");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        <div className="mb-8">
          <div className="text-center mb-6">
            <h1 className="text-5xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-3" style={{lineHeight: '1.5'}} data-testid="dashboard-title">
              AI Agent For API Testing
            </h1>
            <p className="text-slate-600 text-lg" data-testid="dashboard-subtitle">
              Generate and run AI-powered test cases for your APIs
            </p>
          </div>
          
          <div className="flex justify-center gap-3">
            <Button 
              onClick={() => navigate("/response-validation")} 
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              <ClipboardCheck className="w-4 h-4 mr-2" />
              Response Validation
            </Button>

            <Button 
              onClick={() => navigate("/contract-testing")} 
              className="bg-teal-600 hover:bg-teal-700"
            >
              <FileJson className="w-4 h-4 mr-2" />
              Contract Testing
            </Button>

            <Button 
              onClick={() => navigate("/json-schema-generator")} 
              className="bg-orange-600 hover:bg-orange-700"
            >
              <Code className="w-4 h-4 mr-2" />
              JSON Schema
            </Button>

            <Button 
              onClick={() => navigate("/collections")} 
              className="bg-purple-600 hover:bg-purple-700"
            >
              <Layers className="w-4 h-4 mr-2" />
              API Collections
            </Button>

            <Dialog open={dialogOpen} onOpenChange={(open) => {
              setDialogOpen(open);
              if (!open) {
                setShowCurlSection(false);
                setCurlCommand("");
              }
            }}>
              <DialogTrigger asChild>
                <Button className="bg-blue-600 hover:bg-blue-700" data-testid="add-api-button">
                  <Plus className="w-4 h-4 mr-2" />
                  Add API
                </Button>
              </DialogTrigger>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="add-api-dialog">
              <DialogHeader>
                <DialogTitle className="text-2xl flex items-center gap-2">
                  <i className="fas fa-plus-circle text-blue-600"></i>
                  Add New API
                </DialogTitle>
                <DialogDescription>
                  Configure your API endpoint for testing
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Import cURL Section */}
                <div className="border border-dashed border-slate-300 rounded-lg p-3">
                  {!showCurlSection ? (
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full"
                      onClick={() => setShowCurlSection(true)}
                      data-testid="import-curl-button"
                    >
                      <Terminal className="w-4 h-4 mr-2" />
                      Import from cURL
                    </Button>
                  ) : (
                    <div className="space-y-2">
                      <Label className="text-sm font-medium flex items-center gap-2">
                        <Terminal className="w-4 h-4" />
                        Paste cURL Command
                      </Label>
                      <Textarea
                        value={curlCommand}
                        onChange={(e) => setCurlCommand(e.target.value)}
                        placeholder='curl -X POST "https://api.example.com/users" -H "Content-Type: application/json" -d {"name": "John"}'
                        className="font-mono text-sm min-h-[100px]"
                        rows={4}
                      />
                      <div className="flex gap-2">
                        <Button type="button" size="sm" onClick={handleCurlImport}>
                          Parse & Fill
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => { setShowCurlSection(false); setCurlCommand(""); }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  <Label htmlFor="project_name" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-folder text-slate-600"></i>
                    Project Name <span className="text-red-500">*</span>
                  </Label>
                  <div className="relative">
                    <Input
                      id="project_name"
                      data-testid="api-project-name-input"
                      value={formData.project_name}
                      onChange={(e) => {
                        setFormData({ ...formData, project_name: e.target.value });
                        setShowProjectSuggestions(true);
                      }}
                      onFocus={() => setShowProjectSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowProjectSuggestions(false), 200)}
                      placeholder="Enter or select project name"
                      autoComplete="off"
                      required
                    />
                    {showProjectSuggestions && projects.filter(p => p.toLowerCase().includes((formData.project_name || '').toLowerCase())).length > 0 && (
                      <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-40 overflow-y-auto">
                        {projects
                          .filter(p => p.toLowerCase().includes((formData.project_name || '').toLowerCase()))
                          .map((p) => (
                            <div
                              key={p}
                              className="px-3 py-2 hover:bg-slate-100 cursor-pointer text-sm"
                              onMouseDown={() => {
                                setFormData({ ...formData, project_name: p });
                                setShowProjectSuggestions(false);
                              }}
                            >
                              {p}
                            </div>
                          ))}
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <Label htmlFor="name" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-tag text-slate-600"></i>
                    API Name
                  </Label>
                  <Input
                    id="name"
                    data-testid="api-name-input"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Get Users API"
                    required
                  />
                </div>
                
                <div>
                  <Label htmlFor="url" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-link text-slate-600"></i>
                    URL
                  </Label>
                  <Input
                    id="url"
                    data-testid="api-url-input"
                    value={formData.url}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                    placeholder="https://api.example.com/users"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="method" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-code-branch text-slate-600"></i>
                    Method
                  </Label>
                  <Select
                    value={formData.method}
                    onValueChange={(value) => setFormData({ ...formData, method: value })}
                  >
                    <SelectTrigger data-testid="api-method-select">
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
                  <Label htmlFor="headers" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-heading text-slate-600"></i>
                    Headers (JSON)
                  </Label>
                  <Textarea
                    id="headers"
                    data-testid="api-headers-input"
                    value={formData.headers}
                    onChange={(e) => {
                      handleTextareaChange('headers', e.target.value);
                      e.target.style.height = 'auto';
                      e.target.style.height = e.target.scrollHeight + 'px';
                    }}
                    placeholder='{"Content-Type": "application/json"}'
                    className="font-mono text-sm min-h-[80px] resize-none"
                    style={{ height: 'auto' }}
                  />
                </div>

                <div>
                  <Label htmlFor="query_params" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-search text-slate-600"></i>
                    Query Parameters (JSON)
                  </Label>
                  <Textarea
                    id="query_params"
                    data-testid="api-query-params-input"
                    value={formData.query_params}
                    onChange={(e) => {
                      handleTextareaChange('query_params', e.target.value);
                      e.target.style.height = 'auto';
                      e.target.style.height = e.target.scrollHeight + 'px';
                    }}
                    placeholder='{"page": "1", "limit": "10"}'
                    className="font-mono text-sm min-h-[80px] resize-none"
                    style={{ height: 'auto' }}
                  />
                </div>

                <div>
                  <Label htmlFor="body" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-database text-slate-600"></i>
                    Body (JSON)
                  </Label>
                  <Textarea
                    id="body"
                    data-testid="api-body-input"
                    value={formData.body}
                    onChange={(e) => {
                      handleTextareaChange('body', e.target.value);
                      e.target.style.height = 'auto';
                      e.target.style.height = e.target.scrollHeight + 'px';
                    }}
                    placeholder='{"name": "John", "email": "john@example.com"}'
                    className="font-mono text-sm min-h-[80px] resize-none"
                    style={{ height: 'auto' }}
                    disabled={formData.method === 'GET' || formData.method === 'DELETE'}
                  />
                  {(formData.method === 'GET' || formData.method === 'DELETE') && (
                    <p className="text-xs text-slate-500 mt-1">
                      Body is not allowed for {formData.method} requests
                    </p>
                  )}
                </div>

                <div>
                  <Label htmlFor="description" className="flex items-center gap-2" style={{lineHeight: '2'}}>
                    <i className="fas fa-file-alt text-slate-600"></i>
                    Description (Optional)
                  </Label>
                  <Textarea
                    id="description"
                    data-testid="api-description-input"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="What does this API do?"
                    rows={2}
                  />
                </div>

                <div className="flex gap-2 pt-2">
                  <Button type="submit" className="flex-1" data-testid="submit-api-button">
                    <i className="fas fa-check mr-2"></i>
                    Add API
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={() => setDialogOpen(false)}
                    data-testid="cancel-api-button"
                  >
                    <i className="fas fa-times mr-2"></i>
                    Cancel
                  </Button>
                </div>
              </form>
            </DialogContent>
          </Dialog>
          </div>
        </div>

        {/* Overall Statistics Dashboard - Only show if APIs exist */}
        {!loading && apis.length > 0 && stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <Card className="border-l-4 border-l-purple-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-purple-600" />
                  Total AI Generated Test Cases
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-purple-600">{stats.total_test_cases}</p>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-blue-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Play className="w-4 h-4 text-blue-600" />
                  Total Test Runs
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-blue-600">{stats.total_test_runs}</p>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-green-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-green-600" />
                  Total Passed
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-green-600">{stats.total_passed}</p>
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-red-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-red-600" />
                  Total Failed
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-red-600">{stats.total_failed}</p>
              </CardContent>
            </Card>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-64" data-testid="loading-indicator">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        ) : apis.length === 0 ? (
          <Card className="border-2 border-dashed" data-testid="empty-state">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <Server className="w-16 h-16 text-slate-300 mb-4" />
              <h3 className="text-xl font-semibold text-slate-700 mb-2">No APIs yet</h3>
              <p className="text-slate-500 mb-4">Add your first API to start testing</p>
              <Button onClick={() => setDialogOpen(true)} data-testid="empty-add-api-button">
                <Plus className="w-4 h-4 mr-2" />
                Add API
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Search Bar */}
            <div className="flex items-center gap-3 mb-4">
              <div className="relative flex-1 max-w-md">
                <Input
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setCurrentPage(1);
                  }}
                  placeholder="Search by project, name, method, or URL..."
                  className="pl-9"
                />
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              {searchQuery && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => { setSearchQuery(""); setCurrentPage(1); }}
                >
                  Clear
                </Button>
              )}
            </div>

            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full" data-testid="apis-grid">
                    <thead>
                      <tr className="border-b bg-slate-50">
                        <th className="text-left px-6 py-4 text-sm font-semibold text-slate-600">Project</th>
                        <th className="text-left px-6 py-4 text-sm font-semibold text-slate-600">Name</th>
                        <th className="text-left px-6 py-4 text-sm font-semibold text-slate-600">Method</th>
                        <th className="text-left px-6 py-4 text-sm font-semibold text-slate-600">URL</th>
                        <th className="text-left px-6 py-4 text-sm font-semibold text-slate-600">Description</th>
                        <th className="text-right px-6 py-4 text-sm font-semibold text-slate-600">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {apis.map((api) => (
                        <tr
                          key={api.id}
                          className="border-b last:border-b-0 hover:bg-slate-50 cursor-pointer transition-colors"
                          onClick={() => navigate(`/api/${api.id}?page=${currentPage}`)}
                          data-testid={`api-card-${api.id}`}
                        >
                          <td className="px-6 py-4">
                            <span className="text-sm text-slate-600 bg-blue-50 px-2 py-1 rounded">
                              {api.project_name || "—"}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-slate-800">{api.name}</span>
                              <ExternalLink className="w-3.5 h-3.5 text-slate-400 opacity-0 group-hover:opacity-100" />
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getMethodColor(api.method)}`}>
                              {api.method}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm text-slate-600 font-mono bg-slate-100 px-2 py-1 rounded max-w-xs truncate inline-block">
                              {api.url}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm text-slate-500 line-clamp-1">
                              {api.description || "—"}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  navigate(`/api/${api.id}?page=${currentPage}`);
                                }}
                                data-testid={`view-api-${api.id}`}
                              >
                                <Eye className="w-4 h-4 mr-1" />
                                View
                              </Button>
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={(e) => openDeleteDialog(api, e)}
                                data-testid={`delete-api-${api.id}`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            {/* Pagination Controls */}
            {totalApis > itemsPerPage && (
              <div className="flex items-center justify-center gap-4 mt-8">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  data-testid="prev-page-button"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous
                </Button>
                
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-600">
                    Page {currentPage} of {Math.ceil(totalApis / itemsPerPage)}
                  </span>
                  <span className="text-xs text-slate-500">
                    ({totalApis} total APIs)
                  </span>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalApis / itemsPerPage), prev + 1))}
                  disabled={currentPage >= Math.ceil(totalApis / itemsPerPage)}
                  data-testid="next-page-button"
                >
                  Next
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the API <span className="font-semibold text-slate-900">"{apiToDelete?.name}"</span> and all its associated test cases and results. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default Dashboard;
