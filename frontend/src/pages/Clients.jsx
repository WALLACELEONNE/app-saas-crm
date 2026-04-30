import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, StatusTag, Loading, EmptyState, PaginationBar } from "../components/UI";
import { useAuth } from "../lib/auth";
import { Plus, Search, Sparkles, X } from "lucide-react";

export default function Clients() {
  const { can } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [appliedQ, setAppliedQ] = useState("");
  const [open, setOpen] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [form, setForm] = useState({
    type: "producer", name: "", doc: "", region: "",
    culture: "", classification: "B", potential: "medio", area_ha: 0,
  });

  const load = useCallback((search = "", nextSkip = 0, nextLimit = 20) => {
    setLoading(true);
    api.get("/clients", { params: { ...(search ? { q: search } : {}), skip: nextSkip, limit: nextLimit } })
      .then((r) => {
        setItems(r.data.items);
        setTotal(r.data.total || 0);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(appliedQ, skip, limit); }, [appliedQ, skip, limit, load]);

  const search = () => {
    setSkip(0);
    setAppliedQ(q);
    load(q, 0, limit);
  };

  const submit = async (e) => {
    e.preventDefault();
    const payload = {
      ...form,
      culture: form.culture.split(",").map((s) => s.trim()).filter(Boolean),
      area_ha: Number(form.area_ha) || 0,
    };
    await api.post("/clients", payload);
    setOpen(false);
    setForm({ type: "producer", name: "", doc: "", region: "", culture: "",
              classification: "B", potential: "medio", area_ha: 0 });
    setSkip(0);
    setAppliedQ(q);
    load(q, 0, limit);
  };

  const analyze = async (clientId) => {
    setAnalysisLoading(true);
    setAnalysis({ loading: true });
    try {
      const r = await api.post("/ai/marketing/analyze-client", { client_id: clientId });
      setAnalysis(r.data);
    } catch (e) {
      setAnalysis({ error: e?.response?.data?.detail || "Erro" });
    } finally { setAnalysisLoading(false); }
  };

  return (
    <div data-testid="clients-page">
      <PageHeader
        title="Clientes"
        subtitle="Produtores rurais e empresas, com classificacao por cultura, regiao, potencial e tier."
        actions={
          can("clients.create") ? (
            <button className="btn-primary flex items-center gap-2" onClick={() => setOpen(true)} data-testid="new-client-btn">
              <Plus size={16} /> Novo cliente
            </button>
          ) : null
        }
      />

      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && search()}
            placeholder="Buscar por nome, documento ou regiao..."
            className="input-field pl-9"
            data-testid="clients-search"
          />
        </div>
        <button className="btn-ghost" onClick={search} data-testid="clients-search-btn">Buscar</button>
      </div>

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState title="Sem clientes ainda" /> : (
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="clients-table">
              <thead><tr>
                <th>SEQ</th><th>Tipo</th><th>Nome</th><th>Regiao</th>
                <th>Cultura</th><th>Tier</th><th>Potencial</th><th>Area (ha)</th><th></th>
              </tr></thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} data-testid={`client-row-${c.seq_id}`}>
                    <td className="font-mono text-muted">#{c.seq_id}</td>
                    <td><StatusTag status={c.type} /></td>
                    <td className="font-medium">{c.name}</td>
                    <td className="text-muted">{c.region || "-"}</td>
                    <td>{(c.culture || []).map((x) => <span key={x} className="tag tag-muted mr-1">{x}</span>)}</td>
                    <td><StatusTag status={c.classification} /></td>
                    <td className="capitalize">{c.potential}</td>
                    <td className="font-mono">{c.area_ha?.toLocaleString("pt-BR") || 0}</td>
                    <td>
                      {can("ai.use") && (
                        <button
                          onClick={() => analyze(c.id)}
                          className="btn-ghost !py-1 !px-2 text-xs flex items-center gap-1"
                          data-testid={`analyze-${c.seq_id}`}
                        >
                          <Sparkles size={12} className="text-accent-yellow" /> IA
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && items.length > 0 && (
          <PaginationBar
            total={total}
            skip={skip}
            limit={limit}
            onPageChange={setSkip}
            onLimitChange={(value) => { setLimit(value); setSkip(0); }}
          />
        )}
      </Card>

      {open && can("clients.create") && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <form onSubmit={submit} onClick={(e) => e.stopPropagation()}
                className="card-surface p-6 w-full max-w-lg space-y-3" data-testid="new-client-modal">
            <div className="flex justify-between items-center">
              <h2 className="font-head font-bold text-xl">Novo cliente</h2>
              <button type="button" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="overline">Tipo</label>
                <select className="input-field" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  <option value="producer">Produtor</option>
                  <option value="company">Empresa</option>
                </select>
              </div>
              <div>
                <label className="overline">Tier</label>
                <select className="input-field" value={form.classification} onChange={(e) => setForm({ ...form, classification: e.target.value })}>
                  <option>A</option><option>B</option><option>C</option>
                </select>
              </div>
            </div>
            <div>
              <label className="overline">Nome</label>
              <input className="input-field" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="client-name-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="overline">CPF/CNPJ</label>
                <input className="input-field font-mono" value={form.doc} onChange={(e) => setForm({ ...form, doc: e.target.value })} />
              </div>
              <div>
                <label className="overline">Regiao</label>
                <input className="input-field" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="overline">Culturas (separadas por virgula)</label>
              <input className="input-field" value={form.culture} onChange={(e) => setForm({ ...form, culture: e.target.value })} placeholder="soja, milho" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="overline">Potencial</label>
                <select className="input-field" value={form.potential} onChange={(e) => setForm({ ...form, potential: e.target.value })}>
                  <option value="alto">Alto</option><option value="medio">Medio</option><option value="baixo">Baixo</option>
                </select>
              </div>
              <div>
                <label className="overline">Area (ha)</label>
                <input className="input-field font-mono" type="number" value={form.area_ha} onChange={(e) => setForm({ ...form, area_ha: e.target.value })} />
              </div>
            </div>
            <button type="submit" className="btn-primary w-full mt-3" data-testid="save-client-btn">Salvar</button>
          </form>
        </div>
      )}

      {analysis && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={() => setAnalysis(null)}>
          <div className="card-surface p-6 w-full max-w-2xl max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}
               data-testid="ai-analysis-modal">
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <Sparkles size={18} className="text-accent-yellow" />
                <h2 className="font-head font-bold text-xl">Analise - Agente Marketing</h2>
              </div>
              <button onClick={() => setAnalysis(null)}><X size={18} /></button>
            </div>
            {analysis.loading || analysisLoading ? <Loading /> :
              analysis.error ? <div className="text-accent-red">{analysis.error}</div> : (
              <>
                <div className="overline mb-2">Cliente</div>
                <div className="font-head text-lg font-semibold mb-4">{analysis.client_name}</div>
                <div className="overline mb-2">Analise</div>
                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-body" data-testid="analysis-text">{analysis.analysis}</pre>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
