import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState, PaginationBar } from "../components/UI";

export default function Support() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/support", { params: { skip, limit } })
      .then((r) => { setItems(r.data.items); setTotal(r.data.total || 0); })
      .finally(() => setLoading(false));
  }, [skip, limit]);

  return (
    <div data-testid="support-page">
      <PageHeader title="Suporte / Pos-venda" subtitle="Chamados, SLAs e historico do atendimento ao cliente." />

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> : (
          <div className="overflow-x-auto">
            <table className="data-table" data-testid="tickets-table">
              <thead><tr>
                <th>SEQ</th><th>Cliente</th><th>Assunto</th><th>Prioridade</th><th>SLA</th><th>Status</th>
              </tr></thead>
              <tbody>
                {items.map((t) => (
                  <tr key={t.id} data-testid={`ticket-${t.seq_id}`}>
                    <td className="font-mono text-muted">#{t.seq_id}</td>
                    <td className="font-medium">{t.client_name}</td>
                    <td>{t.subject}</td>
                    <td><StatusTag status={t.priority} /></td>
                    <td className="font-mono">{t.sla_hours}h</td>
                    <td><StatusTag status={t.status} /></td>
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
