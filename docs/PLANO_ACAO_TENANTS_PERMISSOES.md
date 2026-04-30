# Plano de Acao e Implementacao - Tenants, Filiais, Permissoes e Seguranca

Data: 2026-04-29
Projeto: Agro CRM SaaS
Status: planejamento executivo e tecnico, com Sprints 0 a 7 e governanca de IA implementadas em base funcional

## 1. Objetivo

Estruturar a evolucao do Agro CRM para um modelo SaaS profissional, seguro e preparado para LGPD, onde:

- Tenant representa a empresa contratante/cliente.
- Branch representa filial, unidade operacional ou matriz dentro do tenant.
- Usuario possui identidade global e vinculos com uma ou mais empresas.
- Permissoes controlam rigorosamente o que cada usuario pode visualizar e executar.
- O backend e a fonte real de autorizacao; o frontend apenas reflete a experiencia permitida.
- O modelo atual shared database continua viavel, mas fica preparado para clientes enterprise com banco dedicado.

## 2. Estado Atual Verificado

### 2.1 Infraestrutura e autenticacao

Itens ja corrigidos:

- Login funcional via `https://crm.apoctecnologia.com.br/api/auth/login`.
- Login funcional via `https://api.apoctecnologia.com.br/api/auth/login`.
- `JWT_SECRET` externalizado no `.env`.
- `JWT_SECRET` nao esta mais hardcoded no `docker-compose.yml`.
- `bcrypt` pinado em `4.0.1` com `passlib[bcrypt]==1.7.4`.
- Removido fallback inseguro que gravava senha em texto puro.
- Hashes dos usuarios atuais migrados para bcrypt real.
- Frontend nao usa mais `http://localhost` no bundle de producao.
- Frontend usa `/api` por padrao.
- Credenciais demo nao aparecem mais no bundle de producao.
- Seed demo desligado por padrao via `ENABLE_DEMO_SEED=false`.

Validacoes realizadas:

- Health publico da API: OK.
- Health via CRM: OK.
- Login: OK.
- `/auth/me`: OK.
- Containers Docker: OK.
- Bundle frontend sem credenciais demo e sem `localhost`.

### 2.2 Dados atuais

Os dados atuais nao sao mocks no frontend. Eles sao dados seed/demo persistidos no MongoDB.

Contagens verificadas:

| Colecao | Quantidade | Origem |
|---|---:|---|
| users | 2 | seed/demo |
| clients | 5 | seed/demo |
| products | 6 | seed/demo |
| pipeline_stages | 5 | seed/demo |
| opportunities | 5 | seed/demo |
| contracts | 4 | seed/demo |
| orders | 3 | seed/demo |
| vehicles | 3 | seed/demo |
| cargas | 3 | seed/demo |
| tickets | 3 | seed/demo |
| audit_logs | 39 | auditoria gerada pelo seed |

Usuarios atuais preservados:

| Usuario | Papel futuro sugerido | Tenant futuro | Escopo futuro |
|---|---|---|---|
| admin@agrocrm.com | tenant_owner | Agro CRM Demo | todas as filiais |
| trader@agrocrm.com | trader | Agro CRM Demo | filial Matriz |

## 3. Decisao Arquitetural

Adotar modelo hibrido:

1. Shared database como padrao inicial.
2. `tenant_id` obrigatorio em todas as entidades de negocio.
3. `branch_id` obrigatorio em entidades operacionais quando aplicavel.
4. Camada de acesso preparada para database dedicado por tenant enterprise.

### 3.1 Por que modelo hibrido

Vantagens:

- Baixo custo inicial.
- Menor complexidade operacional no MVP.
- Permite evoluir para banco dedicado sem reescrever o dominio.
- Boa aderencia para SaaS com diferentes perfis de cliente.

Riscos mitigados:

- Vazamento entre tenants por query sem filtro.
- Acesso indevido entre filiais.
- Exposicao indevida de modulos no frontend.
- Permissoes aplicadas apenas na UI.
- Dificuldade futura para LGPD, auditoria e clientes enterprise.

## 4. Modelo De Dominio Proposto

### 4.1 Entidades centrais

```text
Platform
  Tenant
    Branch
    TenantMembership
      Role
      Permissions
```

### 4.2 Colecao `tenants`

Representa a empresa contratante.

Campos sugeridos:

```js
{
  id,
  slug,
  name,
  legal_name,
  document,
  status, // active, suspended, inactive, deleted
  plan,
  data_isolation_mode, // shared_db, dedicated_db
  data_region,
  settings,
  security_policy,
  created_at,
  updated_at,
  deleted_at
}
```

### 4.3 Colecao `branches`

Representa matriz, filial, unidade operacional, fazenda operacional, armazem ou escritorio.

```js
{
  id,
  tenant_id,
  name,
  document,
  code,
  city,
  state,
  is_headquarters,
  status, // active, inactive, deleted
  created_at,
  updated_at,
  deleted_at
}
```

### 4.4 Colecao `users`

Identidade global do usuario.

```js
{
  id,
  email,
  name,
  password_hash,
  status, // active, invited, suspended, deleted
  last_login_at,
  mfa_enabled,
  created_at,
  updated_at,
  deleted_at
}
```

### 4.5 Colecao `tenant_memberships`

Vinculo entre usuario, empresa contratante, papel e filiais permitidas.

```js
{
  id,
  user_id,
  tenant_id,
  role,
  branch_scope, // all, selected
  branch_ids,
  extra_permissions,
  denied_permissions,
  status, // active, invited, suspended, deleted
  created_at,
  updated_at,
  deleted_at
}
```

## 5. Permissoes e Roles

### 5.1 Principio

O usuario logado deve visualizar e executar somente aquilo que esta liberado para ele.

Isso exige duas camadas:

- Backend: autorizacao obrigatoria e definitiva.
- Frontend: ocultacao de menus, paginas, botoes e acoes para melhor experiencia.

### 5.2 Padrao de permissao

Formato:

```text
modulo.acao
```

Acoes padrao:

```text
view
create
update
delete
approve
export
configure
manage
```

Permissoes iniciais:

```text
dashboard.view
clients.view
clients.create
clients.update
clients.delete
pipeline.view
pipeline.create
pipeline.update
pipeline.move
contracts.view
contracts.create
contracts.update
contracts.delete
contracts.approve
orders.view
orders.create
orders.update
orders.update_status
products.view
products.create
products.update
products.delete
logistics.view
logistics.create
logistics.update
logistics.delete
support.view
support.create
support.update
support.delete
ai.use
ai.configure
erp.view
erp.test_connector
erp.configure
erp.retry
audit.view
users.view
users.invite
users.update
users.disable
branches.view
branches.manage
settings.view
settings.manage
```

### 5.3 Roles iniciais

| Role | Descricao |
|---|---|
| platform_admin | Administrador interno da plataforma, uso restrito |
| tenant_owner | Dono da empresa contratante, acesso maximo ao tenant |
| tenant_admin | Administra usuarios, filiais e configuracoes do tenant |
| branch_manager | Gerencia uma ou mais filiais |
| commercial_manager | Gestao comercial, clientes, pipeline e contratos |
| trader | Operacao comercial, oportunidades, contratos e pedidos |
| logistics | Operacao de logistica, cargas e veiculos |
| support | Atendimento e tickets |
| finance | Leitura financeira, contratos, pedidos e aprovacoes especificas |
| auditor | Leitura e auditoria |
| read_only | Leitura limitada |

### 5.4 Matriz inicial de permissoes

| Modulo | tenant_owner | tenant_admin | branch_manager | commercial_manager | trader | logistics | support | finance | auditor | read_only |
|---|---|---|---|---|---|---|---|---|---|---|
| Dashboard | total | total | filial | comercial | basico | operacional | suporte | financeiro | leitura | leitura |
| Clientes | CRUD | CRUD | filial CRUD | CRUD | ver/criar/editar | ver | ver | ver | ver | ver |
| Pipeline | CRUD | CRUD | filial CRUD | CRUD | ver/mover/editar | nao | nao | ver | ver | ver |
| Contratos | CRUD/aprovar | CRUD | filial ver/editar | CRUD | criar/editar | ver | nao | ver/aprovar | ver | ver |
| Pedidos | CRUD | CRUD | filial CRUD | ver/criar | criar/ver | status/logistica | nao | ver | ver | ver |
| Produtos | CRUD | CRUD | ver | ver | ver | ver | nao | ver | ver | ver |
| Logistica | CRUD | CRUD | filial CRUD | ver | ver | CRUD | nao | ver | ver | ver |
| Suporte | CRUD | CRUD | filial ver | ver | ver | ver | CRUD | nao | ver | ver |
| IA | usar/configurar | usar/configurar | usar | usar | usar | limitado | limitado | nao | nao | nao |
| ERP Hub | total | configurar | ver | ver | nao | nao | nao | ver | ver | nao |
| Auditoria | total | total | filial | nao | nao | nao | nao | nao | ver | nao |
| Usuarios | total | gerenciar | limitado | nao | nao | nao | nao | nao | nao | nao |
| Filiais | total | gerenciar | ver | nao | nao | nao | nao | nao | nao | nao |

## 6. Regras De Autorizacao

Toda requisicao protegida deve validar:

1. Usuario autenticado.
2. Tenant ativo.
3. Membership ativa.
4. Role ou permissao efetiva permite a acao.
5. Escopo de filial permite acesso ao registro.
6. Registro pertence ao mesmo tenant do token.

Regra obrigatoria:

```text
tenant_id nunca deve ser confiado do payload do frontend.
tenant_id deve vir do token/session context.
branch_id pode vir do payload, mas deve ser validado contra o escopo do usuario.
```

### 6.1 JWT futuro

```json
{
  "sub": "user-id",
  "tenant_id": "tenant-id",
  "membership_id": "membership-id",
  "role": "trader",
  "permissions": ["clients.view", "pipeline.view"],
  "branch_scope": "selected",
  "branch_ids": ["branch-matriz"],
  "kind": "access"
}
```

### 6.2 Filtro automatico por tenant e filial

Listagem:

```text
query.tenant_id = current_tenant.id
if branch_scope == selected:
  query.branch_id in membership.branch_ids
```

Criacao:

```text
data.tenant_id = current_tenant.id
validar data.branch_id contra membership
```

Leitura por ID:

```text
buscar por id + tenant_id
validar branch_id se existir
```

Atualizacao/delecao:

```text
buscar por id + tenant_id
validar permissao
validar filial
aplicar mutacao
auditar
```

## 7. LGPD e Seguranca

### 7.1 Medidas tecnicas

- Controle de acesso por menor privilegio.
- Segregacao logica por tenant.
- Segregacao operacional por filial.
- Auditoria por tenant, filial, usuario, acao e entidade.
- Logs sem senhas, tokens, secrets ou payloads sensiveis desnecessarios.
- Backups criptografados.
- Segredos fora do codigo.
- Testes automatizados contra vazamento cross-tenant e cross-branch.
- Respostas `404` ou `403` para acesso indevido sem revelar existencia de dados.

### 7.2 Medidas administrativas

- Politica de retencao.
- Processo de atendimento a titulares.
- Processo de exportacao de dados.
- Processo de anonimizacao/exclusao.
- Procedimento de incidente.
- Registro de acesso administrativo interno.

### 7.3 Pontos de atencao

- Dados de produtores/clientes podem conter dados pessoais e empresariais.
- Contatos, documentos, telefone e email exigem controle de acesso.
- Auditoria deve evitar duplicar dados pessoais em excesso.
- Suporte interno da plataforma deve ter acesso temporario, justificado e auditado.

### 7.4 Governanca de IA e custos

Controles implementados para agentes e pontos com consumo de IA:

- Gateway unico de LLM em `core/ai_gateway.py`.
- Provider configuravel por variavel de ambiente.
- Integracao preparada para OpenAI Responses API quando `OPENAI_API_KEY` estiver configurada.
- Modo seguro `stub` quando nao existe chave de provider, evitando custo externo acidental.
- Limites configuraveis por tenant:
  - chamadas por usuario/minuto;
  - chamadas por usuario/dia;
  - chamadas por tenant/dia;
  - orcamento mensal estimado em tokens;
  - limite maximo de caracteres de entrada;
  - limite maximo de tokens de saida;
  - TTL de cache.
- Cache para analises deterministicas de marketing e vendas.
- Chat de canal sem cache para preservar contexto conversacional.
- Medicao em `ai_usage` com provider, modelo, agente, usuario, tenant, tokens, status e erros.
- Tentativas bloqueadas por politica sao registradas como `blocked`, mas nao contam como consumo efetivo.
- Painel Admin com configuracao de limites e orcamento.
- Tela Agentes IA com visao compacta de uso e bloqueios.

Pontos de consumo cobertos nesta sprint:

| Ponto | Agente | Cache | Controle |
|---|---|---:|---|
| Analise de cliente | Marketing | sim | `ai.use`, tenant/branch, rate limit |
| Resumo de oportunidade | Vendas | sim | `ai.use`, tenant/branch, rate limit |
| Chat CRM | Canal | nao | `ai.use`, tenant/branch, rate limit |
| Configuracao de IA | Admin | n/a | `ai.configure` |

## 8. Roadmap Em Sprints

### Sprint 0 - Estabilizacao ja executada

Status: concluida.

Entregas:

- Login corrigido.
- Hash bcrypt corrigido.
- Tokens funcionando.
- `JWT_SECRET` externalizado.
- Frontend sem `localhost`.
- Demo credentials removidas do build padrao.
- Seed demo desligado por padrao.
- Validacao dos dados atuais como seed/demo persistido.

Prioridade: P0.

### Sprint 1 - Base multi-tenant e bootstrap seguro

Objetivo:

Criar a base estrutural sem quebrar os usuarios atuais.

Entregas:

- Criar modelos/colecoes `tenants`, `branches`, `tenant_memberships`.
- Criar tenant inicial `Agro CRM Demo`.
- Criar branch inicial `Matriz`.
- Migrar usuarios atuais:
  - `admin@agrocrm.com` como `tenant_owner`, branch_scope `all`.
  - `trader@agrocrm.com` como `trader`, branch_scope `selected`, branch `Matriz`.
- Adicionar `branch_id` aos registros operacionais atuais quando aplicavel.
- Atualizar seed para criar tenant, branch e memberships somente quando demo seed estiver ativo.
- Criar indices:
  - `tenants.slug` unico.
  - `branches.tenant_id + branches.code`.
  - `tenant_memberships.tenant_id + user_id`.
  - entidades: `tenant_id + branch_id + seq_id`.

Prioridade: P0.

Criterios de aceite:

- Usuarios atuais continuam logando.
- Token contem tenant ativo.
- Entidades existentes continuam visiveis para admin.
- Trader ve apenas filial Matriz.
- Seed nao roda em producao sem `ENABLE_DEMO_SEED=true`.

### Sprint 2 - Auth multi-tenant e selecao de empresa

Objetivo:

Separar identidade global de acesso por tenant.

Entregas:

- Ajustar login para retornar memberships disponiveis.
- Se usuario tiver uma membership ativa, entrar direto.
- Se usuario tiver multiplas memberships, retornar estado `tenant_selection_required`.
- Criar endpoint `POST /api/auth/select-tenant`.
- Criar endpoint `POST /api/auth/switch-tenant`.
- Atualizar JWT com:
  - `tenant_id`
  - `membership_id`
  - `role`
  - `branch_scope`
  - `branch_ids`
- Atualizar `current_user` para validar membership ativa e tenant ativo.
- Criar `current_context` ou equivalente:
  - user
  - tenant
  - membership
  - permissions

Prioridade: P0.

Criterios de aceite:

- Usuario sem membership ativa nao acessa o sistema.
- Tenant suspenso bloqueia login/uso.
- Token antigo sem membership deixa de ser aceito apos migracao controlada.
- `/auth/me` retorna user, tenant, membership e permissions efetivas.

### Sprint 3 - Catalogo de roles e enforcement backend

Objetivo:

Garantir seguranca real no backend.

Entregas:

- Criar catalogo central de permissoes.
- Criar matriz de roles no backend.
- Implementar helper `require_permission(permission)`.
- Implementar helper `require_any_permission([...])`.
- Implementar validacao de filial `require_branch_access`.
- Aplicar permissoes em rotas:
  - Auth/admin users.
  - Clients.
  - Pipeline.
  - Contracts.
  - Orders.
  - Products.
  - Logistics.
  - Support.
  - AI.
  - ERP.
  - Audit.
- Bloquear payload com `tenant_id` divergente.
- Remover confianca em `tenant_id` informado pelo cliente.

Prioridade: P0.

Criterios de aceite:

- Usuario sem permissao recebe `403`.
- Usuario de filial A nao ve filial B.
- Tenant A nao acessa tenant B.
- Rotas sensiveis como ERP configure e audit exigem permissao propria.

### Sprint 4 - Repository com tenant/branch enforcement

Objetivo:

Reduzir risco de query incorreta e vazamento acidental.

Entregas:

- Refatorar `core/repo.py` para receber contexto completo.
- Aplicar filtro automatico por tenant.
- Aplicar filtro automatico por branch quando a entidade for operacional.
- Criar mapa de entidades com escopo:
  - tenant_only
  - tenant_branch
  - global
- Impedir uso de CRUD generico sem contexto.
- Adicionar testes de repository.

Prioridade: P0.

Criterios de aceite:

- Nenhuma listagem retorna registros fora do tenant.
- Nenhuma listagem operacional retorna filial nao permitida.
- Testes cobrem tentativa de acesso cross-tenant/cross-branch.

### Sprint 5 - Frontend permission-aware

Objetivo:

Fazer a UI refletir permissoes reais.

Entregas:

- Atualizar AuthContext com user, tenant, membership e permissions.
- Criar helpers:
  - `can(permission)`
  - `canAny(permissions)`
  - `canAccessBranch(branchId)`
- Esconder menus sem permissao.
- Proteger rotas no frontend.
- Esconder botoes de acao sem permissao.
- Adicionar seletor de tenant quando necessario.
- Adicionar filtro de filial baseado em branches permitidas.

Prioridade: P1.

Criterios de aceite:

- Usuario ve apenas menus permitidos.
- Usuario nao ve botoes de acoes bloqueadas.
- Tentativa manual pela URL mostra pagina sem acesso.
- Backend continua bloqueando mesmo se usuario manipular frontend.

### Sprint 6 - Administracao de tenants, filiais e usuarios

Objetivo:

Permitir gestao operacional segura.

Entregas:

- Tela de filiais.
- Tela de usuarios.
- Convite de usuarios.
- Ativacao/suspensao de usuarios.
- Atribuicao de role.
- Atribuicao de filiais.
- Visualizacao de permissoes efetivas.
- Auditoria de alteracoes administrativas.

Prioridade: P1.

Criterios de aceite:

- Tenant admin gerencia usuarios do proprio tenant.
- Branch manager nao consegue elevar privilegio.
- Alteracao de role/filial gera audit log.
- Usuario suspenso perde acesso.

### Sprint 7 - LGPD, auditoria e governanca

Objetivo:

Consolidar operacao segura e auditavel.

Entregas:

- Audit log enriquecido com tenant_id, branch_id, actor_id, role e IP quando disponivel.
- Mascaramento/minimizacao de campos sensiveis no audit.
- Endpoint de exportacao de dados por tenant.
- Processo tecnico para exclusao/anonimizacao.
- Politica de retencao configuravel.
- Registro de acesso administrativo interno.
- Guia operacional de resposta a incidente.

Prioridade: P1.

Criterios de aceite:

- Acoes sensiveis ficam auditadas.
- Exportacao por tenant funciona sem dados de outro tenant.
- Exclusao/anonimizacao e tecnicamente possivel e registrada.

### Sprint 7A - IA, LLM e governanca de custos

Objetivo:

Permitir uso profissional de agentes de IA sem risco de custo descontrolado, vazamento de contexto entre tenants ou dependencia invisivel de mocks.

Entregas:

- Centralizar chamadas de LLM em gateway unico.
- Remover acoplamento direto das rotas a SDK/provider legado.
- Implementar provider OpenAI configuravel por ambiente.
- Manter fallback seguro sem consumo quando chave nao estiver configurada.
- Aplicar `ai.use` em todos os agentes.
- Aplicar `ai.configure` na configuracao de politicas.
- Aplicar tenant/branch scope antes de montar contexto para o LLM.
- Implementar rate limit por usuario/minuto, usuario/dia e tenant/dia.
- Implementar orcamento mensal estimado por tokens.
- Implementar cache com TTL para analises deterministicas.
- Registrar uso, tokens, erros e bloqueios em `ai_usage`.
- Expor resumo de uso em `/api/ai/usage`.
- Expor configuracao em `/api/ai/settings`.
- Atualizar telas Admin e Agentes IA com uso, politica e bloqueios.

Prioridade: P1.

Criterios de aceite:

- Sem `OPENAI_API_KEY`, nenhuma chamada externa e feita.
- Com `OPENAI_API_KEY`, chamadas passam pelo gateway unico.
- Usuario sem `ai.use` nao usa agentes.
- Usuario sem `ai.configure` nao altera limites.
- Chamada repetida cacheavel reaproveita resposta e evita novo consumo.
- Rate limit retorna `429`.
- Bloqueios ficam registrados sem consumir orcamento.

### Sprint 8 - Preparacao enterprise e banco dedicado

Objetivo:

Preparar clientes com requisitos superiores de isolamento.

Entregas:

- Abstracao de resolucao de banco por tenant.
- Flag `data_isolation_mode`.
- Suporte inicial a `dedicated_db`.
- Scripts de provisionamento de tenant dedicado.
- Backup/restore por tenant.
- Estrategia de migracao shared -> dedicated.

Prioridade: P2.

Criterios de aceite:

- Um tenant pode operar em banco dedicado sem alterar API.
- Migrações rodam por tenant.
- Backup/restore isolado por cliente enterprise.

## 9. Priorizacao Executiva

### P0 - Obrigatorio antes de expansao SaaS

- Tenants.
- Branches.
- Memberships.
- JWT com tenant/membership.
- Permissoes no backend.
- Filtro automatico por tenant/branch.
- Testes contra vazamento.

### P1 - Necessario para operacao profissional

- UI permission-aware.
- Gestao de usuarios.
- Gestao de filiais.
- Auditoria enriquecida.
- Fluxos LGPD.

### P2 - Enterprise e escala

- Banco dedicado por tenant.
- Provisionamento automatizado.
- Backups por tenant.
- Chaves/segredos por tenant.
- Politicas customizadas por contrato.

## 10. Riscos e Mitigacoes

| Risco | Impacto | Mitigacao |
|---|---|---|
| Query sem tenant_id | Vazamento entre clientes | Repository obrigatorio + testes + code review |
| Frontend escondendo, backend liberando | Acesso indevido via API | `require_permission` em toda rota |
| Usuario acessando filial indevida | Vazamento operacional | `branch_scope` + filtro automatico |
| Token com tenant inativo | Acesso indevido | Validar tenant/membership em cada request |
| Seed demo em producao | Dados falsos/exposicao | `ENABLE_DEMO_SEED=false` por padrao |
| Role com permissoes amplas demais | Privilegio excessivo | Matriz revisada + menor privilegio |
| Auditoria gravando dados demais | Risco LGPD | Minimizar/mascarar campos sensiveis |

## 11. Testes Obrigatorios

### 11.1 Seguranca backend

- Tenant A nao lista clientes do tenant B.
- Tenant A nao acessa por ID registro do tenant B.
- Usuario com branch selected nao lista filial fora do escopo.
- Usuario sem `contracts.create` nao cria contrato.
- Usuario sem `erp.configure` nao configura conector.
- Auditor ve audit e nao altera dados.
- Trader nao gerencia usuarios.
- Tenant suspenso bloqueia acesso.

### 11.2 Frontend

- Menu ERP nao aparece sem `erp.view`.
- Botao configurar ERP nao aparece sem `erp.configure`.
- Botao criar cliente nao aparece sem `clients.create`.
- Rota digitada manualmente sem permissao mostra acesso negado.
- Seletor de filial mostra apenas filiais permitidas.

### 11.3 Regressao login

- `admin@agrocrm.com` loga.
- `trader@agrocrm.com` loga.
- `/auth/me` retorna contexto.
- Token expirado retorna 401.
- Refresh token gera novo access token.

## 12. Ordem Recomendada De Execucao

1. Implementar Sprint 1.
2. Implementar Sprint 2.
3. Implementar Sprint 3.
4. Implementar testes P0 antes de evoluir UI.
5. Implementar Sprint 4.
6. Implementar Sprint 5.
7. Implementar Sprint 6.
8. Implementar Sprint 7.
9. Planejar Sprint 8 conforme demanda comercial.

## 13. Decisao Final Recomendada

Adotar:

```text
Tenant = empresa contratante/cliente
Branch = filial/unidade operacional
User = identidade global
TenantMembership = vinculo usuario-empresa-role-filiais
Role = conjunto padrao de permissoes
Permission = acao granular
```

Com isso, o Agro CRM passa a ter uma base segura para SaaS multiempresa, filiais, LGPD, governanca de acesso e evolucao enterprise.

## 14. Status De Implementacao Atualizado

Atualizacao: 2026-04-29.

| Sprint | Status | Observacao |
|---|---|---|
| Sprint 0 | concluida | Login, Docker/Cloudflare, secrets, bcrypt e seed demo estabilizados. |
| Sprint 1 | concluida | Tenant, branch, memberships, indices e bootstrap seguro implementados. |
| Sprint 2 | implementada | Login multi-membership, selecao/troca de tenant e `/auth/memberships` adicionados. |
| Sprint 3 | implementada | Catalogo de roles/permissoes e enforcement backend aplicados. |
| Sprint 4 | implementada parcialmente | CRUD generico e repositorio aplicam tenant/branch; faltam testes automatizados dedicados. |
| Sprint 5 | implementada | UI filtra menu, rotas e acoes por permissao; listas paginadas e compactas. |
| Sprint 6 | implementada base | Tela Admin para usuarios, filiais e roles; falta fluxo real de convite por email. |
| Sprint 7 | implementada base | Auditoria enriquecida, exportacao tenant-scoped e anonimizacao sob demanda adicionadas; faltam politicas de retencao e incidente. |
| Sprint 7A | implementada | Gateway LLM, modo seguro, rate limit, cache, medicao de uso, bloqueios e painel Admin de IA. |
| Sprint 8 | pendente | Preparacao enterprise e banco dedicado. |

## 15. Validacoes Da Sprint De IA

Atualizacao: 2026-04-29.

| Validacao | Resultado |
|---|---|
| `python -m compileall backend` | OK |
| `npm --prefix frontend run build` | OK |
| `docker compose build backend frontend` | OK |
| `docker compose up -d backend frontend` | OK |
| Login admin | OK |
| `/api/ai/usage` | OK |
| Admin altera `/api/ai/settings` | OK |
| Trader altera `/api/ai/settings` | Bloqueado com `403` |
| Analise IA repetida | Segunda chamada veio de cache |
| Rate limit temporario | Segunda chamada bloqueada com `429` |
| Politica restaurada apos teste | OK |
| Provider atual | `stub`, pois `OPENAI_API_KEY` nao esta configurada |
| Screenshot desktop Admin/IA | OK |
| Screenshot mobile Admin | OK |
