# AgroCRM Mobile (React Native + Expo · Offline-first)

App mobile real consumindo a API `/api/sync` do backend Agro CRM. **Funcional offline**: SQLite local + fila de eventos + retry exponencial; sincroniza quando online.

## Stack
- **Expo SDK 51** (React Native 0.74)
- **expo-sqlite** — banco local com mesmo schema do servidor
- **@react-navigation/native** — stack
- **@react-native-community/netinfo** — detecção on/offline
- **axios** — cliente HTTP
- **AsyncStorage** — persistência de auth token

## Arquitetura local

```
┌──────────────────────────────────────────┐
│            UI (React Native)              │
│  Login · Home · Clients · Opps · etc      │
└─────────────┬────────────────────────────┘
              │  read/write
              ▼
┌──────────────────────────────────────────┐
│    SQLite (expo-sqlite) — agrocrm.db      │
│  clients, products, contracts, orders,    │
│  opportunities, pipeline_stages, tickets, │
│  event_queue, sync_state                  │
└─────────────┬────────────────────────────┘
              │  drain  ▲ pull
              ▼         │
┌──────────────────────────────────────────┐
│  syncEngine.js (pull + push, LWW)         │
│  + useAutoSync hook (NetInfo + timer)     │
└─────────────┬────────────────────────────┘
              │
              ▼
   POST /api/sync/pull · /api/sync/push
```

## Estrutura

```
mobile/
├── App.js                       # AuthProvider + NavigationContainer
├── app.json                     # Expo config (BACKEND_URL injetada)
├── package.json
└── src/
    ├── api/client.js            # axios + login/logout/currentUser
    ├── context/AuthContext.js
    ├── db/
    │   ├── sqlite.js            # schema + upsert/list helpers
    │   └── eventQueue.js        # local queue com backoff exponencial
    ├── sync/
    │   ├── syncEngine.js        # pull/push (LWW)
    │   └── useAutoSync.js       # hook (timer + NetInfo)
    ├── lib/theme.js
    └── screens/
        ├── LoginScreen.js
        ├── HomeScreen.js        # Sync status + tiles + pull-to-sync
        ├── ClientsScreen.js     # CRUD offline com badge SYNC
        └── ListScreens.js       # Opps/Contracts/Orders
```

## Estratégia de Sync

- **Pull**: `POST /api/sync/pull { since, entities: [...] }` — desde `last_sync_at`. Aplica upsert em SQLite. **Não** sobrescreve linhas locais com `_dirty=1` mais novas.
- **Push**: drena `event_queue` em lotes de 50, envia `{device_id, records:[{entity, op, data}]}`. Sucesso → remove da queue e zera `_dirty`. Falha → marca tentativa, agenda próximo (backoff 5s · 15s · 45s · 2min · 6min).
- **Conflito**: server LWW por `updated_at`; conflitos chegam em `data.conflicts` e podem ser exibidos ao usuário (TODO: tela de resolução).
- **Auto-sync**: a cada 60s e em toda mudança de conectividade (NetInfo).

## Como executar

```bash
cd /app/mobile
yarn install
yarn start
```

Abrir Expo Go (Android/iOS) e escanear o QR code, ou rodar em emulador (`yarn android` / `yarn ios`).

A `BACKEND_URL` está em `app.json → expo.extra.BACKEND_URL` (já apontando para o ambiente Emergent). Para rodar local com backend em `localhost:8001`, ajuste para o IP da rede da máquina (ex.: `http://192.168.1.10:8001`).

## Credenciais demo
- `admin@agrocrm.com` / `Admin@123`
- `trader@agrocrm.com` / `Trader@123`

## Roadmap mobile (próximos)
- [ ] Tela de resolução de conflitos
- [ ] Detalhe da oportunidade (drill-down)
- [ ] Chat com Agente IA "Canal do Cliente" (já há endpoint)
- [ ] Push notifications via Expo
- [ ] Captura de assinatura digital para contratos no campo
- [ ] Geolocalização/foto em interações de visita
