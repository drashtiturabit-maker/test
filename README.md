# CX Chatbot Platform

Production-ready B2B SaaS CX chatbot platform by **Trivighna**. Each client company gets an isolated RAG agent trained on their website and documents, embeddable via a React webchat widget.

## Architecture

```
Trivighna Admin Dashboard (React)
        │
        ▼
   FastAPI Backend ──────► PostgreSQL (tenants, sessions, jobs)
        │                        │
        ├── CX Agent (LangGraph) │
        ├── Celery Workers       │
        ▼                        ▼
   Pinecone (namespace/client)  Redis
        ▲
        │
 Scraper Service ──► Training Service
        │
   Client Website ◄── React Webchat Widget (embed script)
```

## Services

| Folder | Port | Description |
|---|---|---|
| `backend/` | 8000 | API, CX LangGraph agent, auth, chat |
| `scraper-service/` | 8001 | Website crawling & text extraction |
| `training-service/` | 8002 | Document parsing & chunking |
| `dashboard/` | 5173 | Trivighna admin panel (React) |
| `webchat/` | 5174 | Embeddable client chat widget (React) |
| `database/` | — | PostgreSQL schema |

## Quick Start

### 1. Environment

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and PINECONE_API_KEY
```

### 2. Docker (recommended)

```bash
docker compose up -d
```

### 3. Manual Setup

```bash
# PostgreSQL
psql -U cx_user -d cx_chatbot -f database/schema.sql

# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Celery worker (separate terminal)
celery -A app.tasks.training_tasks.celery_app worker -Q training -l info

# Scraper + Training
cd scraper-service && uvicorn app.main:app --port 8001
cd training-service && uvicorn app.main:app --port 8002

# Dashboard + Webchat
cd dashboard && npm install && npm run dev
cd webchat && npm install && npm run dev
```

### 4. Create Admin

Visit http://localhost:5173 → **Seed Default Admin** → Login:
- Email: `admin@trivighna.com`
- Password: `admin123`

## B2B Flow

1. **Trivighna** creates a client company in the admin dashboard
2. Client gets unique `client_key` + Pinecone `namespace`
3. Admin uploads up to **3 websites** and **5 documents** for that client
4. Training pipeline scrapes/parses → chunks → embeds → Pinecone namespace
5. Client embeds webchat on their domain (domain whitelist enforced)
6. End users chat → CX agent retrieves from client's namespace only

## Limits Per Client

- Max **3** website URLs
- Max **5** documents (PDF, DOCX, DOC, TXT)

## Session Model

- Each widget page load creates a **new session** (including refresh)
- Sessions stored in PostgreSQL with full message history

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [B2B Client Design](docs/B2B_CLIENT_DESIGN.md)
- [API Reference](docs/API.md)
- [Backend](backend/README.md)
- [CX Agent](backend/app/agent/README.md)
- [Scraper](scraper-service/README.md)
- [Training](training-service/README.md)
- [Dashboard](dashboard/README.md)
- [Webchat](webchat/README.md)

## Blueprint Reference

See `CX_Chatbot_Blueprint_v2.md` for the original product specification. This implementation uses **Pinecone** (namespace per client) instead of Milvus, and an **admin-managed dashboard** for Trivighna operators.
