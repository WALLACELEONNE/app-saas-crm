import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";

import Login from "./pages/Login";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Clients from "./pages/Clients";
import Pipeline from "./pages/Pipeline";
import Contracts from "./pages/Contracts";
import Orders from "./pages/Orders";
import Products from "./pages/Products";
import Logistics from "./pages/Logistics";
import Support from "./pages/Support";
import AIAgents from "./pages/AIAgents";
import Architecture from "./pages/Architecture";
import ERP from "./pages/ERP";

function Protected({ children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="clients" element={<Clients />} />
            <Route path="pipeline" element={<Pipeline />} />
            <Route path="contracts" element={<Contracts />} />
            <Route path="orders" element={<Orders />} />
            <Route path="products" element={<Products />} />
            <Route path="logistics" element={<Logistics />} />
            <Route path="support" element={<Support />} />
            <Route path="ai" element={<AIAgents />} />
            <Route path="erp" element={<ERP />} />
            <Route path="architecture" element={<Architecture />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
