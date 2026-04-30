import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState, PaginationBar } from "../components/UI";
import { fmtBRL, fmtTon } from "../lib/utils";
import { useAuth } from "../lib/auth";
import { Plus, X } from "lucide-react";

export default function Contracts() {
  const { can } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [clients, setClients] = useState([]);
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({
    type: "sell", client_id: "", product_id: "",
    volume: 0, price: 0, currency: "BRL",
    delivery_window: "2026-Q2", status: "active",
  });

  const load = useCallback(() => {
    setLoading(true);
    api.get("/contracts", { params: { skip, limit } })
      .then((r) => { setItems(r.data.items); setTotal(r.data.total || 0); })
      .finally(() => setLoading(false));
  }, [skip, limit]);

  useEffect(() => {
    load();
    api.get("/clients", { params: { limit: 200 } }).then((r) => setClients(r.data.items));
    api.get("/products", { params: { limit: 200 } }).then((r) => setProducts(r.data.items));
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const cli = clients.find((c) => c.id === form.client_id);
    const prod = products.find((p) => p.id === form.product_id);
    await api.post("/contracts", {
      ...form,
      client_name: cli?.name,
      product_name: prod?.name,
      volume: Number(form.volume),
      price: Number(form.price),
      signed_at: new Date().toISOString().split("T")[0],
    });
    setOpen(false);
    setSkip(0);
    load();
  };

  return (
    <div data-testid="contracts-page">
      <PageHeader
        title="Contratos"
        subtitle="Compra, venda e barter de graos vinculados ao hub ERP."
        actions={
          can("contracts.create") ? (
            <button className="btn-primary flex items-center gap-2" onClick={() => setOpen(true)} data-testid="new-contract-btn">
              <Plus size={16} /> Novo contrato
            </button>
          ) : null
        }
      />

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> : (
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="contracts-table">
              <thead><tr>
                <th>SEQ</th><th>Tipo</th><th>Cliente</th><th>Produto</th>
                <th>Volume</th><th>Preco</th><th>Total</th><th>Status</th>
              </tr></thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.id} data-testid={`contract-row-${c.seq_id}`}>
                    <td className="font-mono text-muted">#{c.seq_id}</td>
                    <td><StatusTag status={c.type} /></td>
                    <td className="font-medium">{c.client_name}</td>
                    <td>{c.product_name}</td>
                    <td className="font-mono">{fmtTon(c.volume)}</td>
                    <td className="font-mono text-accent-yellow">{c.type === "barter" ? "-" : fmtBRL(c.price)}</td>
                    <td className="font-mono">{c.type === "barter" ? "-" : fmtBRL((c.volume || 0) * (c.price || 0))}</td>
                    <td><StatusTag status={c.status} /></td>
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

      {open && can("contracts.create") && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <form onSubmit={submit} onClick={(e) => e.stopPropagation()}
                className="card-surface p-6 w-full max-w-lg space-y-3" data-testid="new-contract-modal">
            <div className="flex justify-between items-center">
              <h2 className="font-head font-bold text-xl">Novo contrato</h2>
              <button type="button" onClick={() => setOpen(false)}><X size={18} /></button>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="overline">Tipo</label>
                <select className="input-field" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  <option value="sell">Venda</option>
                  <option value="buy">Compra</option>
                  <option value="barter">Barter</option>
                </select>
              </div>
              <div>
                <label className="overline">Status</label>
                <select className="input-field" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                  <option value="draft">Rascunho</option>
                  <option value="active">Ativo</option>
                  <option value="settled">Liquidado</option>
                </select>
              </div>
            </div>
            <div>
              <label className="overline">Cliente</label>
              <select className="input-field" required value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })}>
                <option value="">Selecionar...</option>
                {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="overline">Produto</label>
              <select className="input-field" required value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value })}>
                <option value="">Selecionar...</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="overline">Volume (ton)</label>
                <input className="input-field font-mono" type="number" required value={form.volume} onChange={(e) => setForm({ ...form, volume: e.target.value })} />
              </div>
              <div>
                <label className="overline">Preco (R$/ton)</label>
                <input className="input-field font-mono" type="number" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
              </div>
              <div>
                <label className="overline">Janela</label>
                <input className="input-field" value={form.delivery_window} onChange={(e) => setForm({ ...form, delivery_window: e.target.value })} />
              </div>
            </div>
            <button type="submit" className="btn-primary w-full mt-3" data-testid="save-contract-btn">Salvar contrato</button>
          </form>
        </div>
      )}
    </div>
  );
}
