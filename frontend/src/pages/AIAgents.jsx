import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader } from "../components/UI";
import { Bot, Gauge, MessageSquare, Plus, Send, Sparkles } from "lucide-react";

function InlineText({ text }) {
  const parts = String(text || "").split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, index) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={index}>{part.slice(2, -2)}</strong>;
        }
        return <React.Fragment key={index}>{part}</React.Fragment>;
      })}
    </>
  );
}

function AIMessage({ text }) {
  const lines = String(text || "").split(/\r?\n/);
  const blocks = [];
  let list = [];

  const flushList = () => {
    if (list.length) {
      blocks.push({ type: "list", items: list });
      list = [];
    }
  };

  lines.forEach((raw) => {
    const line = raw.trim();
    if (!line) {
      flushList();
      return;
    }
    const bullet = line.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      list.push(bullet[1]);
      return;
    }
    flushList();
    blocks.push({ type: "p", text: line });
  });
  flushList();

  return (
    <div className="ai-message">
      {blocks.map((block, index) => {
        if (block.type === "list") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}><InlineText text={item} /></li>
              ))}
            </ul>
          );
        }
        return <p key={index}><InlineText text={block.text} /></p>;
      })}
    </div>
  );
}

function plainPreview(text) {
  return String(text || "-")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/^[-*]\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim() || "-";
}

export default function AIAgents() {
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [clients, setClients] = useState([]);
  const [usage, setUsage] = useState(null);
  const [newOpen, setNewOpen] = useState(false);
  const [newClientId, setNewClientId] = useState("");
  const scroller = useRef(null);

  const loadSessions = () => api.get("/ai/channel/sessions").then((r) => setSessions(r.data));
  const loadUsage = () => api.get("/ai/usage").then((r) => setUsage(r.data)).catch(() => {});

  useEffect(() => {
    loadSessions();
    loadUsage();
    api.get("/clients", { params: { limit: 200 } }).then((r) => setClients(r.data.items));
  }, []);

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [active]);

  const start = async () => {
    const cli = clients.find((c) => c.id === newClientId);
    const r = await api.post("/ai/channel/sessions", {
      client_id: newClientId || null,
      title: cli ? `Conversa - ${cli.name}` : "Nova conversa",
    });
    setNewOpen(false);
    setNewClientId("");
    await loadSessions();
    setActive(r.data);
  };

  const send = async (e) => {
    e.preventDefault();
    if (!text.trim() || !active) return;
    setSending(true);
    const userText = text;
    setText("");
    setActive((a) => ({ ...a, messages: [...(a.messages || []), { role: "user", text: userText, at: new Date().toISOString() }] }));
    try {
      const r = await api.post(`/ai/channel/sessions/${active.id}/messages`, { text: userText });
      setActive((a) => ({ ...a, messages: r.data.messages }));
      loadUsage();
      loadSessions();
    } catch (e) {
      setActive((a) => ({ ...a, messages: [...(a.messages || []), { role: "assistant", text: "Erro: " + (e?.response?.data?.detail || e.message), at: new Date().toISOString() }] }));
    } finally {
      setSending(false);
    }
  };

  return (
    <div data-testid="ai-page">
      <PageHeader
        title="Agentes de IA"
        subtitle="Agentes com contexto CRM, cache, rate limit e medicao de uso por tenant."
      />

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card className="border-l-4 !border-l-primary">
          <div className="flex items-center gap-2 mb-2"><Sparkles size={16} className="text-primary" /><div className="overline">Marketing</div></div>
          <div className="font-head font-semibold text-lg">Prospeccao</div>
          <p className="text-muted text-sm mt-2">Analise de perfil, score de potencial e sugestao de abordagem na tela Clientes.</p>
        </Card>
        <Card className="border-l-4 !border-l-accent-yellow">
          <div className="flex items-center gap-2 mb-2"><Sparkles size={16} className="text-accent-yellow" /><div className="overline">Vendas</div></div>
          <div className="font-head font-semibold text-lg">Negociacao</div>
          <p className="text-muted text-sm mt-2">Resumo de oportunidades, proximos passos e riscos na tela Pipeline.</p>
        </Card>
        <Card className="border-l-4 !border-l-accent-orange">
          <div className="flex items-center gap-2 mb-2"><Sparkles size={16} className="text-accent-orange" /><div className="overline">Canal</div></div>
          <div className="font-head font-semibold text-lg">Chat CRM</div>
          <p className="text-muted text-sm mt-2">Conversa com contexto de pedidos, contratos, status e chamados.</p>
        </Card>
        <Card lift={false}>
          <div className="flex items-center gap-2 mb-2"><Gauge size={16} className="text-primary" /><div className="overline">Uso IA</div></div>
          <div className="font-head font-semibold text-lg">{usage?.user_day?.calls || 0}/{usage?.policy?.user_daily_limit || "-"} hoje</div>
          <p className="text-muted text-xs mt-2 font-mono">{usage?.provider || "stub"} - {usage?.model || "-"}</p>
          <p className="text-muted text-xs mt-1 font-mono">{usage?.user_day?.blocked || 0} bloqueadas</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4" style={{ minHeight: 520 }}>
        <Card lift={false} className="lg:col-span-1 !p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <div className="overline">Conversas</div>
            <button onClick={() => setNewOpen(true)} className="btn-ghost !py-1 !px-2 text-xs flex items-center gap-1" data-testid="new-chat-btn">
              <Plus size={13} /> Nova
            </button>
          </div>
          <div className="flex flex-col gap-2 flex-1 overflow-auto">
            {sessions.length === 0 && <div className="text-muted text-sm">Nenhuma conversa ainda.</div>}
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => api.get(`/ai/channel/sessions/${s.id}`).then((r) => setActive(r.data))}
                className={`text-left p-3 rounded-lg border transition ${active?.id === s.id ? "border-primary bg-primary/5" : "border-border-subtle hover:border-border-bright"}`}
                data-testid={`session-${s.seq_id}`}
              >
                <div className="text-sm font-medium truncate">{s.title}</div>
                <div className="text-xs text-muted truncate">{plainPreview((s.messages || []).slice(-1)[0]?.text)}</div>
              </button>
            ))}
          </div>
        </Card>

        <Card lift={false} className="lg:col-span-3 !p-0 flex flex-col" testid="chat-panel">
          {!active ? (
            <div className="flex-1 flex flex-col items-center justify-center text-muted p-12">
              <MessageSquare size={36} className="text-primary mb-3" strokeWidth={1.4} />
              <div className="font-head text-lg font-semibold text-text-main">Selecione uma conversa</div>
              <div className="text-sm">ou inicie uma nova com um cliente vinculado.</div>
            </div>
          ) : (
            <>
              <div className="px-5 py-4 border-b border-border-subtle flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/40 flex items-center justify-center">
                  <Bot size={18} className="text-primary" />
                </div>
                <div>
                  <div className="font-head font-semibold">{active.title}</div>
                  <div className="text-xs text-muted">{usage?.provider || "LLM"} - contexto CRM - rate limit ativo</div>
                </div>
              </div>
              <div ref={scroller} className="flex-1 overflow-auto p-5 space-y-3 bg-surface-card-2/40" style={{ maxHeight: 420 }}>
                {(active.messages || []).length === 0 && (
                  <div className="text-muted text-sm">Envie a primeira mensagem para comecar a conversa.</div>
                )}
                {(active.messages || []).map((m, i) => (
                  <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={m.role === "user" ? "bubble-user" : "bubble-ai"} data-testid={`msg-${i}`}>
                      {m.role === "user" ? m.text : <AIMessage text={m.text} />}
                    </div>
                  </div>
                ))}
                {sending && <div className="flex"><div className="bubble-ai animate-pulse">Pensando...</div></div>}
              </div>
              <form onSubmit={send} className="p-4 border-t border-border-subtle flex gap-2">
                <input
                  className="input-field flex-1"
                  placeholder="Pergunte sobre pedidos, contratos, status logistico..."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  data-testid="chat-input"
                />
                <button type="submit" className="btn-primary flex items-center gap-2" disabled={sending || !text.trim()} data-testid="chat-send">
                  <Send size={15} /> Enviar
                </button>
              </form>
            </>
          )}
        </Card>
      </div>

      {newOpen && (
        <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={() => setNewOpen(false)}>
          <div className="card-surface p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()} data-testid="new-chat-modal">
            <h2 className="font-head font-bold text-lg mb-4">Nova conversa</h2>
            <label className="overline">Cliente vinculado (opcional)</label>
            <select className="input-field mb-4" value={newClientId} onChange={(e) => setNewClientId(e.target.value)}>
              <option value="">Sem cliente vinculado</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <button className="btn-primary w-full" onClick={start} data-testid="start-chat-btn">Iniciar conversa</button>
          </div>
        </div>
      )}
    </div>
  );
}
