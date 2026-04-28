import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState } from "../components/UI";

export default function Support() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/support").then((r) => setItems(r.data.items)).finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="support-page">
      <PageHeader title="Suporte / Pós-venda" subtitle="Chamados, SLAs e histórico do atendimento ao cliente." />

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> : (
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
        )}
      </Card>
    </div>
  );
}
