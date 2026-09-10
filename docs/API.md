# API Reference

Base URL: `http://localhost:8000/api`

## Auth (Admin)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/login` | Admin login → JWT |
| POST | `/auth/seed-admin` | Create default admin (dev only) |

## Admin — Clients

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/clients` | List all B2B clients |
| POST | `/admin/clients` | Create new client |
| GET | `/admin/clients/{id}` | Client detail + usage |
| DELETE | `/admin/clients/{id}` | Delete client + vectors |

## Admin — Data Sources

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/clients/{id}/sources` | List sources |
| POST | `/admin/clients/{id}/sources/url` | Add website URL |
| POST | `/admin/clients/{id}/sources/upload` | Upload document |
| DELETE | `/admin/clients/{id}/sources/{source_id}` | Delete source |
| POST | `/admin/clients/{id}/sources/{source_id}/retrain` | Retrain source |

## Admin — Training Jobs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/clients/{id}/jobs` | List training jobs |
| GET | `/admin/clients/{id}/jobs/{job_id}` | Job status |

## Admin — Agent & Widget Config

| Method | Endpoint | Description |
|---|---|---|
| GET | `/admin/clients/{id}/agent-config` | Get agent config |
| PUT | `/admin/clients/{id}/agent-config` | Update agent config |
| GET | `/admin/clients/{id}/domains` | List allowed domains |
| POST | `/admin/clients/{id}/domains` | Add domain |
| DELETE | `/admin/clients/{id}/domains/{domain_id}` | Remove domain |
| PUT | `/admin/clients/{id}/widget-config` | Update widget settings |

## Public — Widget & Chat

| Method | Endpoint | Description |
|---|---|---|
| GET | `/widget/config?key=ck_...` | Public widget config |
| POST | `/chat/session?client_key=ck_...` | Create new chat session |
| POST | `/chat/message` | Send message (SSE stream) |

### Chat Message (SSE)

```json
POST /api/chat/message
{
  "client_key": "ck_abc123",
  "session_id": "sess_xyz",
  "message": "What is your refund policy?",
  "page_url": "https://client.com/pricing"
}
```

Response: `text/event-stream`

```
data: {"type": "token", "content": "Our "}
data: {"type": "token", "content": "refund policy..."}
data: {"type": "done", "sources": ["https://..."], "latency_ms": 1200}
```

## Scraper Service (internal)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/scrape` | Crawl website |
| GET | `/health` | Health check |

## Training Service (internal)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/parse` | Parse document file |
| POST | `/chunk` | Chunk text with metadata |
| GET | `/health` | Health check |
