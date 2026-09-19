import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "../components/ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "../components/ui/alert-dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import { toast } from "sonner";
import { Plus, Trash2, FolderOpen, Layers, ArrowLeft, Play, ChevronDown, ChevronRight } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Collections = () => {
  const navigate = useNavigate();
  const [collections, setCollections] = useState([]);
  const [apis, setApis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [collectionToDelete, setCollectionToDelete] = useState(null);
  const [expandedProjects, setExpandedProjects] = useState({});
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    selectedApis: []
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [collectionsRes, apisRes] = await Promise.all([
        axios.get(`${API}/collections`),
        axios.get(`${API}/apis?page=1&limit=1000`)
      ]);
      setCollections(collectionsRes.data);
      setApis(apisRes.data);
    } catch (error) {
      toast.error("Failed to fetch data");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (formData.selectedApis.length === 0) {
      toast.error("Please select at least one API");
      return;
    }

    try {
      await axios.post(`${API}/collections`, {
        name: formData.name,
        description: formData.description,
        api_ids: formData.selectedApis
      });

      toast.success("Collection created successfully");
      setDialogOpen(false);
      setFormData({ name: "", description: "", selectedApis: [] });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to create collection");
    }
  };

  const handleDelete = async () => {
    if (!collectionToDelete) return;

    try {
      await axios.delete(`${API}/collections/${collectionToDelete.id}`);
      toast.success("Collection deleted successfully");
      setDeleteDialogOpen(false);
      setCollectionToDelete(null);
      fetchData();
    } catch (error) {
      toast.error("Failed to delete collection");
    }
  };

  const openDeleteDialog = (collection, e) => {
    e.stopPropagation();
    setCollectionToDelete(collection);
    setDeleteDialogOpen(true);
  };

  const toggleApiSelection = (apiId) => {
    setFormData(prev => ({
      ...prev,
      selectedApis: prev.selectedApis.includes(apiId)
        ? prev.selectedApis.filter(id => id !== apiId)
        : [...prev.selectedApis, apiId]
    }));
  };

  const toggleProjectExpand = (projectName) => {
    setExpandedProjects(prev => ({ ...prev, [projectName]: !prev[projectName] }));
  };

  const getApisByProject = () => {
    const grouped = {};
    apis.forEach(api => {
      const project = api.project_name || "Ungrouped";
      if (!grouped[project]) grouped[project] = [];
      grouped[project].push(api);
    });
    return grouped;
  };

  const toggleProjectSelection = (projectApis) => {
    const projectApiIds = projectApis.map(a => a.id);
    const allSelected = projectApiIds.every(id => formData.selectedApis.includes(id));
    setFormData(prev => ({
      ...prev,
      selectedApis: allSelected
        ? prev.selectedApis.filter(id => !projectApiIds.includes(id))
        : [...new Set([...prev.selectedApis, ...projectApiIds])]
    }));
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
        <div className="mb-8">
          <Button
            variant="outline"
            onClick={() => navigate("/")}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>

          <div className="flex items-center justify-between">
            <div className="text-center flex-1">
              <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-800 to-blue-600 bg-clip-text text-transparent mb-2">
                Test Collections
              </h1>
              <p className="text-slate-600">
                Group multiple APIs and run all tests together
              </p>
            </div>

            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-blue-600 hover:bg-blue-700">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Collection
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create New Collection</DialogTitle>
                <DialogDescription>
                  Select APIs to group together for batch testing
                </DialogDescription>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <Label htmlFor="name">Collection Name</Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="User Flow Tests"
                    required
                  />
                </div>

                <div>
                  <Label htmlFor="description">Description (Optional)</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Tests for user registration, login, and profile"
                    rows={2}
                  />
                </div>

                <div>
                  <Label>Select APIs ({formData.selectedApis.length} selected)</Label>
                  <div className="border rounded-lg p-3 max-h-72 overflow-y-auto mt-2">
                    {apis.length === 0 ? (
                      <p className="text-sm text-slate-500 text-center py-4">
                        No APIs available. Create APIs first.
                      </p>
                    ) : (
                      Object.entries(getApisByProject()).map(([projectName, projectApis]) => {
                        const isExpanded = expandedProjects[projectName];
                        const projectApiIds = projectApis.map(a => a.id);
                        const allSelected = projectApiIds.every(id => formData.selectedApis.includes(id));
                        const someSelected = projectApiIds.some(id => formData.selectedApis.includes(id));
                        return (
                          <div key={projectName} className="mb-1">
                            <div className="flex items-center gap-2 p-2 bg-slate-50 rounded-md hover:bg-slate-100 cursor-pointer">
                              <Checkbox
                                checked={allSelected}
                                className={someSelected && !allSelected ? "opacity-60" : ""}
                                onCheckedChange={() => toggleProjectSelection(projectApis)}
                              />
                              <div
                                className="flex items-center gap-1 flex-1"
                                onClick={() => toggleProjectExpand(projectName)}
                              >
                                {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
                                <span className="text-sm font-semibold text-slate-700">{projectName}</span>
                                <span className="text-xs text-slate-400 ml-1">({projectApis.length})</span>
                              </div>
                            </div>
                            {isExpanded && (
                              <div className="ml-6 border-l-2 border-slate-200 pl-3 mt-1 space-y-1">
                                {projectApis.map(api => (
                                  <div key={api.id} className="flex items-center space-x-2 p-1.5 hover:bg-slate-50 rounded">
                                    <Checkbox
                                      id={api.id}
                                      checked={formData.selectedApis.includes(api.id)}
                                      onCheckedChange={() => toggleApiSelection(api.id)}
                                    />
                                    <label htmlFor={api.id} className="flex-1 text-sm cursor-pointer">
                                      <span className="font-medium">{api.name}</span>
                                      <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-semibold ${
                                        api.method === 'GET' ? 'bg-emerald-100 text-emerald-700' :
                                        api.method === 'POST' ? 'bg-blue-100 text-blue-700' :
                                        api.method === 'PUT' ? 'bg-amber-100 text-amber-700' :
                                        api.method === 'DELETE' ? 'bg-rose-100 text-rose-700' :
                                        'bg-purple-100 text-purple-700'
                                      }`}>{api.method}</span>
                                      <div className="text-xs text-slate-400 mt-0.5 truncate">{api.url}</div>
                                    </label>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                <div className="flex gap-2 pt-2">
                  <Button type="submit" className="flex-1">
                    Create Collection
                  </Button>
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={() => {
                      setDialogOpen(false);
                      setFormData({ name: "", description: "", selectedApis: [] });
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {collections.length === 0 ? (
          <Card className="border-2 border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <FolderOpen className="w-16 h-16 text-slate-300 mb-4" />
              <h3 className="text-xl font-semibold text-slate-700 mb-2">No collections yet</h3>
              <p className="text-slate-500 mb-4">Create your first collection to group APIs</p>
              <Button onClick={() => setDialogOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Collection
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {collections.map((collection) => (
              <Card 
                key={collection.id} 
                className="hover:shadow-lg transition-all duration-200 cursor-pointer group"
                onClick={() => navigate(`/collections/${collection.id}`)}
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <CardTitle className="text-lg flex items-center gap-2">
                        <Layers className="w-5 h-5 text-blue-600" />
                        {collection.name}
                      </CardTitle>
                      <CardDescription className="mt-2">
                        {collection.description || "No description"}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">APIs in collection:</span>
                      <span className="font-semibold text-blue-600">{collection.api_count}</span>
                    </div>
                    <div className="flex gap-2 pt-2 border-t">
                      <Button
                        size="sm"
                        className="flex-1"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/collections/${collection.id}`);
                        }}
                      >
                        <Play className="w-4 h-4 mr-1" />
                        View & Run
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={(e) => openDeleteDialog(collection, e)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the collection <span className="font-semibold text-slate-900">"{collectionToDelete?.name}"</span>. 
              The APIs and their test cases will not be deleted.
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

export default Collections;
