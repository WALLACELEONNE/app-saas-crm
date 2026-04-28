import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { fmtBRL, fmtNum, fmtTon } from "../lib/utils";
import { Card, PageHeader, Loading } from "../components/UI";
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, CartesianGrid,
} from "recharts";
import { TrendingUp, FileSignature, ShoppingCart, Users, Wheat, AlertTriangle } from "lucide-react";

const COLORS = ["#22C55E", "#FACC15", "#F97316", "#16A34A", "#EF4444", "#8BA094"];

function Kpi({ icon: Icon, label, value, sub, trace = false, testid, accent = "primary" }) {
  const accentMap = {
    primary: "text-primary",
    yellow: "text-accent-yellow",
    orange: "text-accent-orange",
    red: "text-accent-red",
  };
  return (
    <div className={`card-surface card-lift p-6 ${trace ? "kpi-trace" : ""}`} data-testid={testid}>
      <div className="flex items-start justify-between">
        <div className="overline">{label}</div>
        <Icon size={18} strokeWidth={1.6} className={accentMap[accent]} />
      </div>
      <div className="font-head font-bold text-3xl mt-3 tracking-tight">{value}</div>
      {sub && <div className="text-muted text-xs mt-2 font-mono">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard/kpis").then((r) => setData(r.data));
  }, []);

  if (!data) return <Loading />;
  const s = data.summary;

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title="Dashboard Executivo"
        subtitle="Visão consolidada do trading desk: contratos, volume, pipeline, faturamento por região e logística em tempo real."
        testid="dashboard-header"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 fade-in" data-testid="kpi-grid">
        <Kpi icon={FileSignature} label="Contratos Ativos" value={s.active_contracts}
             sub={`${fmtTon(s.grain_volume_ton)} · ${fmtBRL(s.grain_volume_value_brl)}`}
             trace testid="kpi-active-contracts" />
        <Kpi icon={TrendingUp} label="Pipeline Total" value={fmtBRL(s.pipeline_total_value)}
             sub={`${s.pipeline_total_count} oportunidades`}
             accent="yellow" testid="kpi-pipeline" />
        <Kpi icon={ShoppingCart} label="Pedidos em Aberto" value={s.open_orders}
             sub="Pendentes / em trânsito" accent="orange" testid="kpi-open-orders" />
        <Kpi icon={Users} label="Clientes" value={s.total_clients}
             sub={`${s.open_tickets} chamados em aberto`} testid="kpi-clients" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
        {/* Pipeline by stage — bar chart */}
        <Card className="lg:col-span-2" testid="chart-pipeline-stage">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="overline">Pipeline por Estágio</div>
              <div className="font-head text-xl font-semibold mt-1">Funil de Vendas</div>
            </div>
            <div className="text-muted text-xs font-mono">{fmtBRL(s.pipeline_total_value)}</div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.pipeline_by_stage}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F2922" vertical={false} />
              <XAxis dataKey="stage" stroke="#8BA094" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#8BA094" fontSize={11} tickLine={false} axisLine={false}
                     tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ background: "#0C110E", border: "1px solid #1F2922", borderRadius: 8 }}
                formatter={(v) => fmtBRL(v)}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {data.pipeline_by_stage.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Logistic status pie */}
        <Card testid="chart-logistic">
          <div className="overline">Logística</div>
          <div className="font-head text-xl font-semibold mt-1 mb-2">Status de Pátio</div>
          {data.logistic_status.length ? (
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={data.logistic_status}
                    dataKey="count"
                    nameKey="status"
                    cx="50%"
                    cy="50%"
                    outerRadius={88}
                    innerRadius={50}
                    paddingAngle={2}
                    stroke="#0C110E"
                    strokeWidth={2}
                    isAnimationActive={false}
                  >
                    {data.logistic_status.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#0C110E", border: "1px solid #1F2922", borderRadius: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : <div className="text-muted text-sm py-12 text-center">Sem cargas registradas</div>}
          <div className="grid grid-cols-2 gap-2 mt-2">
            {data.logistic_status.map((s, i) => (
              <div key={s.status} className="flex items-center gap-2 text-xs">
                <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="capitalize text-muted">{s.status.replace("_", " ")}</span>
                <span className="ml-auto font-mono">{s.count}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-6">
        {/* Revenue by region */}
        <Card className="lg:col-span-2" testid="chart-revenue-region">
          <div className="flex items-center gap-2 mb-2">
            <Wheat size={16} className="text-accent-yellow" strokeWidth={1.6} />
            <div className="overline">Faturamento por Região (contratos ativos)</div>
          </div>
          <div className="font-head text-xl font-semibold mb-4">Valor estimado por praça</div>
          {data.revenue_by_region.length ? (
            <div className="space-y-3">
              {data.revenue_by_region.map((r) => {
                const total = data.revenue_by_region[0].value || 1;
                const pct = (r.value / total) * 100;
                return (
                  <div key={r.region} className="" data-testid={`region-${r.region}`}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium">{r.region}</span>
                      <span className="font-mono text-muted">{fmtBRL(r.value)}</span>
                    </div>
                    <div className="h-2 bg-border-subtle rounded">
                      <div
                        className="h-2 rounded bg-gradient-to-r from-primary to-accent-yellow"
                        style={{ width: `${Math.max(pct, 4)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : <div className="text-muted text-sm py-8">Sem dados de faturamento.</div>}
        </Card>

        {/* Activity feed */}
        <Card testid="recent-activity">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-accent-orange" strokeWidth={1.6} />
            <div className="overline">Atividade Recente</div>
          </div>
          <div className="font-head text-xl font-semibold mt-1 mb-3">Audit trail</div>
          <ul className="space-y-3 max-h-[280px] overflow-auto">
            {data.recent_activity.length ? data.recent_activity.map((a, i) => (
              <li key={i} className="text-sm flex gap-3 fade-in" style={{ animationDelay: `${i * 50}ms` }}>
                <span className="text-accent-yellow font-mono text-xs mt-0.5">{a.action.toUpperCase().slice(0, 4)}</span>
                <div>
                  <div>{a.entity} · <span className="font-mono text-muted text-xs">{a.entity_id?.slice(0, 8)}</span></div>
                  <div className="text-muted text-xs">{a.user_email || "system"} · {new Date(a.timestamp).toLocaleString("pt-BR")}</div>
                </div>
              </li>
            )) : <li className="text-muted text-sm">Sem atividade recente.</li>}
          </ul>
        </Card>
      </div>
    </div>
  );
}
