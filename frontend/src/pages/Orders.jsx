import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState, PaginationBar } from "../components/UI";
import { fmtBRL } from "../lib/utils";
import { useAuth } from "../lib/auth";

const STATUS_FLOW = ["pending", "confirmed", "in_transit", "delivered"];

export default function Orders() {
  const { can } = useAuth();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    api.get("/orders", { params: { skip, limit } })
      .then((r) => { setItems(r.data.items); setTotal(r.data.total || 0); })
      .finally(() => setLoading(false));
  }, [skip, limit]);

  useEffect(() => { load(); }, [load]);

  const advance = async (o) => {
    const cur = STATUS_FLOW.indexOf(o.status);
    if (cur < 0 || cur >= STATUS_FLOW.length - 1) return;
    await api.patch(`/orders/${o.id}`, { status: STATUS_FLOW[cur + 1] });
    load();
  };

  return (
    <div data-testid="orders-page">
      <PageHeader title="Pedidos" subtitle="Pedidos de venda e compra com status logistico em tempo real." />

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> : (
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="orders-table">
              <thead><tr>
                <th>SEQ</th><th>Tipo</th><th>Cliente</th><th>Total</th>
                <th>Status</th><th>Logistica</th><th></th>
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
                      {can("orders.update_status") && STATUS_FLOW.indexOf(o.status) < STATUS_FLOW.length - 1 && (
                        <button className="btn-ghost !py-1 !px-2 text-xs" onClick={() => advance(o)}
                                data-testid={`advance-${o.seq_id}`}>
                          Avancar
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
    </div>
  );
}
