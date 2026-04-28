import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader, Loading, StatusTag, EmptyState } from "../components/UI";

export default function Logistics() {
  const [vehicles, setVehicles] = useState([]);
  const [cargas, setCargas] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get("/logistics/vehicles"),
      api.get("/logistics/cargas"),
    ]).then(([v, c]) => {
      setVehicles(v.data.items);
      setCargas(c.data.items);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return <Loading />;

  return (
    <div data-testid="logistics-page">
      <PageHeader title="Logística" subtitle="Frota e cargas em pátio, em rota e entregues." />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2" lift={false}>
          <div className="overline mb-3">Cargas</div>
          {cargas.length === 0 ? <EmptyState /> : (
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
          )}
        </Card>

        <Card lift={false}>
          <div className="overline mb-3">Frota</div>
          <div className="space-y-3">
            {vehicles.map((v) => (
              <div key={v.id} className="flex items-center justify-between p-3 rounded-lg bg-app-bg" data-testid={`vehicle-${v.seq_id}`}>
                <div>
                  <div className="font-mono font-semibold">{v.plate}</div>
                  <div className="text-muted text-xs">{v.type} · {v.capacity_ton}t</div>
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
