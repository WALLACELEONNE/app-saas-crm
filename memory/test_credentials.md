# Agro CRM — Test Credentials

## Web Backoffice (login em /login)

| Role  | Email                  | Senha       |
|-------|------------------------|-------------|
| admin | admin@agrocrm.com      | Admin@123   |
| trader| trader@agrocrm.com     | Trader@123  |

Tenant default: `tenant-default` (multi-tenant ready).

## Endpoints chave

- `POST /api/auth/login` `{ email, password }`
- `GET /api/auth/me` (Bearer token)
- `GET /api/dashboard/kpis`
- `GET /api/clients` · `/api/contracts` · `/api/orders` · `/api/products`
- `GET /api/pipeline/board`
- `POST /api/ai/marketing/analyze-client` `{ client_id }`
- `POST /api/ai/sales/summarize-opportunity` `{ opportunity_id }`
- `POST /api/ai/channel/sessions` → cria sessão de chat
- `POST /api/ai/channel/sessions/{id}/messages` `{ text }`
- `POST /api/sync/pull` `{ since: ISO8601, entities: [...] }`
- `POST /api/sync/push` `{ device_id, records: [...] }`
- `GET /api/integrations/connectors`
- `GET /api/audit`

## Dados de seed (idempotente, criados no startup)
- 5 clientes (Fazenda São Benedito, Boa Vista, Coamo, Três Rios, Boa Esperança)
- 6 produtos (3 grãos + 3 insumos)
- 5 estágios de pipeline + 5 oportunidades
- 4 contratos (sell/buy/barter)
- 3 pedidos · 3 cargas · 3 veículos · 3 tickets

## LLM
- Provider: OpenAI · Modelo: `gpt-5.2`
- Lib: `emergentintegrations`
- Key: `EMERGENT_LLM_KEY` (universal, no `.env` do backend)
