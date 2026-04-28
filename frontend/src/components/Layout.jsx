import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Users, Kanban, FileSignature, ShoppingCart,
  Package, Truck, LifeBuoy, Sparkles, Workflow, LogOut, Wheat, Plug
} from "lucide-react";
import { useAuth } from "../lib/auth";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/clients", label: "Clientes", icon: Users, testid: "nav-clients" },
  { to: "/pipeline", label: "Pipeline", icon: Kanban, testid: "nav-pipeline" },
  { to: "/contracts", label: "Contratos", icon: FileSignature, testid: "nav-contracts" },
  { to: "/orders", label: "Pedidos", icon: ShoppingCart, testid: "nav-orders" },
  { to: "/products", label: "Produtos", icon: Package, testid: "nav-products" },
  { to: "/logistics", label: "Logística", icon: Truck, testid: "nav-logistics" },
  { to: "/support", label: "Suporte", icon: LifeBuoy, testid: "nav-support" },
  { to: "/ai", label: "Agentes IA", icon: Sparkles, testid: "nav-ai" },
  { to: "/erp", label: "ERP Hub", icon: Plug, testid: "nav-erp" },
  { to: "/architecture", label: "Arquitetura", icon: Workflow, testid: "nav-architecture" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

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
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.testid}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            >
              <n.icon size={17} strokeWidth={1.6} />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-4 pt-4 border-t border-border-subtle">
          <div className="px-3 mb-3">
            <div className="text-[0.7rem] text-muted overline">Conectado</div>
            <div className="font-head font-semibold text-sm mt-1" data-testid="current-user-name">{user?.name}</div>
            <div className="text-xs text-muted">{user?.email}</div>
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
