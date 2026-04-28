# Agro CRM — Arquitetura

CRM standalone para o agronegócio, com foco em trading de grãos, revendas, barter e relacionamento com produtores. Backend modular monolith em FastAPI/MongoDB, frontend React, 3 agentes de IA (GPT-5.2) e API de sincronização offline-first para mobile.

## 1. Visão Geral

```
┌─────────────────────────────────────────────────────────────────┐
│                    WEB BACKOFFICE (React)                        │
│  Dashboard · Clientes · Pipeline (Kanban) · Contratos · Pedidos  │
│  Produtos · Logística · Suporte · Agentes IA · Arquitetura       │
└─────────────────────────────────────────────────────────────────┘
                       │ HTTPS /api/*
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                API GATEWAY (FastAPI · /api/*)                    │
│   Auth(JWT) · CORS · Tenant Scope · RBAC · CRUD genérico         │
└─────────────────────────────────────────────────────────────────┘
        │              │                │                │
        ▼              ▼                ▼                ▼
 ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
 │  CRM Core   │ │  AI Agents   │ │ Integration  │ │ Mobile Sync  │
 │  (modules)  │ │  (GPT-5.2)   │ │ Hub (ERP)    │ │ offline-first│
 └──────┬──────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
        └────────┬──────┴────────────────┴────────────────┘
                 ▼
          ┌──────────────┐
          │  EVENT BUS   │   (in-memory dev · RabbitMQ/Kafka prod)
          └──────┬───────┘
                 ▼
          ┌──────────────┐
          │   MongoDB    │  ← UUID + SEQ_ID + soft delete + audit
          └──────────────┘
```

## 2. Estrutura de Pastas

```
/app/backend
├─ server.py                  # FastAPI app (lifespan, routers, CORS)
├─ requirements.txt
├─ .env                       # MONGO_URL, JWT_SECRET, EMERGENT_LLM_KEY, ...
├─ core/
│  ├─ db.py                   # MongoDB client + ensure_indexes
│  ├─ seq.py                  # next_seq(name) → counter atômico
│  ├─ models.py               # BaseEntity, AuditLog
│  ├─ repo.py                 # insert_entity, update, soft_delete + auditoria
│  ├─ crud.py                 # make_crud_router (factory genérica)
│  ├─ auth.py                 # JWT, bcrypt, RBAC
│  ├─ events.py               # EventBus assíncrono in-memory
│  └─ seed.py                 # seed inicial idempotente
└─ modules/
   ├─ auth/                   # /api/auth (login, refresh, register, me)
   ├─ clients/                # /api/clients (Produtores + Empresas)
   ├─ pipeline/               # /api/pipeline (stages, opps, board, move, interactions)
   ├─ contracts/              # /api/contracts (sell|buy|barter)
   ├─ orders/                 # /api/orders (sale|purchase + logistic_status)
   ├─ products/               # /api/products (input|grain)
   ├─ logistics/              # /api/logistics (vehicles, cargas)
   ├─ support/                # /api/support (tickets + SLA)
   ├─ dashboard/              # /api/dashboard/kpis (agregações)
   ├─ ai_agents/              # /api/ai (marketing, sales, channel chat)
   ├─ sync/                   # /api/sync (pull, push, info — offline-first)
   ├─ integrations/           # /api/integrations (connectors, webhook, events)
   └─ audit/                  # /api/audit (audit_logs)
```

## 3. Modelagem (MongoDB)

Convenção comum a todas as coleções principais:

```js
{
  id: "uuid-v4",            // chave estável, pública (não-sequencial)
  seq_id: 42,               // inteiro monotônico, único por coleção (counters)
  tenant_id: "tenant-xyz",  // multi-tenant
  created_at: ISODate,
  updated_at: ISODate,
  deleted_at: null,         // soft delete
  created_by: "user-id",
  updated_by: "user-id",
  // ... campos específicos
}
```

### DDL equivalente (PostgreSQL)
Caso seja preciso espelhar em PostgreSQL no futuro:

```sql
CREATE TABLE clients (
  id UUID PRIMARY KEY,
  seq_id BIGSERIAL UNIQUE,
  tenant_id TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('producer','company')),
  name TEXT NOT NULL,
  doc TEXT,
  region TEXT,
  culture TEXT[],
  classification TEXT,
  potential TEXT,
  area_ha NUMERIC,
  contacts JSONB,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ,
  created_by UUID,
  updated_by UUID
);
CREATE INDEX idx_clients_tenant_seq ON clients (tenant_id, seq_id);
CREATE INDEX idx_clients_deleted ON clients (deleted_at);
-- (mesma convenção para contracts, orders, products, etc.)

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id UUID NOT NULL,
  action TEXT NOT NULL,
  before JSONB,
  after JSONB,
  user_id UUID,
  user_email TEXT,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_logs (entity, entity_id, timestamp DESC);
```

## 4. APIs (FastAPI)

Padrão: tudo sob `/api`, retorno Pydantic, paginação `{items, total, skip, limit}`.

| Verb | Rota | Descrição |
|---|---|---|
| POST | `/api/auth/login` | login (email + password) → access + refresh |
| POST | `/api/auth/refresh` | gera novo access a partir do refresh |
| GET  | `/api/auth/me` | usuário logado |
| GET/POST/PATCH/DELETE | `/api/clients` | CRUD clientes + busca |
| GET  | `/api/pipeline/board` | Kanban completo (stages + opps agrupadas) |
| POST | `/api/pipeline/opportunities/{id}/move` | move oportunidade entre estágios |
| POST | `/api/pipeline/opportunities/{id}/interactions` | adiciona interação |
| GET/POST/PATCH/DELETE | `/api/contracts` | CRUD contratos (sell/buy/barter) |
| GET/POST/PATCH | `/api/orders` | pedidos + status logístico |
| GET/POST | `/api/products` | insumos e grãos |
| GET/POST | `/api/logistics/vehicles` | frota |
| GET/POST | `/api/logistics/cargas` | cargas em pátio/em rota |
| GET/POST | `/api/support` | chamados + SLA |
| GET  | `/api/dashboard/kpis` | KPIs executivos (4 cards + 3 charts) |
| POST | `/api/ai/marketing/analyze-client` | Agente Marketing — análise de cliente |
| POST | `/api/ai/sales/summarize-opportunity` | Agente Vendas — resumo de negociação |
| POST | `/api/ai/channel/sessions` | Inicia sessão de chat |
| GET  | `/api/ai/channel/sessions` | Lista sessões |
| POST | `/api/ai/channel/sessions/{id}/messages` | Envia msg (multi-turn, contexto CRM) |
| POST | `/api/sync/pull` | mobile → puxa deltas desde `since` |
| POST | `/api/sync/push` | mobile → envia mudanças (LWW) |
| GET  | `/api/sync/info` | metadata da sync |
| GET  | `/api/integrations/connectors` | lista de conectores ERP |
| POST | `/api/integrations/webhook/{source}` | inbound do ERP (HMAC em prod) |
| GET  | `/api/integrations/events` | últimos eventos de domínio |
| GET  | `/api/audit` | trilha de auditoria |

Exemplo (criar cliente):

```bash
curl -X POST $API/clients \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"type":"producer","name":"Fazenda X","region":"MT - Sorriso",
       "culture":["soja"],"classification":"A","potential":"alto","area_ha":3200}'
```

## 5. Sincronização Offline-first (Mobile)

Mobile (Flutter ou React Native) com **SQLite** local espelhando as colunas dos documentos. Estratégia:

- **PULL**: `POST /api/sync/pull { since: ISO8601, entities: [...] }` retorna registros com `updated_at > since`. Cliente persiste localmente.
- **PUSH**: `POST /api/sync/push { device_id, records: [{entity, op, data}] }` aplica upserts. Conflito é detectado por `updated_at`: se servidor é mais novo, retorna `{reason: "server_newer"}` e a UI do app mostra o diff para resolução manual.
- **Resolução de conflito**: last-write-wins por `updated_at`; `seq_id` é mantido pelo servidor (autoritativo).
- **Fila local**: cada ação offline (criar, editar, deletar) entra numa `event_queue` local. Quando online, drainagem com retry exponencial (2^n s, jitter, máx 6).
- **Versionamento**: `updated_at` + `seq_id` formam o relógio lógico. Para histórico fino, `audit_logs` no servidor.
- **Entidades sincronizáveis**: `clients, products, contracts, orders, opportunities, pipeline_stages, interactions, tickets`.

## 6. Agentes de IA (GPT-5.2 via emergentintegrations)

### 6.1 Agente de Marketing/Prospecção
- **Endpoint**: `POST /api/ai/marketing/analyze-client { client_id }`
- **Entrada**: perfil completo do cliente (cultura, área, região, tier).
- **Saída**: score de potencial 0-100, fit cultura/insumo, sugestão de canal/abordagem, riscos.
- **System Prompt** (resumo): "agente especialista em agro brasileiro, considere ciclo agrícola, barter, área plantada".

### 6.2 Agente de Vendas/Pós-venda
- **Endpoint**: `POST /api/ai/sales/summarize-opportunity { opportunity_id }`
- **Entrada**: oportunidade + interações + dados do cliente.
- **Saída**: 5 bullets de resumo, 3 próximas ações ordenadas por impacto, alerta de risco.
- **Uso**: botão "Resumo IA" em cada card do Kanban.

### 6.3 Agente de Canal do Cliente (chat)
- **Endpoint**: `POST /api/ai/channel/sessions/{id}/messages { text }` (multi-turn)
- **Contexto injetado**: pedidos, contratos, tickets do cliente vinculado.
- **Persistência**: cada sessão guarda histórico em `ai_sessions.messages[]` no MongoDB.
- **Uso**: aba "Agentes IA" do backoffice.

Implementação usa `emergentintegrations.llm.chat.LlmChat` com `("openai","gpt-5.2")` e `EMERGENT_LLM_KEY` no `.env`.

## 7. Integração com ERP

Hub desacoplado em `/api/integrations`:

- **Connector Registry** com SAP S/4HANA (REST/BAPI/IDoc), Oracle EBS (REST/DB Link), TOTVS Protheus (REST/SOAP).
- **Outbox pattern**: cada CRUD publica evento (`clients.create`, `contracts.update`, ...) no Event Bus. Workers conectores consomem e entregam ao ERP correspondente.
- **Inbound**: `POST /api/integrations/webhook/{source}` recebe respostas/atualizações do ERP. Em prod, exigir HMAC-SHA256 no header `X-Signature`.
- **Idempotência**: chave (source, external_id) registrada em `integration_events` para deduplicar.
- **Padrões aceitos**: REST, Webhooks, mensageria event-driven (RabbitMQ/Kafka).

Fluxo "venda fechada → SAP":

```
POST /api/orders  (status=confirmed)
       │
       └─→ event_bus.publish("orders.create", {after})
                                 │
              ┌──────────────────┴──────────────────┐
              ▼                                     ▼
    Worker SAP (BAPI BAPI_SALESORDER_CREATEFROMDAT2)   audit_logs
              │
              ▼
   integration_events (correlation_id = external SAP id)
              │
              ▼  (callback assíncrono)
   POST /api/integrations/webhook/sap  → atualiza orders.status
```

## 8. Segurança

- **Autenticação**: JWT (HS256), access 60min, refresh 14 dias.
- **Senhas**: bcrypt (passlib).
- **RBAC**: roles `admin`, `trader`, `sales`, `support`.
- **Multi-tenant**: `tenant_id` em todo documento + filtro obrigatório nas queries.
- **Soft delete**: `deleted_at` + filtro padrão.
- **Audit**: `audit_logs` registra cada mutação (before/after).
- **CORS**: configurável via `.env`.
- **Webhooks externos**: HMAC-SHA256 (em prod).

## 9. Observabilidade

- Logs estruturados via uvicorn + handlers.
- Health: `GET /api/health` (DB ping + version).
- Activity feed: dashboard consome `audit_logs`.
- Eventos de domínio: buffer in-memory acessível em `GET /api/integrations/events`.

## 10. Escalabilidade — caminho de evolução

| Etapa | Mudança | Sem breaking? |
|---|---|---|
| 1 | EventBus → RabbitMQ/Kafka | ✅ mesma interface publish/subscribe |
| 2 | Extrair AI Service (FastAPI separado) | ✅ mesmo schema |
| 3 | Extrair Integration Hub (worker pool) | ✅ baseado em fila |
| 4 | MongoDB sharding por `tenant_id` | ✅ |
| 5 | API Gateway com cache (read-heavy) | ✅ |
| 6 | Sync via Change Streams MongoDB | ✅ delta nativo |

## 11. Boas práticas

- **DDD**: cada módulo é independente, com sua entidade, schema Pydantic e router.
- **CRUD genérico** (`core/crud.py`): factory `make_crud_router` evita duplicação.
- **Auditoria automática** em todo `insert/update/delete` via `core/repo.py`.
- **Sequencial imutável** (`seq_id`) para rastreabilidade humana, sem perder UUID público.
- **Event-driven** desde o MVP — adoção futura de microsserviços é cosmética.
