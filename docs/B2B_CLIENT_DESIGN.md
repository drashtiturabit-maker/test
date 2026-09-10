# B2B Client Design

## Roles

| Role | Who | Access |
|---|---|---|
| **Platform Admin** | Trivighna staff | Admin dashboard — all clients |
| **End User** | Visitor on client website | Webchat widget only |

> The dashboard is **admin-managed by Trivighna**, not self-service for end clients. When Trivighna sells the chatbot to Company A, Trivighna operators configure and train Company A's bot from the admin panel.

## Tenant Lifecycle

### 1. Onboarding Company A

```
Trivighna Admin creates client:
  ├── company_name: "Acme Corp"
  ├── client_key: ck_abc123...        (public embed key)
  ├── pinecone_namespace: client_uuid  (vector isolation)
  ├── max_websites: 3
  └── max_documents: 5
```

Auto-created:
- `agent_configs` — bot personality
- `widget_configs` — colors, enable/disable

### 2. Training Company A's Data

Admin uploads from dashboard:
- Website URLs (crawler runs automatically)
- PDF/DOCX/DOC files

Each source triggers a Celery training job:
`queued → scraping → chunking → embedding → done`

Vectors stored in Pinecone namespace `client_{uuid}` only.

### 3. Widget Deployment

Admin configures:
- Allowed domains: `www.acme.com`, `app.acme.com`
- Agent config: bot name, tone, instructions

Admin gives Company A the embed script:

```html
<script src="https://cdn.trivighna.com/embed.js"
        data-client-key="ck_abc123" async></script>
```

### 4. End User Chat

1. User visits `www.acme.com`
2. Widget loads, checks domain whitelist
3. New session created (`POST /api/chat/session`)
4. User asks questions
5. Agent queries Pinecone namespace for Acme only
6. Responses streamed via SSE

## Data Isolation Guarantees

- Company A's `client_key` → resolves to namespace A
- Company B's `client_key` → resolves to namespace B
- Cross-tenant retrieval is impossible by design
- Admin panel requires JWT auth

## Session Model

| Event | Behavior |
|---|---|
| First visit | New `session_id` created |
| Page refresh | **New** `session_id` (fresh conversation) |
| Same page, continued chat | Same `session_id` |
| Messages | Stored in `chat_messages` linked to session |

## Selling Model

```
Trivighna (Platform)
    │
    ├── Sells to Company A → trains A's data → widget on A's domain
    ├── Sells to Company B → trains B's data → widget on B's domain
    └── Manages all via single admin dashboard
```

## PostgreSQL Entity Relationships

```
clients (1) ──► (1) agent_configs
clients (1) ──► (1) widget_configs
clients (1) ──► (*) allowed_domains
clients (1) ──► (*) data_sources
clients (1) ──► (*) training_jobs
clients (1) ──► (*) chat_sessions ──► (*) chat_messages
clients (1) ──► (*) leads
```
