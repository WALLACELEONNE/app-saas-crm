# Agro CRM

CRM para o **agronegócio**, com foco em trading de grãos, revendas, barter e relacionamento com produtores. Backend modular em FastAPI e MongoDB, back-office em React, agentes de IA e uma API de sincronização **offline-first** para o aplicativo mobile.

## Módulos

- **Clientes:** produtores e empresas
- **Pipeline:** funil em Kanban, oportunidades e interações
- **Contratos:** venda, compra e barter
- **Pedidos e produtos:** insumos e grãos, com status logístico
- **Logística:** veículos e cargas
- **Suporte:** chamados com SLA
- **Dashboard:** KPIs por agregação
- **Agentes de IA:** marketing, vendas e chat de canal
- **Sync mobile:** pull e push offline-first (`/api/sync`)
- **Hub de integração com ERP:** conectores, webhooks e eventos
- **Auditoria:** trilha de auditoria de todas as entidades

## Arquitetura

```
Web back-office (React)
        │ HTTPS /api/*
        ▼
API Gateway (FastAPI): JWT · CORS · escopo por tenant · RBAC · CRUD genérico
   │            │               │              │
 CRM Core   AI Agents    Integration Hub   Mobile Sync
   └────────────┴───────┬───────┴──────────────┘
                   Event bus
                        │
                     MongoDB
```

- **Modelagem comum:** UUID público, sequência atômica, exclusão lógica e auditoria em todas as coleções principais.
- **Autenticação:** JWT, bcrypt e controle de acesso por perfil (RBAC), com isolamento por tenant.
- **Eventos:** barramento assíncrono em memória no desenvolvimento, com RabbitMQ ou Kafka previstos para produção.

Detalhes em [`ARCHITECTURE.md`](ARCHITECTURE.md) e em [`docs/`](docs/) (plano de tenants e permissões; plano do hub híbrido de ERP).

## Stack

Python · FastAPI · MongoDB · React · Tailwind CSS · Docker · Traefik · Cloudflare

## Estrutura

```
backend/    API FastAPI (core/ e modules/)
frontend/   Back-office em React
mobile/     Aplicativo mobile
docs/       Planos de implementação
```

## Segurança

Segredos (`MONGO_URL`, `JWT_SECRET`, chaves de LLM) ficam em variáveis de ambiente. Nunca versione o `.env`.

## Autor

**Wallace Leonne Cardoso de Souza** · [APOC Tecnologia](https://apoctecnologia.com.br) · [LinkedIn](https://www.linkedin.com/in/wallace-leonne-cardoso-de-souza/)
