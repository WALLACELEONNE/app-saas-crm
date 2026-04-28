import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState } from "../components/UI";
import { fmtBRL } from "../lib/utils";

export default function Products() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/products").then((r) => setItems(r.data.items)).finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="products-page">
      <PageHeader title="Produtos" subtitle="Insumos agrícolas e grãos negociados pelo trading desk." />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? <Loading /> : items.length === 0 ? <EmptyState /> :
          items.map((p) => (
            <Card key={p.id} testid={`product-${p.seq_id}`}>
              <div className="flex justify-between items-start">
                <div>
                  <div className="overline">SKU {p.sku}</div>
                  <div className="font-head font-semibold text-lg mt-1">{p.name}</div>
                </div>
                <StatusTag status={p.category} />
              </div>
              <div className="mt-4 flex justify-between items-end">
                <div>
                  <div className="overline">Preço atual</div>
                  <div className="font-mono text-2xl font-semibold text-accent-yellow mt-1">{fmtBRL(p.current_price)}</div>
                </div>
                <div className="text-muted text-sm">/ {p.unit}</div>
              </div>
            </Card>
          ))
        }
      </div>
    </div>
  );
}
