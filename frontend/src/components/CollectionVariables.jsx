import { useState } from "react";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "./ui/dialog";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "./ui/alert-dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Textarea } from "./ui/textarea";
import { Switch } from "./ui/switch";
import { Badge } from "./ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import { Plus, Edit, Trash2, Eye, EyeOff, Key, Search, Package, Link } from "lucide-react";
import { toast } from "sonner";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const CollectionVariables = ({ collectionId, onUpdate }) => {
  const [variables, setVariables] = useState([]);
  const [loading, setLoading] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedVariable, setSelectedVariable] = useState(null);
  const [variableToDelete, setVariableToDelete] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});
  const [usageCounts, setUsageCounts] = useState({});
  
  const [formData, setFormData] = useState({
    scope: "headers",
    key: "",
    value: "",
    description: "",
    is_secret: false,
    enabled: true
  });

  const fetchVariables = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/collections/${collectionId}/variables`);
      setVariables(response.data);
      
      // Fetch usage count for each variable
      const counts = {};
      for (const variable of response.data) {
        try {
          const usageResponse = await axios.get(`${API}/collections/${collectionId}/variables/${variable.id}/usage`);
          counts[variable.id] = usageResponse.data.usage_count;
        } catch (error) {
          counts[variable.id] = 0;
        }
      }
      setUsageCounts(counts);
    } catch (error) {
      toast.error("Failed to fetch variables");
    } finally {
      setLoading(false);
    }
  };

  useState(() => {
    fetchVariables();
  }, [collectionId]);

  const handleAdd = async () => {
    try {
      await axios.post(`${API}/collections/${collectionId}/variables`, formData);
      toast.success("Variable added successfully");
      setAddDialogOpen(false);
      setFormData({ scope: "headers", key: "", value: "", description: "", is_secret: false, enabled: true });
      fetchVariables();
      if (onUpdate) onUpdate();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to add variable");
    }
  };

  const handleUpdate = async () => {
    try {
      await axios.put(`${API}/collections/${collectionId}/variables/${selectedVariable.id}`, {
        value: formData.value,
        description: formData.description,
        is_secret: formData.is_secret,
        enabled: formData.enabled
      });
      toast.success("Variable updated successfully");
      setEditDialogOpen(false);
      setSelectedVariable(null);
      fetchVariables();
      if (onUpdate) onUpdate();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update variable");
    }
  };

  const handleDelete = async () => {
    if (!variableToDelete) return;
    
    try {
      await axios.delete(`${API}/collections/${collectionId}/variables/${variableToDelete.id}`);
      toast.success("Variable deleted successfully");
      setDeleteDialogOpen(false);
      setVariableToDelete(null);
      fetchVariables();
      if (onUpdate) onUpdate();
    } catch (error) {
      toast.error("Failed to delete variable");
    }
  };

  const openDeleteDialog = (variable) => {
    setVariableToDelete(variable);
    setDeleteDialogOpen(true);
  };

  const openEditDialog = (variable) => {
    setSelectedVariable(variable);
    setFormData({
      scope: variable.scope,
      key: variable.key,
      value: variable.value,
      description: variable.description || "",
      is_secret: variable.is_secret,
      enabled: variable.enabled
    });
    setEditDialogOpen(true);
  };

  const toggleSecret = (id) => {
    setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const maskValue = (value) => {
    return "•".repeat(Math.min(value.length, 20));
  };

  const getScopeIcon = (scope) => {
    switch (scope) {
      case "headers": return <Key className="w-4 h-4 text-orange-600" />;
      case "query_params": return <Search className="w-4 h-4 text-blue-600" />;
      case "body": return <Package className="w-4 h-4 text-green-600" />;
      case "url": return <Link className="w-4 h-4 text-purple-600" />;
      default: return null;
    }
  };

  const groupedVariables = variables.reduce((acc, variable) => {
    if (!acc[variable.scope]) acc[variable.scope] = [];
    acc[variable.scope].push(variable);
    return acc;
  }, {});

  const scopeLabels = {
    headers: "HEADERS",
    query_params: "QUERY PARAMS",
    body: "BODY",
    url: "URL"
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            🔧 Collection Variables ({variables.length})
          </CardTitle>
          <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="w-4 h-4 mr-2" />
                Add Variable
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Collection Variable</DialogTitle>
                <DialogDescription>
                  Variables will override API values when running tests in this collection
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label>Scope *</Label>
                  <Select 
                    value={formData.scope} 
                    onValueChange={(value) => {
                      setFormData({ 
                        ...formData, 
                        scope: value,
                        key: value === 'url' ? 'baseUrl' : formData.key
                      });
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="headers">Headers</SelectItem>
                      <SelectItem value="query_params">Query Parameters</SelectItem>
                      <SelectItem value="body">Body</SelectItem>
                      <SelectItem value="url">URL</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Key *</Label>
                  {formData.scope === 'url' ? (
                    <Select 
                      value={formData.key} 
                      onValueChange={(value) => setFormData({ ...formData, key: value })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select URL replacement type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="baseUrl">baseUrl (domain only)</SelectItem>
                        <SelectItem value="fullUrl">fullUrl (complete URL)</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      value={formData.key}
                      onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                      placeholder="e.g., Authorization, api_key, userId"
                    />
                  )}
                  {formData.scope === 'url' && (
                    <div className="text-xs text-slate-600 mt-1 space-y-1">
                      <p>• <strong>baseUrl</strong>: Replace only domain (e.g., https://api.example.com)</p>
                      <p>• <strong>fullUrl</strong>: Replace entire URL including path</p>
                    </div>
                  )}
                </div>
                <div>
                  <Label>Value *</Label>
                  <Textarea
                    value={formData.value}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                    placeholder={
                      formData.scope === 'url' && formData.key === 'baseUrl'
                        ? 'e.g., https://api.example.com (domain only)'
                        : formData.scope === 'url' && formData.key === 'fullUrl'
                        ? 'e.g., https://api.example.com/api/v1/todos/123 (complete URL)'
                        : 'e.g., Bearer token123'
                    }
                    rows={3}
                  />
                  {formData.scope === 'url' && formData.key === 'baseUrl' && (
                    <p className="text-xs text-amber-600 mt-1">
                      ⚠️ Enter ONLY the base domain (e.g., https://api.example.com), NOT the full path
                    </p>
                  )}
                  {formData.scope === 'url' && formData.key === 'fullUrl' && (
                    <p className="text-xs text-blue-600 mt-1">
                      ℹ️ Enter the complete URL including path (e.g., https://api.example.com/api/v1/resource)
                    </p>
                  )}
                </div>
                <div>
                  <Label>Description (Optional)</Label>
                  <Input
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="What is this variable for?"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Secret (mask value)</Label>
                  <Switch
                    checked={formData.is_secret}
                    onCheckedChange={(checked) => setFormData({ ...formData, is_secret: checked })}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Enabled</Label>
                  <Switch
                    checked={formData.enabled}
                    onCheckedChange={(checked) => setFormData({ ...formData, enabled: checked })}
                  />
                </div>
                <Button onClick={handleAdd} className="w-full">Add Variable</Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="text-center py-8 text-slate-500">Loading variables...</div>
        ) : variables.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <p>No variables defined yet</p>
            <p className="text-sm mt-2">Add variables to override API values during test execution</p>
          </div>
        ) : (
          <Accordion type="multiple" defaultValue={["headers", "query_params", "body", "url"]}>
            {Object.entries(scopeLabels).map(([scope, label]) => {
              const scopeVars = groupedVariables[scope] || [];
              return (
                <AccordionItem key={scope} value={scope}>
                  <AccordionTrigger>
                    <div className="flex items-center gap-2">
                      {getScopeIcon(scope)}
                      <span className="font-semibold">{label}</span>
                      <Badge variant="outline">({scopeVars.length})</Badge>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    {scopeVars.length === 0 ? (
                      <div className="text-sm text-slate-500 py-2">No {label.toLowerCase()} variables defined</div>
                    ) : (
                      <div className="space-y-3 pt-2">
                        {scopeVars.map((variable) => (
                          <div key={variable.id} className="border rounded-lg p-4 bg-slate-50">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  {getScopeIcon(variable.scope)}
                                  <span className="font-semibold">{variable.key}</span>
                                  {!variable.enabled && <Badge variant="outline" className="text-xs">Disabled</Badge>}
                                </div>
                                <div className="flex items-center gap-2 text-sm">
                                  <span className="text-slate-600">Value:</span>
                                  <code className="bg-white px-2 py-1 rounded border text-xs">
                                    {variable.is_secret && !showSecrets[variable.id]
                                      ? maskValue(variable.value)
                                      : variable.value}
                                  </code>
                                  {variable.is_secret && (
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => toggleSecret(variable.id)}
                                      className="h-6 w-6 p-0"
                                    >
                                      {showSecrets[variable.id] ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                                    </Button>
                                  )}
                                </div>
                                {variable.description && (
                                  <p className="text-xs text-slate-500 mt-1">{variable.description}</p>
                                )}
                                <div className="flex items-center gap-2 mt-2">
                                  <Badge variant="outline" className="text-xs">
                                    Used in {usageCounts[variable.id] || 0} test case{(usageCounts[variable.id] || 0) !== 1 ? 's' : ''}
                                  </Badge>
                                </div>
                              </div>
                              <div className="flex gap-1">
                                <Button variant="ghost" size="sm" onClick={() => openEditDialog(variable)}>
                                  <Edit className="w-4 h-4" />
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => openDeleteDialog(variable)}>
                                  <Trash2 className="w-4 h-4 text-red-600" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        )}
      </CardContent>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Variable: {selectedVariable?.key}</DialogTitle>
            <DialogDescription>Update variable value and settings</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Value *</Label>
              <Textarea
                value={formData.value}
                onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                rows={3}
              />
            </div>
            <div>
              <Label>Description</Label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label>Secret (mask value)</Label>
              <Switch
                checked={formData.is_secret}
                onCheckedChange={(checked) => setFormData({ ...formData, is_secret: checked })}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label>Enabled</Label>
              <Switch
                checked={formData.enabled}
                onCheckedChange={(checked) => setFormData({ ...formData, enabled: checked })}
              />
            </div>
            <Button onClick={handleUpdate} className="w-full">Update Variable</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Variable?</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete the variable <strong>"{variableToDelete?.key}"</strong>?
              {usageCounts[variableToDelete?.id] > 0 && (
                <span className="block mt-2 text-amber-600">
                  ⚠️ This variable is currently used in {usageCounts[variableToDelete?.id]} test case{usageCounts[variableToDelete?.id] !== 1 ? 's' : ''}.
                </span>
              )}
              <span className="block mt-2">
                This action cannot be undone.
              </span>
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
    </Card>
  );
};

export default CollectionVariables;
