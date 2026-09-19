import { useState, useEffect } from "react";
import "./App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import APIDetail from "./pages/APIDetail";
import Collections from "./pages/Collections";
import CollectionDetail from "./pages/CollectionDetail";
import ContractTesting from "./pages/ContractTesting";
import ResponseValidation from "./pages/ResponseValidation";
import JSONSchemaGenerator from "./pages/JSONSchemaGenerator";
import { Toaster } from "./components/ui/sonner";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/api/:apiId" element={<APIDetail />} />
          <Route path="/collections" element={<Collections />} />
          <Route path="/collections/:collectionId" element={<CollectionDetail />} />
          <Route path="/contract-testing" element={<ContractTesting />} />
          <Route path="/response-validation" element={<ResponseValidation />} />
          <Route path="/json-schema-generator" element={<JSONSchemaGenerator />} />
        </Routes>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}

export default App;
