import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import { Loading } from "./components/UI";

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
import Admin from "./pages/Admin";

function Protected({ children }) {
  const { user, hydrating } = useAuth();
  if (hydrating) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RequirePermission({ permission, children }) {
  const { can, hydrating } = useAuth();
  if (hydrating) return <Loading />;
  if (!can(permission)) return <Navigate to="/dashboard" replace />;
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
            <Route path="dashboard" element={<RequirePermission permission="dashboard.view"><Dashboard /></RequirePermission>} />
            <Route path="clients" element={<RequirePermission permission="clients.view"><Clients /></RequirePermission>} />
            <Route path="pipeline" element={<RequirePermission permission="pipeline.view"><Pipeline /></RequirePermission>} />
            <Route path="contracts" element={<RequirePermission permission="contracts.view"><Contracts /></RequirePermission>} />
            <Route path="orders" element={<RequirePermission permission="orders.view"><Orders /></RequirePermission>} />
            <Route path="products" element={<RequirePermission permission="products.view"><Products /></RequirePermission>} />
            <Route path="logistics" element={<RequirePermission permission="logistics.view"><Logistics /></RequirePermission>} />
            <Route path="support" element={<RequirePermission permission="support.view"><Support /></RequirePermission>} />
            <Route path="ai" element={<RequirePermission permission="ai.use"><AIAgents /></RequirePermission>} />
            <Route path="erp" element={<RequirePermission permission="erp.view"><ERP /></RequirePermission>} />
            <Route path="admin" element={<RequirePermission permission="users.view"><Admin /></RequirePermission>} />
            <Route path="architecture" element={<RequirePermission permission="settings.view"><Architecture /></RequirePermission>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
