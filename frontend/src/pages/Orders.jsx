import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState } from "../components/UI";
import { fmtBRL } from "../lib/utils";

const STATUS_FLOW = ["pending", "confirmed", "in_transit", "delivered"];

export default function Orders() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.get("/orders").then((r) => setItems(r.data.items)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const advance = async (o) => {
    const cur = STATUS_FLOW.indexOf(o.status);
    if (cur < 0 || cur >= STATUS_FLOW.length - 1) return;
    await api.patch(`/orders/${o.id}`, { status: STATUS_FLOW[cur + 1] });
    load();
  };

  return (
    <div data-testid="orders-page">
      <PageHeader title="Pedidos" subtitle="Pedidos de venda e compra com status logístico em tempo real." />

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> : (
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="orders-table">
              <thead><tr>
                <th>SEQ</th><th>Tipo</th><th>Cliente</th><th>Total</th>
                <th>Status</th><th>Logística</th><th></th>
              </tr></thead>
              <tbody>
                {items.map((o) => (
                  <tr key={o.id} data-testid={`order-row-${o.seq_id}`}>
                    <td className="font-mono text-muted">#{o.seq_id}</td>
                    <td><StatusTag status={o.type} /></td>
                    <td className="font-medium">{o.client_name}</td>
                    <td className="font-mono text-accent-yellow">{fmtBRL(o.total)}</td>
                    <td><StatusTag status={o.status} /></td>
                    <td><StatusTag status={o.logistic_status} /></td>
                    <td>
                      {STATUS_FLOW.indexOf(o.status) < STATUS_FLOW.length - 1 && (
                        <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => advance(o)}
                                data-testid={`advance-${o.seq_id}`}>
                          Avançar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
