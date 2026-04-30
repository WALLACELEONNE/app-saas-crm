import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState, PaginationBar } from "../components/UI";
import { fmtBRL } from "../lib/utils";

export default function Products() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(20);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/products", { params: { skip, limit } })
      .then((r) => { setItems(r.data.items); setTotal(r.data.total || 0); })
      .finally(() => setLoading(false));
  }, [skip, limit]);

  return (
    <div data-testid="products-page">
      <PageHeader title="Produtos" subtitle="Insumos agricolas e graos negociados pelo trading desk." />

      <Card lift={false} className="!p-0 overflow-hidden">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 p-4">
            {items.map((p) => (
              <div key={p.id} className="border border-border-subtle rounded-lg p-4" data-testid={`product-${p.seq_id}`}>
                <div className="flex justify-between items-start gap-3">
                  <div className="min-w-0">
                    <div className="overline truncate">SKU {p.sku}</div>
                    <div className="font-head font-semibold text-base mt-1 truncate">{p.name}</div>
                  </div>
                  <StatusTag status={p.category} />
                </div>
                <div className="mt-4 flex justify-between items-end">
                  <div>
                    <div className="overline">Preco atual</div>
                    <div className="font-mono text-xl font-semibold text-accent-yellow mt-1">{fmtBRL(p.current_price)}</div>
                  </div>
                  <div className="text-muted text-sm">/ {p.unit}</div>
                </div>
              </div>
            ))}
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
