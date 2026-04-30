import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState, PaginationBar } from "../components/UI";

export default function Logistics() {
  const [vehicles, setVehicles] = useState([]);
  const [cargas, setCargas] = useState([]);
  const [cargasTotal, setCargasTotal] = useState(0);
  const [cargasSkip, setCargasSkip] = useState(0);
  const [cargasLimit, setCargasLimit] = useState(20);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get("/logistics/vehicles", { params: { limit: 10 } }),
      api.get("/logistics/cargas", { params: { skip: cargasSkip, limit: cargasLimit } }),
    ]).then(([v, c]) => {
      setVehicles(v.data.items);
      setCargas(c.data.items);
      setCargasTotal(c.data.total || 0);
    }).finally(() => setLoading(false));
  }, [cargasSkip, cargasLimit]);

  if (loading) return <Loading />;

  return (
    <div data-testid="logistics-page">
      <PageHeader title="Logistica" subtitle="Frota e cargas em patio, em rota e entregues." />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2 !p-0 overflow-hidden" lift={false}>
          <div className="overline px-4 pt-4 mb-3">Cargas</div>
          {cargas.length === 0 ? <EmptyState /> : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr>
                  <th>SEQ</th><th>Placa</th><th>Motorista</th><th>Origem</th><th>Destino</th><th>Status</th>
                </tr></thead>
                <tbody>
                  {cargas.map((c) => (
                    <tr key={c.id} data-testid={`carga-${c.seq_id}`}>
                      <td className="font-mono text-muted">#{c.seq_id}</td>
                      <td className="font-mono">{c.vehicle_plate}</td>
                      <td>{c.driver}</td>
                      <td className="text-muted text-sm">{c.origin}</td>
                      <td className="text-muted text-sm">{c.destination}</td>
                      <td><StatusTag status={c.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {cargas.length > 0 && (
            <PaginationBar
              total={cargasTotal}
              skip={cargasSkip}
              limit={cargasLimit}
              onPageChange={setCargasSkip}
              onLimitChange={(value) => { setCargasLimit(value); setCargasSkip(0); }}
            />
          )}
        </Card>

        <Card lift={false}>
          <div className="overline mb-3">Frota</div>
          <div className="space-y-2">
            {vehicles.map((v) => (
              <div key={v.id} className="flex items-center justify-between gap-3 p-3 rounded-lg bg-app-bg" data-testid={`vehicle-${v.seq_id}`}>
                <div className="min-w-0">
                  <div className="font-mono font-semibold truncate">{v.plate}</div>
                  <div className="text-muted text-xs truncate">{v.type} - {v.capacity_ton}t</div>
                </div>
                <StatusTag status={v.status} />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
