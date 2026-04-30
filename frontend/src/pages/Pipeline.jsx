import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeader, Loading } from "../components/UI";
import { fmtBRL } from "../lib/utils";
import { useAuth } from "../lib/auth";
import { Sparkles, X, GripVertical } from "lucide-react";

export default function Pipeline() {
  const { can } = useAuth();
  const [board, setBoard] = useState(null);
  const [drag, setDrag] = useState(null);
  const [summary, setSummary] = useState(null);

  const load = () => api.get("/pipeline/board").then((r) => setBoard(r.data));
  useEffect(() => { load(); }, []);

  const handleDragStart = (opp) => {
    if (can("pipeline.move")) setDrag(opp);
  };

  const handleDrop = async (stage) => {
    if (!can("pipeline.move")) return;
    if (!drag || drag.stage_id === stage.id) { setDrag(null); return; }
    await api.post(`/pipeline/opportunities/${drag.id}/move`, { stage_id: stage.id, stage_name: stage.name });
    setDrag(null);
    load();
  };

  const summarize = async (opp) => {
    setSummary({ loading: true, opp });
    try {
      const r = await api.post("/ai/sales/summarize-opportunity", { opportunity_id: opp.id });
      setSummary({ ...r.data, opp });
    } catch (e) {
      setSummary({ error: e?.response?.data?.detail || "Erro" , opp });
    }
  };

  if (!board) return <Loading />;

  return (
    <div data-testid="pipeline-page">
      <PageHeader
        title="Pipeline de Vendas"
        subtitle={`${board.total_opportunities} oportunidades - ${fmtBRL(board.total_value)} potenciais.`}
      />

      <div className="flex gap-4 overflow-x-auto pb-4" data-testid="kanban-board">
        {board.stages.map((stage) => (
          <div
            key={stage.id}
            className="kanban-col"
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => handleDrop(stage)}
            data-testid={`kanban-stage-${stage.name}`}
          >
            <header className="flex items-center justify-between sticky top-0 bg-surface-sidebar pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ background: stage.color }} />
                <span className="font-head font-semibold text-sm">{stage.name}</span>
                <span className="tag tag-muted !text-[0.65rem]">{stage.opportunities.length}</span>
              </div>
              <div className="text-xs font-mono text-muted">{fmtBRL(stage.total_value)}</div>
            </header>
            <div className="flex flex-col gap-2 overflow-y-auto pr-1">
              {stage.opportunities.map((o) => (
                <div
                  key={o.id}
                  className={`kanban-card ${drag?.id === o.id ? "dragging" : ""}`}
                  draggable={can("pipeline.move")}
                  onDragStart={() => handleDragStart(o)}
                  data-testid={`opp-${o.seq_id}`}
                >
                  <div className="flex items-start gap-2 mb-1">
                    {can("pipeline.move") && <GripVertical size={13} className="text-muted mt-0.5" />}
                    <div className="font-medium text-sm leading-tight">{o.title}</div>
                  </div>
                  <div className="text-xs text-muted ml-5">{o.client_name}</div>
                  <div className="flex items-center justify-between mt-3 ml-5">
                    <div className="font-mono text-[0.78rem] text-accent-yellow">{fmtBRL(o.value)}</div>
                    <span className="tag tag-muted !text-[0.65rem]">{o.probability}%</span>
                  </div>
                  {can("ai.use") && (
                    <button
                      className="btn-ghost w-full mt-3 !py-1 text-xs flex items-center justify-center gap-1"
                      onClick={() => summarize(o)}
                      data-testid={`summarize-${o.seq_id}`}
                    >
                      <Sparkles size={12} className="text-accent-yellow" /> Resumo IA
                    </button>
                  )}
                </div>
              ))}
              {stage.opportunities.length === 0 && (
                <div className="text-muted text-xs italic px-2 py-3">Sem oportunidades</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {summary && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={() => setSummary(null)}>
          <div className="card-surface p-6 w-full max-w-2xl max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}
               data-testid="summary-modal">
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                <Sparkles size={18} className="text-accent-yellow" />
                <h2 className="font-head font-bold text-xl">Agente Vendas - Resumo</h2>
              </div>
              <button onClick={() => setSummary(null)}><X size={18} /></button>
            </div>
            <div className="overline mb-1">Oportunidade</div>
            <div className="font-head text-lg font-semibold mb-4">{summary.opp.title}</div>
            {summary.loading ? <Loading /> : summary.error ? (
              <div className="text-accent-red">{summary.error}</div>
            ) : (
              <pre className="whitespace-pre-wrap text-sm leading-relaxed font-body">{summary.summary}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
