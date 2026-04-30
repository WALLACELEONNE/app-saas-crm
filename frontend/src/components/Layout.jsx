import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Users, Kanban, FileSignature, ShoppingCart,
  Package, Truck, LifeBuoy, Sparkles, Workflow, LogOut, Wheat, Plug, Settings
} from "lucide-react";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard", permission: "dashboard.view" },
  { to: "/clients", label: "Clientes", icon: Users, testid: "nav-clients", permission: "clients.view" },
  { to: "/pipeline", label: "Pipeline", icon: Kanban, testid: "nav-pipeline", permission: "pipeline.view" },
  { to: "/contracts", label: "Contratos", icon: FileSignature, testid: "nav-contracts", permission: "contracts.view" },
  { to: "/orders", label: "Pedidos", icon: ShoppingCart, testid: "nav-orders", permission: "orders.view" },
  { to: "/products", label: "Produtos", icon: Package, testid: "nav-products", permission: "products.view" },
  { to: "/logistics", label: "Logistica", icon: Truck, testid: "nav-logistics", permission: "logistics.view" },
  { to: "/support", label: "Suporte", icon: LifeBuoy, testid: "nav-support", permission: "support.view" },
  { to: "/ai", label: "Agentes IA", icon: Sparkles, testid: "nav-ai", permission: "ai.use" },
  { to: "/erp", label: "ERP Hub", icon: Plug, testid: "nav-erp", permission: "erp.view" },
  { to: "/admin", label: "Admin", icon: Settings, testid: "nav-admin", permission: "users.view" },
  { to: "/architecture", label: "Arquitetura", icon: Workflow, testid: "nav-architecture", permission: "settings.view" },
];

export default function Layout() {
  const { user, logout, can } = useAuth();
  const nav = useNavigate();
  const visibleNav = NAV.filter((item) => can(item.permission));

  return (
    <div className="min-h-screen">
      <aside className="sidebar-shell" data-testid="sidebar">
        <div className="flex items-center gap-2 mb-7 px-1">
          <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/40 flex items-center justify-center">
            <Wheat size={20} className="text-primary" strokeWidth={1.8} />
          </div>
          <div>
            <div className="font-head font-bold text-[1.05rem] tracking-tight">Agro<span className="text-primary">CRM</span></div>
            <div className="text-[0.65rem] text-muted overline">Trading Terminal</div>
          </div>
        </div>

        <nav className="flex flex-col gap-1 flex-1 overflow-y-auto pl-3">
          {visibleNav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={item.testid}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            >
              <item.icon size={17} strokeWidth={1.6} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="account-panel mt-4 pt-4 border-t border-border-subtle">
          <div className="px-3 mb-3">
            <div className="text-[0.7rem] text-muted overline">Conectado</div>
            <div className="font-head font-semibold text-sm mt-1" data-testid="current-user-name">{user?.name}</div>
            <div className="text-xs text-muted">{user?.email}</div>
            <div className="text-[0.65rem] text-muted mt-1 font-mono truncate">{user?.tenant?.name || user?.tenant_id}</div>
          </div>
          <button
            onClick={() => { logout(); nav("/login"); }}
            data-testid="logout-button"
            className="nav-item w-full !text-muted hover:!text-accent-red"
          >
            <LogOut size={16} strokeWidth={1.6} />
            <span>Sair</span>
          </button>
        </div>
      </aside>

      <main className="main-shell">
        <Outlet />
      </main>
    </div>
  );
}
