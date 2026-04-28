import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card, PageHeader } from "../components/UI";
import { GitBranch, Database, Layers, Cloud, RefreshCw, Shield, Eye } from "lucide-react";

const SECTIONS = [
  {
    icon: Layers, color: "text-primary", title: "Arquitetura Geral",
    body: `Modular monolith em Python/FastAPI, preparado para evoluir para microsserviços. Cada módulo
(clients, pipeline, contracts, orders, logistics, support, ai_agents, sync, integrations) é desacoplado
via Event Bus interno. O backend expõe APIs REST sob /api e dispara eventos de domínio que alimentam:
(1) o feed de sincronização mobile, (2) o hub de integrações ERP, e (3) os agentes de IA.

Componentes principais:
• API Gateway (FastAPI + middlewares CORS / Auth)
• Auth Service (JWT access + refresh, RBAC)
• CRM Core (modules/*)
• Integration Hub (connector registry + webhook receiver + outbox)
• AI Agents Service (emergentintegrations + GPT-5.2)
• Event Bus (in-memory async; trocável por RabbitMQ/Kafka via interface idêntica)`
  },
  {
    icon: Database, color: "text-accent-yellow", title: "Modelagem & Banco",
    body: `MongoDB (modo CRM) com convenção rígida em todas as coleções principais:
• id (UUID v4)             — chave estável, não-sequencial
• seq_id (int monotônico)  — gerado via atomic counter (db.counters)
• tenant_id                — multi-tenant ready
• created_at / updated_at  — UTC ISO
• deleted_at               — soft delete (null = vivo)
• created_by / updated_by  — auditoria

Coleções: users, counters, clients, pipeline_stages, opportunities, interactions,
contracts, orders, products, vehicles, cargas, tickets, ai_sessions, audit_logs,
sync_events, integration_events, ai_outputs.

Índices: (tenant_id, seq_id), id único, deleted_at, updated_at.
Auditoria: cada CRUD grava antes/depois em audit_logs e publica evento de domínio.`
  },
  {
    icon: RefreshCw, color: "text-accent-orange", title: "Sincronização Offline-first (Mobile)",
    body: `Estratégia: incremental, bidirecional, last-write-wins por updated_at + seq_id servidor.

PULL  /api/sync/pull  { since: ISO8601, entities: [...] }
   → retorna registros com updated_at > since por entidade (paginado).

PUSH  /api/sync/push  { device_id, records: [{entity, op, data}] }
   → upsert com conflict detection: se server.updated_at > client.updated_at,
     registra conflito (server_newer) e devolve para o app reconciliar.

Cliente (RN/Flutter):
• SQLite local com mesmas colunas (id, seq_id, *_at, deleted_at)
• Fila local de eventos (event queue) — ações offline ficam pendentes
• Retry exponencial (backoff 2^n, máx 6 tentativas) com jitter
• Sync ativo (botão) + automático (intervalo) + push (background)
• Versionamento por updated_at; conflitos são reportados e exibidos ao usuário`
  },
  {
    icon: Cloud, color: "text-primary", title: "Integração com ERP (Hub)",
    body: `Hub desacoplado em modules/integrations:
• Connector Registry  — SAP S/4HANA, Oracle EBS, TOTVS Protheus (registráveis)
• Webhook inbound     — POST /api/integrations/webhook/{source} (HMAC em prod)
• Outbox pattern      — eventos de domínio publicados no Event Bus alimentam workers
                          conectores que entregam via REST/IDoc/SOAP.
• Padrões suportados  — REST, Webhooks, mensageria event-driven (RabbitMQ/Kafka prod).
• Idempotência        — chave (source, external_id) para dedupe de inbound.

Fluxo típico (venda → ERP SAP):
1) Pedido criado em /api/orders → emite "orders.create"
2) Worker SAP consome evento, mapeia para BAPI/IDoc
3) Persiste correlation_id em integration_events
4) Webhook de retorno (status SAP) → atualiza order.status`
  },
  {
    icon: Shield, color: "text-accent-red", title: "Segurança",
    body: `• JWT access (60min) + refresh (14 dias) HS256
• Senhas: bcrypt
• RBAC: roles admin/trader/sales/support
• Multi-tenant: todo dado é escopado por tenant_id em queries
• Soft delete + audit log imutável
• Webhooks externos: HMAC-SHA256 (configurar por connector em prod)
• CORS configurável via .env`
  },
  {
    icon: Eye, color: "text-accent-yellow", title: "Observabilidade",
    body: `• Logs estruturados (uvicorn + handlers)
• Audit trail em audit_logs (entity, action, before, after, user)
• Recent activity feed no Dashboard
• Event history (in-memory) acessível em /api/integrations/events
• Health check em /api/health (DB ping + versão)`
  },
  {
    icon: GitBranch, color: "text-primary", title: "Escalabilidade",
    body: `MVP: monolith modular + MongoDB single + event bus in-memory.

Caminho de evolução (sem breaking changes):
1) Substituir EventBus por RabbitMQ/Kafka (mesma interface publish/subscribe)
2) Extrair AI Agents Service (FastAPI separado, mesmo schema MongoDB)
3) Extrair Integration Hub (worker pool consumindo a fila)
4) Adicionar Read replicas MongoDB / sharding por tenant_id
5) CDN + cache no API Gateway para endpoints read-heavy (dashboard, products)
6) Mobile: sync delta via change streams MongoDB`
  },
];

export default function Architecture() {
  const [stats, setStats] = useState(null);
  const [connectors, setConnectors] = useState([]);
  const [events, setEvents] = useState([]);
  const [syncInfo, setSyncInfo] = useState(null);

  useEffect(() => {
    api.get("/health").then((r) => setStats(r.data)).catch(() => {});
    api.get("/integrations/connectors").then((r) => setConnectors(r.data.connectors));
    api.get("/integrations/events").then((r) => setEvents(r.data.items));
    api.get("/sync/info").then((r) => setSyncInfo(r.data));
  }, []);

  return (
    <div data-testid="architecture-page">
      <PageHeader
        title="Arquitetura"
        subtitle="Documentação técnica viva — backend modular, sync offline-first, hub ERP e agentes de IA."
      />

      {/* Live system telemetry */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
        <Card lift={false}>
          <div className="overline">API</div>
          <div className="font-head font-semibold mt-1">v1.0.0</div>
          <div className="text-muted text-xs mt-1 font-mono">{stats?.status || "—"} · DB {stats?.db || "—"}</div>
        </Card>
        <Card lift={false}>
          <div className="overline">Conectores ERP</div>
          <div className="font-head font-semibold mt-1">{connectors.length}</div>
          <div className="text-muted text-xs mt-1">{connectors.map((c) => c.name).join(" · ")}</div>
        </Card>
        <Card lift={false}>
          <div className="overline">Sync</div>
          <div className="font-head font-semibold mt-1">{syncInfo?.syncable_entities?.length || 0} entidades</div>
          <div className="text-muted text-xs mt-1 font-mono">{syncInfo?.strategy || "—"}</div>
        </Card>
        <Card lift={false}>
          <div className="overline">Eventos</div>
          <div className="font-head font-semibold mt-1">{events.length}</div>
          <div className="text-muted text-xs mt-1">no buffer in-memory</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SECTIONS.map((s) => (
          <Card key={s.title} testid={`arch-${s.title}`}>
            <div className="flex items-center gap-2 mb-3">
              <s.icon className={s.color} size={18} strokeWidth={1.6} />
              <div className="font-head font-bold text-lg">{s.title}</div>
            </div>
            <pre className="whitespace-pre-wrap text-sm text-text-main/90 font-body leading-relaxed">{s.body}</pre>
          </Card>
        ))}
      </div>

      <Card className="mt-4" lift={false} testid="arch-events">
        <div className="overline mb-2">Últimos eventos de domínio (buffer in-memory)</div>
        {events.length === 0 ? <div className="text-muted text-sm">Sem eventos ainda. Crie um cliente ou contrato para popular.</div> : (
          <div className="space-y-1 max-h-72 overflow-auto font-mono text-xs">
            {events.map((e, i) => (
              <div key={i} className="flex gap-3 border-b border-border-subtle py-1">
                <span className="text-muted">{new Date(e.timestamp).toLocaleTimeString("pt-BR")}</span>
                <span className="text-primary">{e.topic}</span>
                <span className="text-muted truncate">{JSON.stringify(e.payload).slice(0, 90)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="mt-4" lift={false} testid="arch-diagram">
        <div className="overline mb-3">Diagrama (texto)</div>
        <pre className="text-xs font-mono leading-snug overflow-auto">
{`┌─────────────────────────────────────────────────────────────────────┐
│                         WEB BACKOFFICE (React)                       │
│   Dashboard · Clientes · Pipeline · Contratos · Pedidos · IA Chat    │
└─────────────────────────────────────────────────────────────────────┘
                          ▲                ▲
                          │ /api (HTTPS)   │ chat session (multi-turn)
                          │                │
                          ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (FastAPI · /api/*)                    │
│  Auth(JWT)  ·  CORS  ·  Tenant Scope  ·  RBAC                        │
└─────────────────────────────────────────────────────────────────────┘
                  │       │        │           │
   ┌──────────────┘       │        │           └──────────────┐
   ▼                      ▼        ▼                          ▼
┌──────────┐  ┌──────────────┐  ┌──────────────┐    ┌─────────────────┐
│   CRM    │  │  AI Agents   │  │ Integration  │    │  Mobile Sync    │
│ Modules  │  │ (GPT-5.2)    │  │   Hub (ERP)  │    │  (offline-first)│
│ (DDD)    │  │ - marketing  │  │ - SAP        │    │ pull · push     │
│          │  │ - sales      │  │ - Oracle     │    │ LWW · seq_id    │
│          │  │ - channel    │  │ - TOTVS      │    │                 │
└────┬─────┘  └──────┬───────┘  └──────┬───────┘    └────────┬────────┘
     │               │                  │                     │
     └───────┬───────┴──────────────────┴─────────────────────┘
             ▼
       ┌──────────────┐
       │  EVENT BUS   │  (in-memory dev · RabbitMQ/Kafka prod)
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │  MongoDB     │  ← UUID + SEQ_ID + soft delete + audit
       └──────────────┘`}
        </pre>
      </Card>
    </div>
  );
}
