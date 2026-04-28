# PRD — Agro CRM

## Problema (original)
Sistema completo de **CRM para o agronegócio** (Agro CRM), com foco em operações de **trading de grãos, revendas, barter e relacionamento com produtores**. Independente de ERP, mas preparado para integração via hub. Suportar baixa conectividade (offline-first) e alto volume transacional.

## Personas
- **Trader de grãos** — opera contratos sell/buy/barter, acompanha pipeline.
- **Gerente comercial** — acompanha KPIs, faturamento por região, oportunidades.
- **Pós-vendas/Suporte** — gerencia chamados, SLAs, satisfação do cliente.
- **Executivo (C-level)** — Dashboard com KPIs do negócio.
- **Mobile field user** — operadores em pátio com baixa conectividade (escopo: API documentada).

## Escolhas do usuário (sessão inicial)
- Web Backoffice React + Backend FastAPI + MongoDB + 1 Agente IA (escopo MVP).
- MongoDB com SEQ_ID/UUID/soft-delete/audit (não PostgreSQL).
- LLM: **GPT-5.2** (OpenAI) via **Emergent LLM Key** universal.
- Mensageria: event bus em Python interno (in-memory, abstração para RabbitMQ/Kafka).
- Mobile: documentar arquitetura + API de sync (sem app real nesta entrega).

## Arquitetura
- **Backend**: FastAPI modular monolith — 13 módulos sob `/api`.
- **Frontend**: React + Tailwind + Recharts + lucide-react.
- **Banco**: MongoDB (UUID + SEQ_ID + soft delete + audit log + tenant_id).
- **Auth**: JWT (access 60min + refresh 14d), bcrypt, RBAC.
- **Event Bus**: in-memory async com mesma interface de RabbitMQ/Kafka.
- **AI**: 3 agentes via `emergentintegrations.LlmChat` (gpt-5.2).
- **Sync**: pull/push offline-first, last-write-wins por `updated_at`.

## Implementado nesta sessão (28/01/2026)

### Iteração 2 — ERP Workers Reais + Mobile React Native

**Backend ERP Workers (durável + retries + 3 conectores reais)**
- ✅ `/app/backend/modules/integrations/connectors.py` — Classes `SAPConnector`, `OracleConnector`, `SiagriConnector` com transforms vendor-específicos (SAP BusinessPartner/SalesContract, Oracle OM Module, **Siagri Agribusiness em pt-BR** — Produtor, ContratoGraos, PedidoVenda, Carga)
- ✅ `/app/backend/modules/integrations/worker.py` — `ErpWorker` singleton com:
  - Outbox durável em `db.outbox_events` (assina `*` no event_bus)
  - Loop de polling (2s) que dispara para conectores que matcham o tópico
  - Retry com backoff exponencial (5s · 15s · 45s · 2min · 6min, máx 5 tentativas)
  - Log de cada delivery em `db.connector_deliveries`
- ✅ Endpoints:
  - `GET /api/integrations/connectors` (lista + status)
  - `POST /api/integrations/connectors/{vendor}/configure` (admin only, atualiza endpoint/headers/enabled)
  - `POST /api/integrations/connectors/{vendor}/test` (dispatch síncrono p/ debug)
  - `GET /api/integrations/outbox` (com filtro de status + counters)
  - `POST /api/integrations/outbox/{id}/retry` (re-enfileira)
  - `GET /api/integrations/deliveries` (log por vendor)
  - `POST /api/integrations/_simulator/{vendor}` (simulador interno público — destino default dos conectores)
  - `GET /api/integrations/_simulator/{vendor}/log`

**Frontend — Página `/erp`**
- ✅ `/app/frontend/src/pages/ERP.jsx` — Hub completo com:
  - 3 cards de conectores (SAP/Oracle/Siagri) com status, tópicos, endpoint, botões de Disparar Teste e Configurar
  - Modal de configuração (endpoint custom + enable/disable, admin only)
  - Stats Outbox (delivered/pending/in_progress/failed) clicável p/ filtro
  - Lista de eventos com badges por vendor + botão Re-disparar
  - Tabela de Log de Entregas com vendor, latência, tentativa, endpoint
  - Auto-refresh 5s
- ✅ Sidebar agora tem 11 itens (adicionado **ERP Hub**)

**Mobile App (React Native + Expo · `/app/mobile`)**
- ✅ `package.json` com Expo SDK 51, expo-sqlite, NetInfo, react-navigation
- ✅ `src/db/sqlite.js` — schema espelhado (clients, products, contracts, orders, opportunities, pipeline_stages, tickets) + `event_queue` + `sync_state`
- ✅ `src/db/eventQueue.js` — fila local com backoff exponencial (5s · 15s · 45s · 2min · 6min)
- ✅ `src/sync/syncEngine.js` — pull/push bidirecional com LWW, não sobrescreve linhas `_dirty` mais novas
- ✅ `src/sync/useAutoSync.js` — hook NetInfo + timer 60s + push em mudanças de conectividade
- ✅ `src/api/client.js` — axios + AsyncStorage para token + login/logout
- ✅ Telas: `LoginScreen`, `HomeScreen` (status sync + tiles + pull-to-refresh), `ClientsScreen` (CRUD offline com badge SYNC), `OpportunitiesScreen`, `ContractsScreen`, `OrdersScreen`
- ✅ `App.js` com NavigationContainer + AuthProvider
- ✅ `/app/mobile/README.md` com diagrama, estrutura e instruções de execução

### Iteração 1 (sessão anterior — preservada)

### Backend (13 módulos)
- ✅ `/api/auth` — login, refresh, register (admin), me — JWT
- ✅ `/api/clients` — CRUD Produtores/Empresas com classificação A/B/C
- ✅ `/api/pipeline` — stages CRUD, opportunities CRUD, **/board** (Kanban), **/move**, /interactions
- ✅ `/api/contracts` — CRUD compra/venda/barter
- ✅ `/api/orders` — CRUD com logistic_status
- ✅ `/api/products` — Insumos + Grãos
- ✅ `/api/logistics` — Vehicles + Cargas
- ✅ `/api/support` — Tickets com SLA
- ✅ `/api/dashboard/kpis` — agregação completa
- ✅ `/api/ai/marketing/analyze-client` — Agente Marketing (GPT-5.2)
- ✅ `/api/ai/sales/summarize-opportunity` — Agente Vendas (GPT-5.2)
- ✅ `/api/ai/channel/sessions` + messages — Chat multi-turn com contexto CRM
- ✅ `/api/sync/pull` + `/push` + `/info` — Offline-first
- ✅ `/api/integrations/connectors` + `/webhook/{source}` + `/events` — ERP Hub
- ✅ `/api/audit` — trilha de auditoria

### Core
- ✅ `core/repo.py` — insert/update/soft_delete + auditoria automática
- ✅ `core/crud.py` — factory CRUD genérica
- ✅ `core/seq.py` — counters atômicos para SEQ_ID
- ✅ `core/auth.py` — JWT + bcrypt + RBAC
- ✅ `core/events.py` — EventBus async in-memory
- ✅ `core/seed.py` — dados iniciais idempotentes

### Frontend (11 páginas)
- ✅ Login (split panel, branding)
- ✅ Dashboard (4 KPIs + bar chart pipeline + donut logística + faturamento por região + audit trail)
- ✅ Clientes (tabela, busca, modal novo, **botão IA → análise GPT-5.2**)
- ✅ Pipeline (Kanban drag&drop entre estágios, **botão Resumo IA**)
- ✅ Contratos (tabela + modal com tipo sell/buy/barter)
- ✅ Pedidos (tabela + Avançar status)
- ✅ Produtos (grid de cards)
- ✅ Logística (cargas + frota)
- ✅ Suporte (tickets + SLA)
- ✅ **Agentes IA** (3 cards explicativos + chat panel funcional multi-turn)
- ✅ **Arquitetura** (telemetria viva + 7 seções + diagrama ASCII)

### Documentação
- ✅ `/app/ARCHITECTURE.md` — completa (modelagem, DDL Postgres equivalente, APIs, sync, ERP hub, segurança, escalabilidade)
- ✅ `/app/design_guidelines.json` — paleta dark agro-terminal, fontes Outfit/Manrope/IBM Plex Mono

### Testing
- ✅ Backend: 27/27 testes pytest (100%)
- ✅ Frontend: 100% navegação + render
- ✅ 2 issues visuais corrigidos (donut height + KPI overlay)

## Backlog / P1
- [ ] App mobile real (Flutter ou RN) consumindo `/api/sync` (apenas API documentada nesta fase)
- [ ] Endpoint dedicado `POST /api/orders/{id}/advance` com state machine
- [ ] Workers reais para conectores SAP/Oracle (hoje somente registro + outbox)
- [ ] HMAC-SHA256 nos webhooks `/api/integrations/webhook/{source}`
- [ ] WebSocket para push de eventos ao frontend (atualização live do Kanban)
- [ ] Drag&drop com biblioteca (atualmente HTML5 nativo)

## Backlog / P2
- [ ] Migrar EventBus in-memory para RabbitMQ/Kafka (interface já abstraída)
- [ ] Extrair AI Service em microsserviço separado
- [ ] MongoDB Change Streams para sync delta
- [ ] Multi-tenant UI (atualmente só seed default)
- [ ] Relatórios PDF/Excel exportáveis
- [ ] Painel de mercado (preços CME/B3 ao vivo)
- [ ] App white-label para o produtor (lite mobile com pedidos + chat IA)

## Métricas de sucesso (sugeridas)
- Tempo médio de fechamento de oportunidade no pipeline
- Volume de grãos negociado por mês (ton e BRL)
- NPS de clientes via chamados de Suporte
- % de pedidos entregues no SLA logístico

## Credenciais de teste
Veja `/app/memory/test_credentials.md`.
