# CX Chatbot — B2B SaaS Product Blueprint

> **Purpose:** End-to-end technical specification for an AI-powered Customer Experience chatbot platform that lets B2B clients train a RAG agent on their own data (website + documents) and embed it as a widget on any website.

---

## Table of Contents

1. [System Overview & Architecture](#1-system-overview--architecture)
2. [Tech Stack Decisions](#2-tech-stack-decisions)
3. [Frontend — Dashboard & Chat Widget](#3-frontend--dashboard--chat-widget)
4. [Scraping Service](#4-scraping-service)
5. [Document Processing Pipeline](#5-document-processing-pipeline)
6. [RAG Training Pipeline](#6-rag-training-pipeline)
7. [Backend APIs](#7-backend-apis)
8. [Database Design (PostgreSQL + Milvus)](#8-database-design-postgresql--milvus)
9. [Agent / RAG Query Pipeline](#9-agent--rag-query-pipeline)
10. [Client Identity & Multi-Tenancy](#10-client-identity--multi-tenancy)
11. [Async Job Queue Architecture](#11-async-job-queue-architecture)
12. [Security & Auth](#12-security--auth)
13. [Deployment Architecture](#13-deployment-architecture)
14. [Implementation Phases & Task Breakdown](#14-implementation-phases--task-breakdown)

---

## 1. System Overview & Architecture

### What the Product Does

A multi-tenant B2B SaaS platform where each client (company) can:
- Scrape their own website URLs OR upload PDF/DOCX documents
- Train a private RAG (Retrieval-Augmented Generation) agent on that data
- Get an embeddable chat widget (`<script>` tag) to drop on any website
- Manage everything from a central dashboard

### High-Level Data Flow

```
CLIENT DASHBOARD
      │
      ├─► [URL Input]  ──► Scraper Service ──► Text Extractor
      │                                                │
      └─► [File Upload] ──► Doc Parser ───────────────┘
                                                       │
                                              Chunking Engine
                                                       │
                                             Embedding Generator
                                                       │
                                           Milvus VectorDB (per client namespace)
                                                       │
                                    ┌──────────────────┘
                                    │
                         USER SENDS CHAT MESSAGE
                                    │
                               Query Embedder
                                    │
                         Vector Similarity Search (Milvus)
                                    │
                           Top-K Context Chunks Retrieved
                                    │
                        Prompt Builder (System + Context + Query)
                                    │
                                LLM API (Claude / OpenAI)
                                    │
                           Streamed Response to Chat Widget
```

### Multi-Tenancy Model

Every B2B client has:
- A unique `client_id` (UUID, internal)
- A unique `client_key` (public-facing API key used in the chat widget)
- An isolated **Milvus collection** (or partition) so no data crosses between clients
- Their own set of data sources, training jobs, chat sessions

---

## 2. Tech Stack Decisions

| Layer | Technology | Reason |
|---|---|---|
| Frontend Dashboard | **Next.js 14 (App Router)** | SSR, fast, excellent DX |
| Chat Widget | **Vanilla JS + Web Components** | Zero-dependency embed, works on any site |
| Backend API | **FastAPI (Python 3.11+)** | Async-first, fast, great for AI workloads |
| Task Queue | **Celery + Redis** | Async scraping & training jobs |
| Relational DB | **PostgreSQL 15** | Client data, jobs, sessions, metadata |
| Vector DB | **Milvus (self-hosted) or Qdrant (cloud-friendly)** | Dense vector storage + ANN search |
| Object Storage | **MinIO (self-hosted) / AWS S3** | Uploaded PDFs, DOCXs |
| Embeddings | **OpenAI `text-embedding-3-small`** or **`sentence-transformers/all-MiniLM-L6-v2`** (local) | Semantic search |
| LLM | **Claude claude-sonnet-4-20250514 / GPT-4o** (configurable per client) | RAG answer generation |
| Scraping | **Playwright + BeautifulSoup4** | JS-rendered + static pages |
| Auth | **JWT (access + refresh tokens)** + bcrypt | Stateless, secure |
| Cache | **Redis** | Rate limiting, session cache, job status |
| Reverse Proxy | **Nginx** | Routing dashboard, API, widget CDN |

---

## 3. Frontend — Dashboard & Chat Widget

### 3.1 Dashboard (Next.js)

#### Project Structure

```
/dashboard
  /app
    /auth
      login/page.tsx
      register/page.tsx
    /dashboard
      layout.tsx               ← sidebar + topbar shell
      page.tsx                 ← overview stats
      /sources
        page.tsx               ← list all data sources
        /new
          page.tsx             ← add URL or upload file
      /training
        page.tsx               ← training job history + status
      /chat-logs
        page.tsx               ← all conversations
        /[session_id]/page.tsx ← single conversation view
      /widget
        page.tsx               ← widget customization + embed code
      /settings
        page.tsx               ← account, API keys, billing
  /components
    /ui                        ← shadcn/ui base components
    /dashboard
      Sidebar.tsx
      StatsCard.tsx
      SourceTable.tsx
      JobStatusBadge.tsx
      ChatLogViewer.tsx
      WidgetPreview.tsx
      EmbedCodeBlock.tsx
  /lib
    api.ts                     ← axios/fetch wrapper with auth headers
    auth.ts                    ← JWT helpers
    hooks/
      useJobs.ts               ← polling hook for job status
      useSources.ts
  /types
    index.ts                   ← shared TypeScript types
```

#### Key Dashboard Pages & Features

**Login / Register**
- Email + password auth
- JWT stored in httpOnly cookie
- Redirect to dashboard on success

**Overview Page (`/dashboard`)**
- Total data sources trained
- Total chat conversations
- Active widget status (on/off)
- Recent training jobs with status chips

**Data Sources Page (`/dashboard/sources`)**
- Table: Name | Type (URL/PDF/DOCX) | Status | Last Trained | Actions
- "Add Source" button opens modal:
  - Tab 1: Paste URL(s) — support comma-separated or line-by-line
  - Tab 2: Upload file — drag-and-drop PDF / DOCX (max 50MB)
- Per-row actions: Re-train, Delete, View chunks (debug)

**Training Jobs Page (`/dashboard/training`)**
- Live-updating job list (polling every 3s via `useJobs` hook)
- Job states: `queued → scraping → chunking → embedding → done | failed`
- Progress bar per job
- Error log expand for failed jobs

**Chat Logs Page (`/dashboard/chat-logs`)**
- List of all chat sessions with timestamp, user message count
- Click into session: full conversation thread view
- Filter by date range, keyword

**Widget Page (`/dashboard/widget`)**
- Live preview of the chat widget (iframe)
- Customization: primary color, chatbot name, welcome message, avatar
- Embed code block (auto-generated with `client_key`):
  ```html
  <script 
    src="https://yourplatform.com/widget.js"
    data-client-key="ck_abc123xyz"
  ></script>
  ```
- Toggle widget ON/OFF (disables responses without removing embed)

**Settings Page (`/dashboard/settings`)**
- Profile info
- Rotate `client_key`
- LLM model selection (if offering choice)
- Danger zone: delete all data, delete account

---

### 3.2 Chat Widget (Embeddable)

The widget is a single JS file served from your CDN. No React, no dependencies — must work inside any client website.

#### File: `widget.js`

**Initialization Flow:**
1. Script tag loaded → reads `data-client-key`
2. Fetches widget config from API (`GET /api/widget/config?key=ck_abc123`)
3. Injects Shadow DOM container (prevents CSS conflicts with host page)
4. Renders floating button + chat panel

**Widget Structure (Shadow DOM):**
```
#shadow-root
  ├── <style> (scoped CSS with brand colors from config)
  ├── <div id="cx-widget-btn">  ← floating button
  └── <div id="cx-chat-panel">
        ├── header (bot name + close btn)
        ├── messages area (scrollable)
        ├── typing indicator
        └── input area (text field + send btn)
```

**Chat Flow:**
1. User types message → `POST /api/chat/message` with `{ client_key, session_id, message }`
2. Response streams back via **Server-Sent Events (SSE)**
3. Widget renders streamed tokens progressively
4. `session_id` is stored in `localStorage` to preserve conversation across page refreshes

**Widget Features:**
- Streaming response (SSE)
- "Thinking..." indicator during LLM call
- Auto-scroll to latest message
- Mobile responsive
- Keyboard shortcut (Enter to send)
- "Powered by [YourBrand]" footer (removable on paid plan)

---

## 4. Scraping Service

### 4.1 Scraper Design

**File:** `services/scraper/scraper.py`

The scraper handles two challenges:
- **Static sites** (pure HTML) — use `httpx` + `BeautifulSoup4`
- **Dynamic/JS-rendered sites** — use `Playwright` (headless Chromium)

### 4.2 Scraping Logic

```python
# Pseudocode flow

async def scrape_url(url: str, client_id: str, job_id: str) -> list[str]:
    # Step 1: Detect if page is JS-rendered
    raw_html = await fetch_with_httpx(url)
    if is_js_rendered(raw_html):
        html = await fetch_with_playwright(url)
    else:
        html = raw_html

    # Step 2: Extract clean text
    text = extract_text(html)       # remove nav, footer, scripts, ads
    
    # Step 3: Crawl internal links (configurable depth, default: 2)
    links = extract_internal_links(html, base_url=url)
    for link in links[:MAX_PAGES_PER_SOURCE]:
        child_text = await scrape_url(link, client_id, job_id)
    
    return text
```

### 4.3 Text Extraction Rules

Use `BeautifulSoup4` with these extraction rules:
- **Keep:** `<p>`, `<h1>`-`<h6>`, `<li>`, `<td>`, `<th>`, `<blockquote>`, `<article>`, `<section>`
- **Remove:** `<nav>`, `<footer>`, `<header>`, `<script>`, `<style>`, `<ads>`, cookie banners
- Collapse whitespace, remove duplicate lines
- Preserve semantic structure: add `\n\n` between headings/sections

### 4.4 Scraper Config Options (per data source)

```json
{
  "max_depth": 2,
  "max_pages": 50,
  "exclude_patterns": ["/blog", "/careers"],
  "include_patterns": ["/products", "/support"],
  "respect_robots_txt": true,
  "rate_limit_ms": 500
}
```

### 4.5 Anti-Detection & Politeness

- Random user-agent rotation
- Configurable delay between requests (default 500ms)
- Respect `robots.txt`
- Retry with exponential backoff on 429/503 errors (max 3 retries)

---

## 5. Document Processing Pipeline

### 5.1 Supported Formats

| Format | Library |
|---|---|
| PDF | `pymupdf` (fitz) — handles scanned + text PDFs |
| DOCX | `python-docx` |
| TXT | native Python |
| CSV | `pandas` — each row treated as a document chunk |

### 5.2 Upload Flow

1. Client uploads file via dashboard
2. FastAPI receives multipart upload → validates type, size
3. File saved to **MinIO/S3**: `uploads/{client_id}/{source_id}/{filename}`
4. `data_sources` record created in PostgreSQL with `status = "pending"`
5. Celery task queued: `process_document.delay(source_id)`

### 5.3 Document Parser Logic

```python
# services/document_processor/parser.py

def parse_pdf(filepath: str) -> str:
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text("text") + "\n\n"
    return clean_text(text)

def parse_docx(filepath: str) -> str:
    doc = Document(filepath)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    tables = extract_docx_tables(doc)      # flatten table cells as text
    return "\n\n".join(paragraphs + tables)

def clean_text(text: str) -> str:
    # Normalize whitespace
    # Remove repeated newlines > 2
    # Strip page numbers, headers/footers
    # Return cleaned string
```

---

## 6. RAG Training Pipeline

### 6.1 Pipeline Stages

```
Raw Text (from scraper or document parser)
         │
         ▼
  [Stage 1] Text Cleaner
         │   - Unicode normalization
         │   - Remove boilerplate
         │   - Sentence boundary detection
         ▼
  [Stage 2] Chunker
         │   - Strategy: Recursive Character Text Splitter
         │   - chunk_size: 512 tokens
         │   - chunk_overlap: 64 tokens
         │   - Respect paragraph/sentence boundaries
         ▼
  [Stage 3] Metadata Tagger
         │   - source_url or filename
         │   - page_number (PDF)
         │   - client_id
         │   - chunk_index
         │   - timestamp
         ▼
  [Stage 4] Embedding Generator
         │   - Batch API calls (OpenAI or local)
         │   - 1536-dim vectors (OpenAI) or 384-dim (MiniLM)
         │   - Retry on failure
         ▼
  [Stage 5] Vector Store Upsert
             - Collection: cx_client_{client_id}
             - Upsert by chunk_id (idempotent re-training)
             - Also store chunk text in Milvus payload
```

### 6.2 Chunking Strategy

```python
# services/pipeline/chunker.py

from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_text(text: str, source_meta: dict) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_text(text)
    return [
        {
            "chunk_id": f"{source_meta['source_id']}_{i}",
            "client_id": source_meta["client_id"],
            "source_id": source_meta["source_id"],
            "source_type": source_meta["type"],    # "url" | "pdf" | "docx"
            "source_name": source_meta["name"],
            "text": chunk,
            "chunk_index": i,
        }
        for i, chunk in enumerate(chunks)
    ]
```

### 6.3 Embedding Generation

```python
# services/pipeline/embedder.py

import openai

async def embed_chunks(chunks: list[dict]) -> list[dict]:
    texts = [c["text"] for c in chunks]
    
    # Batch in groups of 100 (OpenAI limit)
    all_embeddings = []
    for batch in batched(texts, 100):
        response = await openai.AsyncOpenAI().embeddings.create(
            model="text-embedding-3-small",
            input=batch
        )
        all_embeddings.extend([e.embedding for e in response.data])
    
    for chunk, embedding in zip(chunks, all_embeddings):
        chunk["embedding"] = embedding
    
    return chunks
```

### 6.4 Milvus Collection Schema

```python
# services/pipeline/vector_store.py

from pymilvus import CollectionSchema, FieldSchema, DataType

def get_collection_schema():
    return CollectionSchema(fields=[
        FieldSchema("chunk_id",    DataType.VARCHAR, max_length=256, is_primary=True),
        FieldSchema("client_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("source_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("source_name", DataType.VARCHAR, max_length=512),
        FieldSchema("source_type", DataType.VARCHAR, max_length=32),
        FieldSchema("text",        DataType.VARCHAR, max_length=4096),
        FieldSchema("chunk_index", DataType.INT64),
        FieldSchema("embedding",   DataType.FLOAT_VECTOR, dim=1536),
    ])

# Index: HNSW for fast ANN search
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 256}
}
```

### 6.5 Re-Training / Update Strategy

- Re-training a source = delete all chunks with `source_id` from Milvus → re-run pipeline
- Deleting a source = delete all chunks from Milvus + PostgreSQL record
- This is idempotent and safe; the client's other sources are untouched

---

## 7. Backend APIs

### 7.1 API Structure

```
/api
  /auth
    POST   /register              ← new client account
    POST   /login                 ← returns access + refresh tokens
    POST   /refresh               ← rotate access token
    POST   /logout

  /sources
    GET    /                      ← list all data sources (auth)
    POST   /url                   ← submit URL(s) for scraping
    POST   /upload                ← upload PDF or DOCX
    DELETE /{source_id}           ← delete source + its vectors
    POST   /{source_id}/retrain   ← re-run pipeline on source

  /jobs
    GET    /                      ← list training jobs
    GET    /{job_id}              ← job status + progress

  /chat
    POST   /message               ← send message, stream SSE response
    GET    /sessions              ← list sessions (dashboard)
    GET    /sessions/{session_id} ← full session history
    DELETE /sessions/{session_id} ← delete session

  /widget
    GET    /config                ← public endpoint (by client_key)
    PUT    /config                ← update widget settings (auth)

  /clients
    GET    /me                    ← current client info
    PUT    /me                    ← update profile
    POST   /rotate-key            ← rotate client_key
    DELETE /me                    ← delete account + all data
```

### 7.2 Endpoint Details

#### `POST /api/sources/url`
```json
Request:
{
  "name": "Main Website",
  "urls": ["https://company.com", "https://company.com/products"],
  "scrape_config": {
    "max_depth": 2,
    "max_pages": 30,
    "exclude_patterns": ["/careers"]
  }
}

Response:
{
  "source_id": "src_abc123",
  "job_id": "job_xyz789",
  "status": "queued",
  "message": "Scraping job queued successfully"
}
```

#### `POST /api/sources/upload`
```
Content-Type: multipart/form-data
Fields:
  - file: <binary>
  - name: "Product Manual Q4 2024"

Response:
{
  "source_id": "src_def456",
  "job_id": "job_uvw321",
  "status": "queued",
  "filename": "product_manual.pdf",
  "size_bytes": 2048000
}
```

#### `POST /api/chat/message` (SSE Streaming)
```json
Request:
{
  "client_key": "ck_abc123xyz",
  "session_id": "sess_001",
  "message": "What are your return policy details?"
}

Response: text/event-stream
data: {"type": "token", "content": "Our "}
data: {"type": "token", "content": "return "}
data: {"type": "token", "content": "policy..."}
data: {"type": "done", "sources": ["https://company.com/returns"], "session_id": "sess_001"}
```

#### `GET /api/widget/config?key=ck_abc123xyz`
```json
Response (public, no auth needed):
{
  "bot_name": "Aria",
  "welcome_message": "Hi! How can I help you today?",
  "primary_color": "#4F46E5",
  "avatar_url": "https://cdn.yourplatform.com/avatars/default.png",
  "enabled": true
}
```

### 7.3 API Middleware Stack

```python
# main.py middleware order (FastAPI)

app.add_middleware(CORSMiddleware, ...)
app.add_middleware(RateLimitMiddleware, ...)   # Redis-backed rate limiter
app.add_middleware(RequestLoggerMiddleware, ...)
app.add_middleware(ClientKeyResolverMiddleware, ...)  # for /chat endpoints
```

### 7.4 Rate Limiting Rules

| Endpoint | Limit |
|---|---|
| `POST /chat/message` | 20 req/min per session_id |
| `POST /sources/upload` | 10 req/hour per client |
| `POST /sources/url` | 5 req/hour per client |
| `POST /auth/login` | 10 req/min per IP |

---

## 8. Database Design (PostgreSQL + Milvus)

### 8.1 PostgreSQL Schema

#### Table: `clients`
```sql
CREATE TABLE clients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    company_name    VARCHAR(255),
    client_key      VARCHAR(64) UNIQUE NOT NULL,  -- public key used in widget
    plan            VARCHAR(32) DEFAULT 'free',   -- free | starter | pro
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_clients_client_key ON clients(client_key);
```

#### Table: `data_sources`
```sql
CREATE TABLE data_sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    type            VARCHAR(16) NOT NULL,          -- 'url' | 'pdf' | 'docx' | 'txt'
    status          VARCHAR(32) DEFAULT 'pending', -- pending | processing | trained | failed
    
    -- For URL sources
    urls            TEXT[],                        -- array of submitted URLs
    scrape_config   JSONB DEFAULT '{}',
    pages_scraped   INT DEFAULT 0,
    
    -- For file sources
    file_path       VARCHAR(512),                  -- S3/MinIO path
    file_size_bytes BIGINT,
    original_filename VARCHAR(255),
    
    -- Training metadata
    chunk_count     INT DEFAULT 0,
    last_trained_at TIMESTAMPTZ,
    error_message   TEXT,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_data_sources_client ON data_sources(client_id);
CREATE INDEX idx_data_sources_status ON data_sources(status);
```

#### Table: `training_jobs`
```sql
CREATE TABLE training_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_id       UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status          VARCHAR(32) DEFAULT 'queued',  -- queued | scraping | chunking | embedding | done | failed
    progress        INT DEFAULT 0,                 -- 0-100
    stage_message   VARCHAR(255),                  -- "Scraping page 4 of 20..."
    chunks_created  INT DEFAULT 0,
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_training_jobs_client ON training_jobs(client_id);
CREATE INDEX idx_training_jobs_status ON training_jobs(status);
```

#### Table: `chat_sessions`
```sql
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    session_key     VARCHAR(128) UNIQUE NOT NULL,  -- public session identifier
    user_identifier VARCHAR(255),                  -- optional: email or user_id from host site
    ip_address      INET,
    user_agent      TEXT,
    message_count   INT DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_sessions_client ON chat_sessions(client_id);
CREATE INDEX idx_chat_sessions_key ON chat_sessions(session_key);
```

#### Table: `chat_messages`
```sql
CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,          -- 'user' | 'assistant' | 'system'
    content         TEXT NOT NULL,
    sources         TEXT[],                        -- source URLs/filenames used for answer
    tokens_used     INT,
    latency_ms      INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_client ON chat_messages(client_id);
CREATE INDEX idx_chat_messages_created ON chat_messages(created_at DESC);
```

#### Table: `widget_configs`
```sql
CREATE TABLE widget_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    bot_name        VARCHAR(100) DEFAULT 'Assistant',
    welcome_message TEXT DEFAULT 'Hi! How can I help you today?',
    primary_color   VARCHAR(16) DEFAULT '#4F46E5',
    avatar_url      VARCHAR(512),
    is_enabled      BOOLEAN DEFAULT TRUE,
    fallback_message TEXT DEFAULT 'I''m not sure about that. Let me connect you with a human.',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### Table: `refresh_tokens`
```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 8.2 Milvus (Vector DB) Design

**Strategy:** One collection per client. This provides:
- Strong data isolation between tenants
- Easy bulk delete when a client removes all data
- Optimized ANN search (no cross-client filtering needed)

```python
# Collection naming convention
collection_name = f"cx_client_{client_id.replace('-', '_')}"
# e.g. cx_client_550e8400_e29b_41d4_a716_446655440000

# Alternatively, use one collection + partition per client
# (better if you have 1000s of clients with small data)
partition_name = f"client_{client_id.replace('-', '_')}"
```

**Fields in Milvus Collection:**
```
chunk_id      (VARCHAR, primary key)
client_id     (VARCHAR)
source_id     (VARCHAR)
source_name   (VARCHAR)
source_type   (VARCHAR)   ← "url" | "pdf" | "docx"
source_url    (VARCHAR)   ← original URL or filename for citation
text          (VARCHAR)   ← actual chunk content
chunk_index   (INT64)
embedding     (FLOAT_VECTOR, dim=1536)
```

**Why store `text` in Milvus too?** So you don't need an extra DB roundtrip to fetch chunk content after similarity search. The full chunk text + metadata comes back in one query.

---

## 9. Agent / RAG Query Pipeline

### 9.1 Full Query Flow

```python
# services/agent/pipeline.py

async def handle_query(
    client_key: str,
    session_id: str,
    user_message: str,
    history: list[dict]
) -> AsyncGenerator[str, None]:

    # 1. Resolve client from client_key
    client = await get_client_by_key(client_key)
    
    # 2. Check if client is active + widget enabled
    if not client.is_active or not client.widget_config.is_enabled:
        yield fallback_message(client)
        return

    # 3. Embed the user query
    query_embedding = await embed_text(user_message)

    # 4. Search Milvus for top-K relevant chunks
    results = await milvus_search(
        collection_name=f"cx_client_{client.id}",
        query_vector=query_embedding,
        top_k=5,
        output_fields=["text", "source_name", "source_url", "source_type"]
    )

    # 5. Build context string from retrieved chunks
    context = build_context(results)            # ranked, deduplicated
    sources = extract_sources(results)          # for citation in response

    # 6. Detect if query needs human handoff
    if should_escalate(user_message, context):
        yield escalation_message(client)
        return

    # 7. Build full prompt
    prompt = build_rag_prompt(
        bot_name=client.widget_config.bot_name,
        context=context,
        history=history[-6:],                  # last 3 turns for brevity
        user_message=user_message
    )

    # 8. Stream response from LLM
    async for token in llm_stream(prompt):
        yield token

    # 9. Save to DB (fire-and-forget)
    asyncio.create_task(
        save_message(session_id, client.id, user_message, full_response, sources)
    )
```

### 9.2 RAG System Prompt Template

```
You are {bot_name}, a helpful customer support assistant for {company_name}.
Your job is to answer questions accurately based ONLY on the provided context.

Rules:
- Answer ONLY from the context below. Do not make up information.
- If the answer is not in the context, say: "I don't have that information right now. 
  Would you like to speak with a human agent?"
- Be concise, friendly, and professional.
- Do not reveal internal document names or technical details.

--- CONTEXT ---
{context}
--- END CONTEXT ---

Conversation history:
{history}

User: {user_message}
{bot_name}:
```

### 9.3 Context Builder

```python
def build_context(results: list[dict]) -> str:
    seen = set()
    context_parts = []
    
    for result in results:
        text = result["text"].strip()
        # Deduplicate near-identical chunks
        key = text[:100]
        if key in seen:
            continue
        seen.add(key)
        context_parts.append(
            f"[Source: {result['source_name']}]\n{text}"
        )
    
    return "\n\n---\n\n".join(context_parts)
```

### 9.4 Human Handoff Detection

```python
ESCALATION_PHRASES = [
    "speak to a human", "talk to someone", "real person",
    "agent please", "human support", "not helpful",
    "call me", "phone number", "urgent", "complaint"
]

def should_escalate(message: str, context: str) -> bool:
    msg_lower = message.lower()
    # Phrase-based detection
    if any(phrase in msg_lower for phrase in ESCALATION_PHRASES):
        return True
    # No relevant context found
    if not context.strip():
        return True
    return False
```

### 9.5 Conversation History Management

- Last **N turns** (configurable, default 6 messages = 3 user + 3 assistant) sent to LLM
- Full history stored in PostgreSQL `chat_messages`
- Widget sends `session_id` on every request; backend fetches recent messages
- Redis cache for last 10 messages per session (TTL: 2 hours)

---

## 10. Client Identity & Multi-Tenancy

### 10.1 Keys Overview

| Key | Where Used | Who Sees It | Purpose |
|---|---|---|---|
| `client_id` (UUID) | Internal DB foreign keys | Never exposed | Unique database identifier |
| `client_key` (`ck_` prefix, 32-char) | Widget script tag, chat API | Public (client embeds it) | Identifies which client's knowledge base to query |
| JWT Access Token | Dashboard API calls | Dashboard only | Auth for management endpoints |

### 10.2 `client_key` Generation

```python
import secrets

def generate_client_key() -> str:
    return "ck_" + secrets.token_urlsafe(32)
    # e.g. ck_aB3kL9mNpQrStUvWxYz...
```

### 10.3 `client_key` Rotation

When client rotates their key:
1. New key generated and saved
2. Old key immediately invalidated
3. Client must update the `<script>` tag on their website
4. All existing sessions continue using `session_id` (unaffected)

### 10.4 Milvus Namespace Isolation

```python
# Every Milvus operation is scoped to the client's collection
async def search_client_knowledge(client_id: str, query_vector: list[float]):
    collection = Collection(f"cx_client_{client_id.replace('-','_')}")
    return collection.search(
        data=[query_vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"ef": 128}},
        limit=5,
        output_fields=["text", "source_name", "source_url"]
    )
```

---

## 11. Async Job Queue Architecture

### 11.1 Celery Task Definitions

```python
# tasks/training_tasks.py

@celery_app.task(bind=True, max_retries=3)
def run_training_job(self, job_id: str, source_id: str, client_id: str):
    try:
        update_job(job_id, status="scraping", progress=5)
        
        source = get_source(source_id)
        
        if source.type == "url":
            text = run_scraper(source.urls, source.scrape_config)
            update_job(job_id, status="scraping", progress=40)
        else:
            text = run_doc_parser(source.file_path, source.type)
            update_job(job_id, status="chunking", progress=40)
        
        update_job(job_id, status="chunking", progress=50)
        chunks = chunk_text(text, source_meta(source))
        
        update_job(job_id, status="embedding", progress=60)
        chunks_with_embeddings = embed_chunks(chunks)   # batched
        
        update_job(job_id, status="embedding", progress=80)
        upsert_to_milvus(client_id, chunks_with_embeddings)
        
        update_source(source_id, status="trained", chunk_count=len(chunks))
        update_job(job_id, status="done", progress=100)
        
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))
        update_source(source_id, status="failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
```

### 11.2 Redis Job Status

```python
# For real-time dashboard polling (faster than DB query)
redis.setex(
    f"job:{job_id}:status",
    ttl=86400,   # 24 hours
    value=json.dumps({
        "status": "embedding",
        "progress": 75,
        "stage_message": "Generating embeddings for 120 of 160 chunks..."
    })
)
```

### 11.3 Celery Configuration

```python
# config/celery_config.py

CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_EXPIRES = 86400   # 24 hours
CELERY_WORKER_CONCURRENCY = 4
CELERY_TASK_ROUTES = {
    "tasks.training_tasks.run_training_job": {"queue": "training"},
    "tasks.scraper_tasks.*": {"queue": "scraping"},
}
```

---

## 12. Security & Auth

### 12.1 JWT Auth Flow

```
POST /auth/login
    → verify password (bcrypt)
    → generate access_token (exp: 15 min)
    → generate refresh_token (exp: 30 days, stored hashed in DB)
    → return both tokens

POST /auth/refresh
    → verify refresh_token exists + not expired
    → rotate: delete old, issue new refresh_token
    → return new access_token

Protected API routes:
    → Extract Bearer token from Authorization header
    → Verify JWT signature + expiry
    → Attach client_id to request context
```

### 12.2 Security Checklist

- Passwords hashed with **bcrypt** (cost factor 12)
- JWT signed with **RS256** (asymmetric keys)
- `client_key` validated on every chat request (but is NOT a secret — it's like a public API key)
- SQL injection: use **SQLAlchemy ORM** (parameterized queries only)
- XSS: widget uses Shadow DOM + CSP-safe code
- File uploads: validate MIME type server-side, virus scan optional (ClamAV integration)
- Rate limiting on all endpoints (Redis-backed)
- CORS: restrict dashboard API to dashboard origin; chat API to `*` (needed for widget)
- Secrets in environment variables (never in code)

---

## 13. Deployment Architecture

### 13.1 Services Breakdown

```
┌─────────────────────────────────────────────────────┐
│                    Nginx / Load Balancer              │
│   dashboard.yourplatform.com → Next.js (port 3000)   │
│   api.yourplatform.com       → FastAPI  (port 8000)   │
│   cdn.yourplatform.com       → widget.js static file  │
└─────────────────────────────────────────────────────┘
         │                    │
    Next.js App          FastAPI App
    (Docker)             (Docker, 2+ workers)
                              │
              ┌───────────────┼───────────────┐
              │               │               │
           PostgreSQL       Redis           Milvus
           (Docker)        (Docker)         (Docker)
              │               │
           MinIO          Celery Workers
           (Docker)       (Docker, 4 workers)
```

### 13.2 Docker Compose (Development)

```yaml
# docker-compose.yml

services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis, milvus]

  dashboard:
    build: ./dashboard
    ports: ["3000:3000"]
    env_file: .env.local

  celery_worker:
    build: ./backend
    command: celery -A tasks worker -Q training,scraping -c 4
    env_file: .env
    depends_on: [redis, postgres]

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: cx_chatbot
      POSTGRES_USER: cx_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  milvus:
    image: milvusdb/milvus:v2.4.0
    command: milvus run standalone
    ports: ["19530:19530"]
    volumes: ["milvus_data:/var/lib/milvus"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio_data:/data"]

volumes:
  pgdata:
  milvus_data:
  minio_data:
```

### 13.3 Environment Variables

```bash
# Backend .env

DATABASE_URL=postgresql+asyncpg://cx_user:password@postgres:5432/cx_chatbot
REDIS_URL=redis://redis:6379/0
MILVUS_HOST=milvus
MILVUS_PORT=19530
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=cx-uploads

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

JWT_PRIVATE_KEY=...   # RS256 private key
JWT_PUBLIC_KEY=...    # RS256 public key
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=30

ALLOWED_ORIGINS=https://dashboard.yourplatform.com
```

---

## 14. Implementation Phases & Task Breakdown

### Phase 1 — Foundation (Week 1-2)

**Backend:**
- [ ] FastAPI project scaffold (`app/`, `models/`, `schemas/`, `routers/`, `services/`)
- [ ] PostgreSQL async connection (SQLAlchemy 2.0 async)
- [ ] Alembic migrations for all tables
- [ ] Auth endpoints: register, login, refresh, logout
- [ ] Client model + `client_key` generation
- [ ] JWT middleware

**Frontend:**
- [ ] Next.js project scaffold with Tailwind + shadcn/ui
- [ ] Auth pages (login, register)
- [ ] Auth context + token handling
- [ ] Dashboard shell layout (sidebar, topbar)

---

### Phase 2 — Data Ingestion (Week 3-4)

**Backend:**
- [ ] MinIO/S3 integration (upload, download helper)
- [ ] File upload endpoint (`POST /sources/upload`)
- [ ] URL source endpoint (`POST /sources/url`)
- [ ] Celery + Redis setup
- [ ] Document parsers: PDF (`pymupdf`), DOCX (`python-docx`)
- [ ] Scraper: `httpx` + `BeautifulSoup4` (static), `Playwright` (dynamic)
- [ ] Chunking service (`RecursiveCharacterTextSplitter`)
- [ ] Embedding service (OpenAI batched)
- [ ] Milvus collection creation + upsert logic
- [ ] Full training job Celery task
- [ ] Job status endpoint (`GET /jobs/{job_id}`)

**Frontend:**
- [ ] Sources page (table + add source modal)
- [ ] URL input form (multi-URL)
- [ ] File upload dropzone
- [ ] Training jobs page with live status polling
- [ ] Progress bar + stage messages

---

### Phase 3 — Chat Agent (Week 5-6)

**Backend:**
- [ ] Chat session creation / retrieval
- [ ] Milvus ANN search service
- [ ] RAG prompt builder
- [ ] LLM streaming integration (OpenAI + Anthropic)
- [ ] SSE streaming endpoint (`POST /chat/message`)
- [ ] Human handoff detection
- [ ] Chat history storage (PostgreSQL)
- [ ] Redis cache for recent messages

**Widget:**
- [ ] `widget.js` base scaffold (Shadow DOM)
- [ ] Chat panel HTML/CSS (brand-colored, responsive)
- [ ] SSE response streaming in widget
- [ ] `localStorage` session persistence
- [ ] Widget toggle (open/close)

---

### Phase 4 — Dashboard & Polish (Week 7-8)

**Frontend:**
- [ ] Widget customization page
- [ ] Embed code generator
- [ ] Chat logs page (session list + conversation view)
- [ ] Settings page (profile, rotate key)
- [ ] Dashboard overview stats (API calls: stats endpoint)
- [ ] Toast notifications (job done, errors)
- [ ] Mobile responsive polish

**Backend:**
- [ ] Widget config CRUD endpoints
- [ ] Chat logs / sessions endpoints
- [ ] Stats endpoint (source count, conversation count, etc.)
- [ ] `client_key` rotation endpoint
- [ ] Account deletion (cascade: delete all vectors + DB records)

---

### Phase 5 — Production Hardening (Week 9-10)

- [ ] Rate limiting middleware (Redis-backed)
- [ ] Full Docker Compose setup
- [ ] Nginx config (routing + SSL termination)
- [ ] Env variable audit (no secrets in code)
- [ ] Error monitoring (Sentry integration)
- [ ] Logging (structured JSON logs → ELK or Loki)
- [ ] Retry + dead-letter queue for failed Celery tasks
- [ ] Input validation (file type, size, URL format)
- [ ] CORS hardening
- [ ] Load test chat endpoint (locust or k6)
- [ ] Backup strategy: PostgreSQL daily dumps, Milvus snapshots

---

## Appendix: Key File/Folder Structure

```
/cx-chatbot
  /backend                     ← FastAPI backend
    /app
      /routers
        auth.py
        sources.py
        jobs.py
        chat.py
        widget.py
        clients.py
      /models                  ← SQLAlchemy models
      /schemas                 ← Pydantic schemas
      /services
        /scraper
          scraper.py
          extractor.py
        /document_processor
          parser.py
        /pipeline
          chunker.py
          embedder.py
          vector_store.py
        /agent
          pipeline.py
          prompt_builder.py
          handoff.py
      /tasks
        training_tasks.py
      /core
        auth.py
        config.py
        database.py
        redis.py
    main.py
    celery_app.py
    requirements.txt

  /dashboard                   ← Next.js frontend
    /app
    /components
    /lib
    /types
    package.json

  /widget                      ← Embeddable chat widget
    widget.js                  ← single-file output (built)
    /src
      index.js
      ui.js
      api.js
      styles.js

  /infra
    docker-compose.yml
    docker-compose.prod.yml
    /nginx
      nginx.conf
    /scripts
      init_milvus.py           ← create collections
      init_db.sh               ← run migrations

  .env.example
  README.md
```

---

*Blueprint version 1.0 — CX Chatbot B2B SaaS Platform*
*Generated for use with AI coding tools (Claude Code, Cursor, Windsurf, etc.)*
