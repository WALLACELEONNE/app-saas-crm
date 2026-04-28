import React, { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, EmptyState } from "../components/UI";
import { fmtDate } from "../lib/utils";
import { Plug, RefreshCw, Send, Inbox, CheckCircle2, XCircle, Clock, RotateCw, Settings, ShieldAlert, Skull, Play, Trash2 } from "lucide-react";

const VENDOR_COLORS = {
  sap: "text-accent-yellow",
  oracle: "text-accent-orange",
  siagri: "text-primary",
};

export default function ERP() {
  const [connectors, setConnectors] = useState([]);
  const [outbox, setOutbox] = useState({ items: [], counts: {} });
  const [deliveries, setDeliveries] = useState([]);
  const [breakers, setBreakers] = useState([]);
  const [dlq, setDlq] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [testing, setTesting] = useState(null);
  const [config, setConfig] = useState(null);
  const [filterStatus, setFilterStatus] = useState("");

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const [c, o, d, b, q] = await Promise.all([
        api.get("/integrations/connectors"),
        api.get("/integrations/outbox", { params: filterStatus ? { status: filterStatus } : {} }),
        api.get("/integrations/deliveries"),
        api.get("/integrations/circuit-breakers"),
        api.get("/integrations/dlq"),
      ]);
      setConnectors(c.data.connectors);
      setOutbox(o.data);
      setDeliveries(d.data.items);
      setBreakers(b.data.breakers);
      setDlq(q.data);
    } finally { setRefreshing(false); setLoading(false); }
  }, [filterStatus]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const triggerTest = async (vendor) => {
    setTesting(vendor);
    try {
      const r = await api.post(`/integrations/connectors/${vendor}/test`, {
        topic: "clients.create",
        payload: { after: { id: "test-uuid", seq_id: 9999, name: "Cliente Test " + vendor.toUpperCase(),
                            type: "producer", region: "Test/BR", doc: "00.000.000/0001-00",
                            culture: ["soja"], classification: "A", potential: "alto", area_ha: 1000 } },
      });
      alert(`Teste ${vendor.toUpperCase()}\n${r.data.result.ok ? "✅ OK" : "❌ FAIL"} (${r.data.result.status_code}) ${r.data.result.latency_ms}ms\n${r.data.result.response.slice(0,200)}`);
      load();
    } catch (e) {
      alert("Erro: " + (e?.response?.data?.detail || e.message));
    } finally { setTesting(null); }
  };

  const retry = async (id) => {
    await api.post(`/integrations/outbox/${id}/retry`);
    load();
  };

  const saveConfig = async () => {
    await api.post(`/integrations/connectors/${config.vendor}/configure`, {
      endpoint: config.endpoint || null,
      enabled: config.enabled,
    });
    setConfig(null);
    load();
  };

  if (loading) return <Loading />;

  const statusIcon = (s) => {
    if (s === "delivered") return <CheckCircle2 size={14} className="text-primary" />;
    if (s === "failed") return <XCircle size={14} className="text-accent-red" />;
    if (s === "in_progress") return <RotateCw size={14} className="text-accent-yellow animate-spin" />;
    return <Clock size={14} className="text-muted" />;
  };

  return (
    <div data-testid="erp-page">
      <PageHeader
        title="ERP — Hub de Integração"
        subtitle="Conectores reais SAP / Oracle / Siagri Agribusiness com outbox durável e workers em background. Eventos de domínio são despachados automaticamente para os ERPs habilitados."
        actions={
          <button onClick={load} className="btn-ghost flex items-center gap-2" data-testid="erp-refresh-btn">
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /> Atualizar
          </button>
        }
      />

      {/* Connectors */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {connectors.map((c) => (
          <Card key={c.vendor} testid={`connector-${c.vendor}`}>
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                <Plug size={18} className={VENDOR_COLORS[c.vendor]} strokeWidth={1.6} />
                <div>
                  <div className="overline">{c.vendor.toUpperCase()}</div>
                  <div className="font-head font-bold text-lg">{c.name}</div>
                </div>
              </div>
              <span className={`tag ${c.enabled ? "tag-green" : "tag-muted"}`}>
                {c.enabled ? "Ativo" : "Desativado"}
              </span>
            </div>
            <div className="text-xs text-muted mb-3">
              <div className="overline mb-1">Tópicos</div>
              <div className="font-mono break-all">{(c.topics || []).join(" · ") || "—"}</div>
            </div>
            <div className="text-xs text-muted mb-3">
              <div className="overline mb-1">Endpoint</div>
              <div className="font-mono break-all text-text-main/80">{c.endpoint || "—"}</div>
            </div>
            <div className="flex gap-2">
              <button onClick={() => triggerTest(c.vendor)} disabled={!c.enabled || testing === c.vendor}
                      className="btn-primary !py-1 !px-3 text-xs flex items-center gap-1 flex-1 justify-center" data-testid={`test-${c.vendor}`}>
                <Send size={12} /> {testing === c.vendor ? "Testando..." : "Disparar teste"}
              </button>
              <button onClick={() => setConfig({ vendor: c.vendor, endpoint: c.endpoint, enabled: c.enabled })}
                      className="btn-ghost !py-1 !px-2 text-xs flex items-center gap-1" data-testid={`config-${c.vendor}`}>
                <Settings size={12} />
              </button>
            </div>
          </Card>
        ))}
      </div>

      {/* Outbox + status counters */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <Card testid="outbox-stats">
          <div className="flex items-center gap-2 mb-3"><Inbox size={16} className="text-primary" /><div className="overline">Outbox</div></div>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["delivered", "Entregues", "tag-green"],
              ["pending", "Pendentes", "tag-yellow"],
              ["in_progress", "Em curso", "tag-orange"],
              ["failed", "Falhas", "tag-red"],
            ].map(([k, label, cls]) => (
              <button key={k} onClick={() => setFilterStatus(filterStatus === k ? "" : k)}
                      className={`text-left p-3 rounded-lg border transition ${filterStatus === k ? "border-primary" : "border-border-subtle hover:border-border-bright"}`}
                      data-testid={`outbox-counter-${k}`}>
                <div className="overline">{label}</div>
                <div className="font-head font-bold text-2xl mt-1">{outbox.counts[k] || 0}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card className="lg:col-span-2" testid="outbox-list">
          <div className="flex items-center justify-between mb-3">
            <div className="overline">Eventos {filterStatus && <>· filtro: <span className="text-primary">{filterStatus}</span></>}</div>
            <div className="text-xs text-muted">auto-refresh 5s</div>
          </div>
          <div className="max-h-96 overflow-auto space-y-2">
            {outbox.items.length === 0 ? <EmptyState title="Sem eventos" hint="Crie/edite um cliente, contrato ou pedido para gerar eventos." /> : outbox.items.map((e) => (
              <div key={e.id} className="border border-border-subtle rounded-lg p-3" data-testid={`outbox-${e.id.slice(0,8)}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {statusIcon(e.status)}
                    <span className="font-mono text-sm text-primary">{e.topic}</span>
                    <span className="text-muted text-xs">· tentativa {e.attempts}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted text-xs">{fmtDate(e.created_at)}</span>
                    {(e.status === "failed" || e.status === "delivered") && (
                      <button className="btn-ghost !py-0.5 !px-2 text-xs" onClick={() => retry(e.id)}
                              data-testid={`retry-${e.id.slice(0,8)}`}>
                        <RotateCw size={11} className="inline mr-1" /> Re-disparar
                      </button>
                    )}
                  </div>
                </div>
                {e.deliveries?.length > 0 && (
                  <div className="flex gap-2 mt-2 ml-5">
                    {e.deliveries.map((d, i) => (
                      <span key={i} className={`tag ${d.ok ? "tag-green" : "tag-red"} !text-[0.65rem]`}>
                        {d.vendor.toUpperCase()} {d.ok ? "✓" : "✗"} {d.status_code}
                      </span>
                    ))}
                  </div>
                )}
                {e.last_error && e.status !== "delivered" && <div className="text-accent-red text-xs mt-1 ml-5">{e.last_error}</div>}
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Circuit Breakers + DLQ row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card lift={false} testid="circuit-breakers">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><ShieldAlert size={16} className="text-accent-yellow" /><div className="overline">Circuit Breakers</div></div>
            <div className="text-muted text-xs font-mono">5 falhas em 60s → OPEN · cooldown 30s</div>
          </div>
          <div className="space-y-2">
            {breakers.map((b) => {
              const stateMap = {
                closed: { color: "tag-green", label: "CLOSED" },
                half_open: { color: "tag-yellow", label: "HALF-OPEN" },
                open: { color: "tag-red", label: "OPEN" },
              };
              const m = stateMap[b.state] || stateMap.closed;
              return (
                <div key={b.vendor} className="flex items-center gap-3 p-2 border border-border-subtle rounded-lg" data-testid={`breaker-${b.vendor}`}>
                  <span className={`tag ${m.color} font-mono`}>{m.label}</span>
                  <div className="flex-1">
                    <div className="font-mono text-sm uppercase">{b.vendor}</div>
                    <div className="text-muted text-xs">{b.failures_in_window}/{b.threshold} falhas em {b.window_sec}s</div>
                  </div>
                  {b.state !== "closed" && (
                    <button onClick={() => resetBreaker(b.vendor)}
                            className="btn-ghost !py-1 !px-2 text-xs" data-testid={`reset-breaker-${b.vendor}`}>
                      Reset
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </Card>

        <Card lift={false} testid="dlq-card">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2"><Skull size={16} className="text-accent-red" /><div className="overline">Dead-Letter Queue</div></div>
            <span className="tag tag-red font-mono">{dlq.total} eventos</span>
          </div>
          {dlq.items.length === 0 ? <EmptyState title="DLQ vazia" hint="Eventos com max retries excedido aparecem aqui." /> : (
            <div className="max-h-72 overflow-auto space-y-2">
              {dlq.items.map((d) => (
                <div key={d.id} className="border border-accent-red/30 rounded-lg p-3" data-testid={`dlq-${d.id.slice(0,8)}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-mono text-sm text-accent-red">{d.topic}</div>
                      <div className="text-muted text-xs">tentativas: {d.attempts} · {fmtDate(d.moved_at)}</div>
                    </div>
                    <div className="flex gap-1">
                      <button onClick={() => replayDlq(d.id)} className="btn-ghost !py-0.5 !px-2 text-xs flex items-center gap-1"
                              data-testid={`replay-${d.id.slice(0,8)}`}>
                        <Play size={11} /> Replay
                      </button>
                      <button onClick={() => purgeDlq(d.id)} className="btn-ghost !py-0.5 !px-2 text-xs hover:!border-accent-red"
                              data-testid={`purge-${d.id.slice(0,8)}`}>
                        <Trash2 size={11} />
                      </button>
                    </div>
                  </div>
                  <div className="text-muted text-xs mt-1 font-mono">{d.reason}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Recent deliveries log */}
      <Card lift={false} testid="deliveries-log">
        <div className="overline mb-3">Log de entregas (último 50)</div>
        {deliveries.length === 0 ? <EmptyState /> : (
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="deliveries-table">
              <thead><tr><th>Quando</th><th>Vendor</th><th>Tópico</th><th>Status</th><th>Latência</th><th>Tentativa</th><th>Endpoint</th></tr></thead>
              <tbody>
                {deliveries.map((d) => (
                  <tr key={d.id}>
                    <td className="font-mono text-muted text-xs">{fmtDate(d.timestamp)}</td>
                    <td><span className={`tag ${d.ok ? "tag-green" : "tag-red"} font-mono uppercase`}>{d.vendor}</span></td>
                    <td className="font-mono text-xs">{d.topic}</td>
                    <td><span className={d.ok ? "text-primary" : "text-accent-red"}>{d.ok ? "✓ OK" : "✗ FAIL"} ({d.status_code})</span></td>
                    <td className="font-mono">{d.latency_ms}ms</td>
                    <td className="font-mono text-muted">#{d.attempt}</td>
                    <td className="font-mono text-muted text-xs truncate max-w-xs">{d.endpoint}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {config && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={() => setConfig(null)}>
          <div className="card-surface p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()} data-testid="config-modal">
            <h2 className="font-head font-bold text-xl mb-4">Configurar {config.vendor.toUpperCase()}</h2>
            <label className="overline">Endpoint</label>
            <input className="input-field font-mono text-xs mb-3" value={config.endpoint || ""}
                   onChange={(e) => setConfig({ ...config, endpoint: e.target.value })}
                   placeholder="https://api.erp.example.com/webhook" />
            <label className="flex items-center gap-2 mb-4">
              <input type="checkbox" checked={config.enabled} onChange={(e) => setConfig({ ...config, enabled: e.target.checked })} />
              <span className="text-sm">Habilitado</span>
            </label>
            <button className="btn-primary w-full" onClick={saveConfig} data-testid="save-config-btn">Salvar</button>
            <p className="text-muted text-xs mt-3">Em prod: incluir headers de autenticação e HMAC.</p>
          </div>
        </div>
      )}
    </div>
  );
}
