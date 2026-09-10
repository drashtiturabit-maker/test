# CX Chatbot Platform — Complete Technical Blueprint v2

> **Product:** AI-powered Customer Experience Chatbot Platform (B2B SaaS)
> **Stack Reference:** LangGraph + FastAPI + Next.js + Milvus + PostgreSQL
> **Last Updated:** v2 — includes Agent Config, Plans, Domain Whitelist, Widget Embedding

---

## Table of Contents

1. [Product Vision & Architecture Overview](#1-product-vision--architecture-overview)
2. [Dashboard Ownership — Client vs Admin](#2-dashboard-ownership--client-vs-admin)
3. [Tech Stack](#3-tech-stack)
4. [Subscription Plans & Feature Limits](#4-subscription-plans--feature-limits)
5. [Frontend — Client Dashboard](#5-frontend--client-dashboard)
6. [Agent Configuration Page (New)](#6-agent-configuration-page-new)
7. [Chatbot Widget — Embedding on Client Websites](#7-chatbot-widget--embedding-on-client-websites)
8. [Domain Whitelist & Security](#8-domain-whitelist--security)
9. [Scraping Service — Single URL Strategy](#9-scraping-service--single-url-strategy)
10. [Document Upload Pipeline (Plan-Gated)](#10-document-upload-pipeline-plan-gated)
11. [RAG Training Pipeline](#11-rag-training-pipeline)
12. [Backend APIs](#12-backend-apis)
13. [Database Design (PostgreSQL + Milvus)](#13-database-design-postgresql--milvus)
14. [Agent / RAG Query Pipeline (LangGraph)](#14-agent--rag-query-pipeline-langgraph)
15. [Super Admin Panel](#15-super-admin-panel)
16. [Async Job Queue](#16-async-job-queue)
17. [Security & Auth](#17-security--auth)
18. [Deployment Architecture](#18-deployment-architecture)
19. [Implementation Phases & Task Checklist](#19-implementation-phases--task-checklist)

---

## 1. Product Vision & Architecture Overview

### What the Platform Does

A multi-tenant B2B SaaS product where each paying client (a company) gets:
- Their own isolated RAG agent trained on their website + uploaded documents
- A floating chat widget (bottom-right corner) embeddable on their website via a single `<script>` tag
- A self-service dashboard to manage data sources, agent behavior, and conversations
- Lead capture + meeting scheduling capabilities built into the agent
- Plan-based limits on storage, file count, and chat volume

### Existing Code Context

The agent layer is already partially built using:
- **LangGraph** — `StateGraph` with `agent_node → tool_node → final_node`
- **LangChain Tools** — `retrieve_knowledge`, `capture_lead_information`, `meeting_scheduling`, `math_expression_evaluator`
- **Milvus** — Vector store, accessed via `/retrieve-context` API
- **langmem** — Conversation summarization for long context
- **Opik** — LLM call tracing
- **Cal.com API** — Meeting scheduling/rescheduling/cancellation
- **GraphState** — Typed state with `client_info`, `messages`, `chat_history`, `bot_name`, `company_name`, etc.

This blueprint tells you **what to build around that agent core** — the full platform.

### High-Level System Flow

```
 B2B CLIENT (Company X)
        │
        │  1. Registers on Platform
        │  2. Configures agent (name, tone, instructions)
        │  3. Adds ONE website URL + uploads documents
        │  4. Scraper runs → RAG trained
        │  5. Gets embed script for their website
        │
        ▼
 ┌──────────────────────────────────────────────────────────────────┐
 │               CLIENT DASHBOARD (Next.js)                         │
 │  Agent Config │ Data Sources │ Training Jobs │ Chat Logs │ Widget │
 └──────────────────────────────────────────────────────────────────┘
                            │
                       FastAPI Backend
                            │
          ┌─────────────────┼───────────────────┐
          │                 │                   │
       PostgreSQL        Redis              Milvus
    (clients, jobs,    (queue, cache,     (vectors per
     sessions, logs)    rate limits)       client)
          │
     Celery Workers
    (Scrape → Chunk → Embed → Store)


 COMPANY X'S WEBSITE (any domain)
   └── <script src="widget.js" data-client-key="ck_...">
         │
         ├── Domain check → allowed? ✓ → render widget
         │                           ✗ → silent fail
         │
         └── User chats → POST /api/chat/message
                            │
                       LangGraph Agent
                       (retrieve_knowledge → Milvus)
                            │
                       Streamed SSE response
```

---

## 2. Dashboard Ownership — Client vs Admin

> **Question: Should the dashboard be for the admin or the client/user?**

### Answer: Give the Dashboard to the CLIENT. Build a Separate Super Admin Panel.

Here is the exact split:

| Dashboard Type | Who Uses It | What They Can Do |
|---|---|---|
| **Client Dashboard** | The B2B company that paid for the product | Upload data, train agent, configure bot, view their own chat logs, manage widget, manage their subscription |
| **Super Admin Panel** | You (the platform owner/operator) | View all clients, monitor usage across all tenants, manage plans, suspend accounts, view system health, override settings |

### Why this split?

Each B2B client is an independent tenant. They need full self-service control over their own bot — name, tone, instructions, data sources, logs — without ever seeing another client's data. The platform owner (you) needs a separate internal panel to manage the business.

Think of it like this:
- **Client Dashboard** = what Intercom or Crisp gives to each paying business
- **Super Admin Panel** = your internal CRM/ops tool to manage all of those businesses

Both are separate Next.js routes (or a separate app entirely for admin).

---

## 3. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend Dashboard | **Next.js 14 (App Router)** | Client portal |
| Super Admin Panel | **Next.js 14** (separate route `/admin`) | Platform owner only |
| Chat Widget | **Vanilla JS + Shadow DOM** | Zero-dependency, works on any site |
| Backend API | **FastAPI (Python 3.11+)** | Async, AI-workload optimized |
| Agent Framework | **LangGraph** | Already in use — keep it |
| LLM | **OpenAI GPT-4.1 / GPT-4.1 Mini** | Already in use |
| Task Queue | **Celery + Redis** | Async scraping + training |
| Relational DB | **PostgreSQL 15** | All structured data |
| Vector DB | **Milvus** | Already in use — one collection per client |
| Object Storage | **MinIO / AWS S3** | PDF, DOCX file storage |
| Embeddings | **OpenAI `text-embedding-3-small`** | 1536-dim |
| Scraping | **Playwright + BeautifulSoup4** | JS + static pages |
| Scheduling | **Cal.com API** | Already integrated |
| Tracing | **Opik** | Already integrated |
| Cache | **Redis** | Sessions, rate limits, job status |
| Auth | **JWT (RS256)** | Access + refresh tokens |
| Reverse Proxy | **Nginx** | Routes dashboard, API, widget CDN |

---

## 4. Subscription Plans & Feature Limits

Plans control what each client can do. All limits are enforced server-side (not just frontend UI).

### Plan Tiers

| Feature | Free | Starter | Pro | Enterprise |
|---|---|---|---|---|
| **Website URL** | 1 URL | 1 URL | 1 URL | 1 URL |
| **Crawl Depth** | 1 level | 2 levels | 3 levels | 5 levels |
| **Max Pages Scraped** | 10 pages | 30 pages | 100 pages | 500 pages |
| **PDF/DOCX Upload Count** | 1 file | 5 files | 20 files | Unlimited |
| **Max File Size (each)** | 5 MB | 10 MB | 25 MB | 50 MB |
| **Chat Messages / Month** | 500 | 2,000 | 10,000 | Unlimited |
| **Chat Sessions (stored)** | 30 days | 90 days | 1 year | Unlimited |
| **Allowed Domains** | 1 | 3 | 10 | Unlimited |
| **Custom Instructions** | ✗ | ✓ | ✓ | ✓ |
| **Fallback Message Config** | Default only | ✓ | ✓ | ✓ |
| **Lead Capture Tool** | ✗ | ✓ | ✓ | ✓ |
| **Meeting Scheduling Tool** | ✗ | ✗ | ✓ | ✓ |
| **Remove "Powered by" branding** | ✗ | ✗ | ✓ | ✓ |
| **Priority Support** | ✗ | ✗ | ✗ | ✓ |

### How Limits Are Enforced

```python
# services/plan_enforcer.py

class PlanEnforcer:
    PLAN_LIMITS = {
        "free":       {"file_count": 1,  "file_size_mb": 5,  "pages": 10,  "depth": 1, "messages_month": 500,  "domains": 1},
        "starter":    {"file_count": 5,  "file_size_mb": 10, "pages": 30,  "depth": 2, "messages_month": 2000, "domains": 3},
        "pro":        {"file_count": 20, "file_size_mb": 25, "pages": 100, "depth": 3, "messages_month": 10000,"domains": 10},
        "enterprise": {"file_count": -1, "file_size_mb": 50, "pages": 500, "depth": 5, "messages_month": -1,   "domains": -1},
    }

    @staticmethod
    def can_upload_file(client: Client, file_size_bytes: int) -> tuple[bool, str]:
        limits = PlanEnforcer.PLAN_LIMITS[client.plan]
        current_count = count_files_for_client(client.id)
        max_count = limits["file_count"]
        max_size_mb = limits["file_size_mb"]
        file_size_mb = file_size_bytes / (1024 * 1024)

        if max_count != -1 and current_count >= max_count:
            return False, f"Your {client.plan} plan allows {max_count} file(s). Upgrade to upload more."
        if file_size_mb > max_size_mb:
            return False, f"File exceeds the {max_size_mb}MB limit on your {client.plan} plan."
        return True, "OK"

    @staticmethod
    def can_send_message(client: Client, messages_this_month: int) -> tuple[bool, str]:
        limits = PlanEnforcer.PLAN_LIMITS[client.plan]
        limit = limits["messages_month"]
        if limit == -1:
            return True, "OK"
        if messages_this_month >= limit:
            return False, "Monthly message limit reached. Please upgrade your plan."
        return True, "OK"

    @staticmethod
    def check_custom_instructions(client: Client) -> bool:
        return client.plan in ("starter", "pro", "enterprise")
```

### Plan Limit UI Feedback

In the dashboard, every limit shows a usage bar:
```
Documents Uploaded  [■■■□□]  3 / 5  (Starter plan)
                                      [Upgrade to Pro →]
```

When a limit is hit, the upload button is disabled and shows a tooltip: *"Upgrade your plan to upload more files."*

---

## 5. Frontend — Client Dashboard

### Project Structure

```
/dashboard
  /app
    /auth
      login/page.tsx
      register/page.tsx
      forgot-password/page.tsx
    /(protected)
      layout.tsx                ← auth guard + sidebar shell
      /overview
        page.tsx                ← stats: messages, sources, sessions
      /agent-config
        page.tsx                ← bot name, tone, instructions, fallback
      /data-sources
        page.tsx                ← list all sources (URL + files)
        /add/page.tsx           ← add URL or upload file
      /training
        page.tsx                ← training job list + live progress
      /chat-logs
        page.tsx                ← conversation list
        /[session_id]/page.tsx  ← full conversation view
      /widget
        page.tsx                ← widget preview + embed code + domain whitelist
      /settings
        page.tsx                ← profile, plan info, rotate key, danger zone
  /components
    /dashboard
      Sidebar.tsx
      PlanLimitBar.tsx          ← reusable usage bar component
      JobStatusBadge.tsx
      SourceTable.tsx
      WidgetPreview.tsx
      EmbedCodeBlock.tsx
      DomainWhitelistManager.tsx
  /lib
    api.ts
    auth.ts
    hooks/
      useJobs.ts                ← polls job status every 3s
      usePlanLimits.ts          ← fetches + caches plan limits
```

### Key Pages Summary

**Overview Page**
- Cards: total sources, total chat sessions, messages this month (with limit bar), agent status (active/inactive)
- Recent training jobs list
- Quick action: "Add Data Source"

**Agent Config Page** — see full spec in Section 6

**Data Sources Page**
- Table: Name | Type | Status | Pages/Chunks | Last Trained | Actions
- "Add Source" modal with two tabs: Website URL / Upload File
- Per-source actions: Retrain | Delete | View Chunks (debug, Pro+ only)
- URL tab: single URL input field (see Section 9)
- File tab: drag-drop zone with plan-based limit display

**Training Jobs Page**
- Live status with stage labels: `queued → scraping → chunking → embedding → done`
- Progress bar per job
- Error expand panel on failures
- Polling via `useJobs` hook (3s interval, stops when all jobs terminal)

**Chat Logs Page**
- Filter: date range, keyword search, session source
- Click to open full conversation thread
- Export session as JSON

**Widget Page**
- Live widget preview (iframe sandbox)
- Embed code block (read-only, copy button)
- Domain Whitelist manager (add/remove domains, see Section 8)
- Toggle widget on/off globally

**Settings Page**
- Profile: name, email, company
- Current plan + usage summary
- Rotate `client_key` button (with confirmation modal)
- Danger zone: Delete account (wipes all vectors + DB records)

---

## 6. Agent Configuration Page (New)

This is the core page where clients customize how their bot behaves. It maps directly to the `GraphState` fields `bot_name`, `company_name`, and prompt variables in `agent_prompt`.

### Fields

| Field | Type | Required | Default | Plan Gate |
|---|---|---|---|---|
| **Agent Name** | Text input | Yes | "Assistant" | All plans |
| **Company Name** | Text input | Yes | (from registration) | All plans |
| **Tone** | Dropdown select | Yes | "Professional" | All plans |
| **Custom Instructions** | Textarea | No | "" | Starter+ |
| **Fallback Message** | Textarea | No | Platform default | Starter+ |

### Tone Options

```
Professional  (default) — formal, accurate, business-like
Friendly      — warm, approachable, uses light emojis
Formal        — very structured, no casual language
Casual        — relaxed, conversational
```

Each tone maps to a tone-modifier string injected into the system prompt at runtime.

### Custom Instructions Field

Free-form textarea. Clients can write things like:
- *"Always mention our 30-day free trial when users ask about pricing."*
- *"Do not discuss competitors. Redirect to our product page instead."*
- *"Always respond in Spanish regardless of the user's language."*
- *"If the user asks about returns, always offer a direct refund without conditions."*

Max characters: 1,000 (Starter), 3,000 (Pro), 10,000 (Enterprise)

### Fallback Message Field

Shown when the agent has no relevant knowledge OR detects a human handoff trigger.

Default (all plans):
> *"I'm sorry, I don't have that information right now. Would you like to connect with our team for further assistance?"*

Clients on Starter+ can customize this text.

### How These Fields Feed Into the Agent

The values are stored in PostgreSQL `agent_configs` table and passed into `execute_graph()` at runtime:

```python
# main.py — execute_graph()

input_dict = {
    "client_info": {
        "client_key": client.client_key,
        "environment_type": "live",
    },
    "messages": query,
    "thread_id": thread_id,
    "bot_name": agent_config.bot_name,           # ← from Agent Config page
    "company_name": agent_config.company_name,   # ← from Agent Config page
    "tone": agent_config.tone,                   # ← injected into system prompt
    "custom_instructions": agent_config.custom_instructions,  # ← appended to system prompt
    "fallback_message": agent_config.fallback_message,        # ← used in handoff_detector
    "current_date": now.strftime("%a, %d %b %Y"),
}
```

### Updated System Prompt Template

```
You are {bot_name}, representing {company_name}.
Current date: {current_date}

## Tone
{tone_description}

## Custom Instructions
{custom_instructions}

## Core Behavior
- Answer ONLY from the company's knowledge base retrieved via your tools.
- If the answer is not found, use this fallback response:
  "{fallback_message}"
- Never fabricate information. Never discuss competitors.
- Root all responses in {company_name}'s world only.
```

Where `tone_description` maps:
```python
TONE_DESCRIPTIONS = {
    "professional": "Communicate in a professional, accurate, and business-like manner.",
    "friendly": "Be warm, approachable, and use light emojis where natural.",
    "formal": "Use highly structured, formal language with no casual expressions.",
    "casual": "Keep a relaxed, conversational, easy-going tone.",
}
```

### API Endpoint

```
GET  /api/agent-config          ← fetch current config
PUT  /api/agent-config          ← save changes

Request body (PUT):
{
  "bot_name": "Spark",
  "company_name": "ESparkBiz",
  "tone": "professional",
  "custom_instructions": "Always mention our free trial...",
  "fallback_message": "Our team will reach out shortly."
}
```

---

## 7. Chatbot Widget — Embedding on Client Websites

> **Main Question: How does our chatbot appear at the bottom-right corner of another company's website?**

### The Answer: A Single `<script>` Tag

The client copies one line of code from their Widget page and pastes it before `</body>` on their website:

```html
<script 
  src="https://cdn.yourcxplatform.com/widget.js"
  data-client-key="ck_aB3kL9mN..."
  async
></script>
```

That's it. No npm install. No React. No build step. Works on WordPress, Shopify, plain HTML, or any framework.

### How `widget.js` Works Internally

```
Page loads → <script> tag executes widget.js
                    │
                    ▼
         Read data-client-key from script tag
                    │
                    ▼
         GET /api/widget/config?key=ck_...
         (fetches: bot_name, color, welcome_msg, enabled)
                    │
                    ├── enabled: false → EXIT silently (no widget shown)
                    │
                    ▼
         Domain check: is window.location.hostname in allowed_domains?
                    │
                    ├── No → EXIT silently (widget does not render)
                    │
                    ▼
         Inject Shadow DOM container into document.body
                    │
                    ▼
         Render: floating button (bottom-right, fixed position)
                    │
         User clicks button
                    │
                    ▼
         Chat panel slides up (CSS transition)
         Shows welcome message from config
                    │
         User types + sends message
                    │
                    ▼
         POST /api/chat/message (with client_key + session_id)
         Response: SSE stream → tokens rendered progressively
```

### Widget Visual Structure

```
╔═══════════════════════════╗  ← fixed, bottom-right, z-index: 9999
║  🤖 Spark          [×]   ║  ← bot name from config, close button
╠═══════════════════════════╣
║                           ║
║  Hi! How can I help       ║  ← welcome message
║  you today?               ║
║                           ║
║  ┌───────────────────────┐║
║  │ User message here     │║
║  └───────────────────────┘║
║                           ║
║  ● ● ●  (typing indicator)║
║                           ║
╠═══════════════════════════╣
║ [Type a message...] [Send]║
╠═══════════════════════════╣
║ Powered by CX Platform    ║  ← hidden on Pro+
╚═══════════════════════════╝

[🤖]  ← floating bubble when panel is closed
```

### Widget JS Architecture

```javascript
// widget.js (single file, ~8KB minified)

(function () {
  const script = document.currentScript;
  const CLIENT_KEY = script.getAttribute('data-client-key');
  const API_BASE = 'https://api.yourcxplatform.com';

  // 1. Fetch config
  fetch(`${API_BASE}/api/widget/config?key=${CLIENT_KEY}`)
    .then(r => r.json())
    .then(config => {
      if (!config.enabled) return;

      // 2. Domain check
      const hostname = window.location.hostname;
      if (!config.allowed_domains.includes(hostname) &&
          !config.allowed_domains.includes('*')) return;

      // 3. Mount Shadow DOM (CSS isolation from host site)
      const host = document.createElement('div');
      host.id = 'cx-widget-host';
      document.body.appendChild(host);
      const shadow = host.attachShadow({ mode: 'open' });

      // 4. Inject styles + HTML
      shadow.innerHTML = buildWidgetHTML(config);

      // 5. Session management
      let sessionId = localStorage.getItem('cx_session_' + CLIENT_KEY)
                      || generateSessionId();
      localStorage.setItem('cx_session_' + CLIENT_KEY, sessionId);

      // 6. Chat send handler with SSE streaming
      setupChatHandlers(shadow, CLIENT_KEY, sessionId, API_BASE);
    });

  function generateSessionId() {
    return 'sess_' + Math.random().toString(36).substr(2, 16);
  }
})();
```

### Why Shadow DOM?

The host company's website has its own CSS. Without Shadow DOM, your widget's styles would fight with theirs. Shadow DOM creates a completely isolated DOM tree — your widget CSS lives inside it, completely protected from and from affecting the host page.

### Session Persistence

- `session_id` is stored in `localStorage` with key `cx_session_{client_key}`
- This means the user's conversation **continues across page refreshes** on the same browser
- A new session starts if the user clears browser data or after TTL (configurable, default 24h)
- The backend stores full conversation in PostgreSQL `chat_messages` table

---

## 8. Domain Whitelist & Security

> **The problem:** If anyone finds your client's `client_key` (it's in their HTML source), they could embed your widget on any website. The domain whitelist prevents this.

### How It Works

1. Client registers allowed domains from their Widget page in the dashboard
2. Domains stored in PostgreSQL `allowed_domains` table
3. Widget script checks the current domain at load time
4. **Two layers of checking:**
   - **Client-side** (in widget.js): soft check — fast, good UX
   - **Server-side** (in `/api/chat/message`): hard check — security layer, can't be bypassed

```python
# In /api/chat/message endpoint

async def chat_message(payload: ChatRequest, request: Request):
    client = await get_client_by_key(payload.client_key)
    
    # Get Origin or Referer header from the browser request
    origin = request.headers.get("origin") or request.headers.get("referer", "")
    request_domain = extract_domain(origin)
    
    allowed = await get_allowed_domains(client.id)
    
    if allowed and request_domain not in allowed:
        raise HTTPException(403, "Domain not authorized for this client key.")
    
    # proceed with chat...
```

### Domain Management UI (Widget Page)

```
Allowed Domains
─────────────────────────────────────────────────────────
  app.companyxyz.com          [Remove]
  www.companyxyz.com          [Remove]
  staging.companyxyz.com      [Remove]
─────────────────────────────────────────────────────────
  [+ Add domain]   Free plan: 1 domain | Starter: 3 | Pro: 10
```

### Domain Entry Rules

- Enter only the hostname, no `https://` prefix: `www.company.com`
- Wildcards NOT supported (prevents abuse)
- `localhost` and `127.0.0.1` are auto-allowed in `sandbox` environment (for testing)
- Domain count enforced per plan (see Section 4)

### `client_key` vs Secret

| Property | `client_key` |
|---|---|
| Is it a secret? | **No** — it's like a public API key. It will be visible in the website's HTML source. That is fine and expected. |
| What protects it from abuse? | Domain whitelist (server-side check) + rate limiting |
| Can it be rotated? | Yes — from Settings page. Old key immediately invalidated. |

---

## 9. Scraping Service — Single URL Strategy

> **Design Decision: Accept only ONE root URL. The scraper crawls child pages automatically.**

### Why One URL?

- Simpler UX — clients don't need to figure out which pages to add
- Prevents duplicate content (if client adds both `/products` and the homepage, which already links to `/products`)
- Easier to control crawl scope via depth setting
- Cleaner re-training (just re-crawl the root)

### How It Works

```
Client enters: https://company.com
                        │
                  Scraper starts at root URL
                        │
              Extracts all internal links (<a href>)
              Filters: same domain only, no external links
                        │
              Crawls links up to configured depth
              (Free: 1 level, Pro: 3 levels, etc.)
                        │
              Max pages enforced per plan
                        │
              All scraped text → chunking → embedding → Milvus
```

### Data Source UI (Add URL)

```
Website URL
─────────────────────────────────────────────────────────
  Enter your website's main URL:
  [ https://www.yourcompany.com           ]

  ℹ  We'll automatically crawl your website starting from
     this URL. Only pages on the same domain will be 
     included. Based on your plan (Starter), we'll crawl
     up to 2 levels deep and process up to 30 pages.

  [Start Scraping & Training]
─────────────────────────────────────────────────────────
  ⚠ You already have a website source. Adding a new one 
    will replace the current one.          [Replace]
```

Note: Only **one URL source** is allowed per client at a time. Adding a new one replaces the old one (after confirmation). This keeps the data clean.

### URL Validation

```python
def validate_root_url(url: str) -> tuple[bool, str]:
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "URL must start with http:// or https://"
        if not parsed.netloc:
            return False, "Invalid URL format."
        if parsed.path not in ("", "/"):
            # Allow, but warn that crawling starts from this path
            pass
        return True, "OK"
    except Exception:
        return False, "Invalid URL."
```

### Scraper Logic

```python
# services/scraper/scraper.py

async def scrape_website(root_url: str, max_depth: int, max_pages: int) -> list[dict]:
    visited = set()
    results = []
    queue = [(root_url, 0)]  # (url, depth)

    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        # Fetch page (Playwright for JS, httpx for static)
        html = await fetch_page(url)
        if not html:
            continue

        # Extract clean text
        text = extract_text(html)
        if text.strip():
            results.append({"url": url, "text": text, "depth": depth})

        # Enqueue child links (same domain only)
        if depth < max_depth:
            links = extract_internal_links(html, base_domain=get_domain(root_url))
            for link in links:
                if link not in visited:
                    queue.append((link, depth + 1))

    return results


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Remove boilerplate
    for tag in soup(["nav", "footer", "header", "script", "style",
                     "aside", "form", "iframe", "noscript"]):
        tag.decompose()
    # Extract meaningful text blocks
    blocks = []
    for tag in soup.find_all(["h1","h2","h3","h4","p","li","td","th","blockquote","article"]):
        t = tag.get_text(" ", strip=True)
        if len(t) > 30:  # skip micro-text
            blocks.append(t)
    return "\n\n".join(blocks)
```

---

## 10. Document Upload Pipeline (Plan-Gated)

### Supported Formats & Size Limits

| Format | Parser Library | Max Size by Plan |
|---|---|---|
| PDF | `pymupdf` (fitz) | Free: 5MB, Starter: 10MB, Pro: 25MB, Enterprise: 50MB |
| DOCX | `python-docx` | Same as PDF |
| TXT | Native Python | Same as PDF |

### Upload Flow

```
1. Client selects file in dashboard
   └── Frontend validates: type + size (client-side, for fast feedback)

2. POST /api/sources/upload (multipart/form-data)
   └── Backend validates: type + size against plan limits
   └── If exceeds: return 400 with upgrade message
   └── If OK: save to MinIO at path: uploads/{client_id}/{source_id}/{filename}

3. PostgreSQL record created: data_sources (status = "pending")

4. Celery task queued: process_document.delay(source_id)

5. Worker: parse → chunk → embed → upsert Milvus
   └── Update job status at each stage

6. Dashboard polls job status → shows progress → "Trained ✓"
```

### File Count Enforcement

```python
# In POST /api/sources/upload

existing_files = await count_file_sources(client_id)
can_upload, reason = PlanEnforcer.can_upload_file(client, file.size)

if not can_upload:
    raise HTTPException(
        status_code=402,
        detail={
            "error": "plan_limit_exceeded",
            "message": reason,
            "upgrade_url": "https://yourcxplatform.com/upgrade"
        }
    )
```

### Document Parsers

```python
# services/document_processor/parser.py

def parse_pdf(filepath: str) -> str:
    doc = fitz.open(filepath)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text:
            pages.append(f"[Page {i+1}]\n{text}")
    return "\n\n".join(pages)


def parse_docx(filepath: str) -> str:
    doc = Document(filepath)
    parts = []
    # Paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text.strip())
    # Tables (flatten as text)
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n\n".join(parts)
```

---

## 11. RAG Training Pipeline

### Pipeline Stages

```
Raw Text (from scraper or document parser)
         │
         ▼
  [Stage 1] Text Cleaner
         │  - Unicode normalization
         │  - Remove repeated whitespace
         │  - Strip page numbers / footers
         ▼
  [Stage 2] Chunker (RecursiveCharacterTextSplitter)
         │  - chunk_size: 512 tokens
         │  - chunk_overlap: 64 tokens
         │  - Respects paragraph/sentence boundaries
         ▼
  [Stage 3] Metadata Tagger
         │  - source_url (for website) or filename (for docs)
         │  - client_id, source_id, chunk_index
         │  - source_type: "url" | "pdf" | "docx"
         ▼
  [Stage 4] Embedding Generator
         │  - OpenAI text-embedding-3-small
         │  - Batch size: 100 chunks per API call
         │  - Retry 3x on failure
         ▼
  [Stage 5] Milvus Upsert
             - Collection: cx_client_{client_id}
             - Upsert by chunk_id (idempotent)
             - Store text + metadata in payload fields
```

### Chunking

```python
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
            "source_type": source_meta["type"],
            "source_name": source_meta["name"],
            "source_url": source_meta.get("url", source_meta.get("filename", "")),
            "text": chunk,
            "chunk_index": i,
        }
        for i, chunk in enumerate(chunks)
    ]
```

### Milvus Collection Schema

```python
from pymilvus import CollectionSchema, FieldSchema, DataType

def get_collection_schema() -> CollectionSchema:
    return CollectionSchema(fields=[
        FieldSchema("chunk_id",    DataType.VARCHAR, max_length=256, is_primary=True),
        FieldSchema("client_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("source_id",   DataType.VARCHAR, max_length=64),
        FieldSchema("source_name", DataType.VARCHAR, max_length=512),
        FieldSchema("source_type", DataType.VARCHAR, max_length=32),
        FieldSchema("source_url",  DataType.VARCHAR, max_length=1024),
        FieldSchema("text",        DataType.VARCHAR, max_length=4096),
        FieldSchema("chunk_index", DataType.INT64),
        FieldSchema("embedding",   DataType.FLOAT_VECTOR, dim=1536),
    ])

# HNSW index for fast ANN search
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 256}
}
```

### Re-train & Delete Strategy

```python
async def retrain_source(source_id: str, client_id: str):
    # Step 1: Delete existing chunks from Milvus
    collection = Collection(f"cx_client_{client_id}")
    collection.delete(expr=f'source_id == "{source_id}"')
    
    # Step 2: Re-run pipeline from scratch
    await run_training_pipeline(source_id, client_id)


async def delete_source(source_id: str, client_id: str):
    # Delete from Milvus
    collection = Collection(f"cx_client_{client_id}")
    collection.delete(expr=f'source_id == "{source_id}"')
    
    # Delete file from MinIO (if document)
    await minio_client.delete_object(source_id)
    
    # Delete PostgreSQL record (cascades to training_jobs)
    await db.execute("DELETE FROM data_sources WHERE id = $1", source_id)
```

---

## 12. Backend APIs

### Full API Map

```
/api
  /auth
    POST  /register
    POST  /login
    POST  /refresh
    POST  /logout

  /agent-config
    GET   /                    ← get current agent config
    PUT   /                    ← update agent config

  /sources
    GET   /                    ← list all sources
    POST  /url                 ← submit root URL
    POST  /upload              ← upload PDF/DOCX
    DELETE/{source_id}         ← delete source + vectors
    POST  /{source_id}/retrain ← re-run pipeline

  /jobs
    GET   /                    ← list training jobs
    GET   /{job_id}            ← live job status (for polling)

  /chat
    POST  /message             ← send message → SSE stream
    GET   /sessions            ← list all sessions
    GET   /sessions/{id}       ← full conversation
    DELETE/sessions/{id}       ← delete session

  /widget
    GET   /config              ← PUBLIC endpoint (no auth), by client_key
    PUT   /config              ← update widget appearance
    GET   /domains             ← list allowed domains
    POST  /domains             ← add domain
    DELETE/domains/{id}        ← remove domain

  /clients
    GET   /me                  ← current client profile
    PUT   /me                  ← update profile
    POST  /rotate-key          ← rotate client_key
    GET   /plan                ← current plan + usage stats
    DELETE/me                  ← delete account

  /admin (Super Admin — separate auth)
    GET   /clients             ← all clients
    GET   /clients/{id}        ← single client
    PUT   /clients/{id}/plan   ← change plan
    DELETE/clients/{id}        ← suspend/delete
    GET   /stats               ← platform-wide stats
```

### Key Endpoint Specs

#### `POST /api/sources/url`
```json
Request:
{
  "name": "Company Website",
  "root_url": "https://company.com"
}

Response:
{
  "source_id": "src_abc123",
  "job_id": "job_xyz789",
  "status": "queued",
  "plan_limits": {
    "max_depth": 2,
    "max_pages": 30
  }
}
```

#### `POST /api/sources/upload`
```
Content-Type: multipart/form-data
Fields:
  - file: <binary> (PDF or DOCX)
  - name: "Product Manual 2024"

Success Response:
{
  "source_id": "src_def456",
  "job_id": "job_uvw321",
  "status": "queued",
  "filename": "product_manual.pdf",
  "size_mb": 4.2
}

Error Response (plan limit):
{
  "error": "plan_limit_exceeded",
  "message": "Your Starter plan allows 5 files. You currently have 5.",
  "upgrade_url": "/upgrade"
}
```

#### `POST /api/chat/message` (SSE Stream)
```json
Request:
{
  "client_key": "ck_abc123xyz",
  "session_id": "sess_abc001",
  "message": "What is your refund policy?"
}

Response: Content-Type: text/event-stream

data: {"type": "token", "content": "Our "}
data: {"type": "token", "content": "refund policy "}
data: {"type": "token", "content": "allows..."}
data: {"type": "done", "sources": ["https://company.com/refunds"], "tokens_used": 412}
data: {"type": "error", "message": "Monthly limit reached. Please upgrade."}
```

#### `GET /api/widget/config?key=ck_abc123`
```json
Response (public — no auth, cached in Redis 60s):
{
  "bot_name": "Spark",
  "welcome_message": "Hi! How can I help you today?",
  "primary_color": "#4F46E5",
  "tone": "friendly",
  "enabled": true,
  "allowed_domains": ["www.esparkbiz.com", "esparkbiz.com"]
}
```

---

## 13. Database Design (PostgreSQL + Milvus)

### PostgreSQL Tables

#### `clients`
```sql
CREATE TABLE clients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    company_name    VARCHAR(255) NOT NULL,
    client_key      VARCHAR(64) UNIQUE NOT NULL,
    plan            VARCHAR(32) DEFAULT 'free',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_clients_key ON clients(client_key);
```

#### `agent_configs`
```sql
CREATE TABLE agent_configs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id            UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    bot_name             VARCHAR(100) DEFAULT 'Assistant',
    company_name         VARCHAR(255),
    tone                 VARCHAR(32) DEFAULT 'professional',
    custom_instructions  TEXT DEFAULT '',
    fallback_message     TEXT DEFAULT 'I don''t have that information. Would you like to speak with our team?',
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);
```

#### `widget_configs`
```sql
CREATE TABLE widget_configs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    primary_color     VARCHAR(16) DEFAULT '#4F46E5',
    avatar_url        VARCHAR(512),
    welcome_message   TEXT DEFAULT 'Hi! How can I help you today?',
    is_enabled        BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
```

#### `allowed_domains`
```sql
CREATE TABLE allowed_domains (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    domain      VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, domain)
);
CREATE INDEX idx_allowed_domains_client ON allowed_domains(client_id);
```

#### `data_sources`
```sql
CREATE TABLE data_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    type                VARCHAR(16) NOT NULL,         -- 'url' | 'pdf' | 'docx' | 'txt'
    status              VARCHAR(32) DEFAULT 'pending',-- pending|processing|trained|failed
    
    -- URL source fields
    root_url            VARCHAR(2048),
    scrape_config       JSONB DEFAULT '{}',
    pages_scraped       INT DEFAULT 0,
    
    -- File source fields
    file_path           VARCHAR(512),                 -- MinIO path
    file_size_bytes     BIGINT,
    original_filename   VARCHAR(255),
    
    -- Training metadata
    chunk_count         INT DEFAULT 0,
    last_trained_at     TIMESTAMPTZ,
    error_message       TEXT,
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_data_sources_client ON data_sources(client_id);
CREATE INDEX idx_data_sources_type ON data_sources(client_id, type);
```

#### `training_jobs`
```sql
CREATE TABLE training_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_id       UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status          VARCHAR(32) DEFAULT 'queued',  -- queued|scraping|chunking|embedding|done|failed
    progress        INT DEFAULT 0,                 -- 0–100
    stage_message   VARCHAR(255),
    chunks_created  INT DEFAULT 0,
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_training_jobs_client ON training_jobs(client_id);
```

#### `chat_sessions`
```sql
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    session_key     VARCHAR(128) UNIQUE NOT NULL,
    ip_address      INET,
    user_agent      TEXT,
    page_url        VARCHAR(2048),               -- which page of client's site
    message_count   INT DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sessions_client ON chat_sessions(client_id);
```

#### `chat_messages`
```sql
CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    role        VARCHAR(16) NOT NULL,     -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    sources     TEXT[],                   -- source URLs used for answer
    tokens_used INT,
    latency_ms  INT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_session ON chat_messages(session_id);
CREATE INDEX idx_messages_created ON chat_messages(created_at DESC);
```

#### `usage_counters`
```sql
CREATE TABLE usage_counters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    month_year  VARCHAR(7) NOT NULL,     -- e.g. "2024-01"
    msg_count   INT DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
-- Reset monthly via a scheduled Celery task
```

#### `refresh_tokens`
```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### Milvus Design

```
Collection naming: cx_client_{client_id_underscored}
e.g. cx_client_550e8400_e29b_41d4_a716_446655440000

Fields: chunk_id (PK), client_id, source_id, source_name,
        source_type, source_url, text, chunk_index, embedding (FLOAT_VECTOR 1536)

Index: HNSW, COSINE similarity
```

---

## 14. Agent / RAG Query Pipeline (LangGraph)

This section documents the full agent pipeline as it currently exists and how to wire it to the platform.

### Agent Graph

```
START
  │
  ▼
agent_node   ← builds prompt from state (bot_name, company_name, tone, custom_instructions)
  │            invokes LLM with bound tools (parallel_tool_calls=False)
  │
  ├──[tools needed]──► tool_node
  │                        │
  │                        │ retrieve_knowledge → POST /retrieve-context (Milvus)
  │                        │ capture_lead_information → save to leads API
  │                        │ meeting_scheduling → Cal.com API
  │                        │ math_expression_evaluator → safe eval
  │                        │
  │                    (loop back to agent_node)
  │
  └──[no tools needed]──► final_node → saves to chat_history → END
```

### Query Flow

```python
# Full request handling in the API layer

async def handle_chat_message(
    client_key: str,
    session_id: str,
    user_message: str,
):
    # 1. Resolve client
    client = await get_client_by_key(client_key)
    agent_config = await get_agent_config(client.id)
    
    # 2. Check monthly message limit
    usage = await get_monthly_usage(client.id)
    can_chat, reason = PlanEnforcer.can_send_message(client, usage.msg_count)
    if not can_chat:
        yield SSEEvent(type="error", message=reason)
        return

    # 3. Load recent chat history from PostgreSQL
    history = await get_recent_messages(session_id, limit=12)
    
    # 4. Build LangGraph config
    config = {
        "configurable": {
            "thread_id": session_id,
            "lead_generation_config": {
                "status": client.plan in ("starter", "pro", "enterprise"),
                "lead_generatiom_obj_mapper": required_params_mapper_obj.copy()
            },
            "meeting_scheduling_config": {
                "status": client.plan in ("pro", "enterprise")
            }
        }
    }

    # 5. Execute LangGraph agent
    result = execute_graph(
        thread_id=session_id,
        query=user_message,
        config=config,
        agent_config=agent_config,   # passes bot_name, company_name, tone, custom_instructions
    )

    # 6. Stream response tokens via SSE
    for token in result.get("streamed_tokens", []):
        yield SSEEvent(type="token", content=token)
    
    # 7. Increment usage counter
    await increment_message_count(client.id)
    
    # 8. Save messages to DB
    await save_messages(session_id, client.id, user_message, full_response, sources)
    
    yield SSEEvent(type="done", sources=sources)
```

### Agent Config Injection

```python
# Updated execute_graph signature
def execute_graph(thread_id: str, query, config: dict, agent_config: AgentConfig):
    
    tone_desc = TONE_DESCRIPTIONS[agent_config.tone]
    
    input_dict = {
        "client_info": {...},
        "messages": [HumanMessage(content=query)],
        "thread_id": thread_id,
        "bot_name": agent_config.bot_name,
        "company_name": agent_config.company_name,
        "tone_description": tone_desc,
        "custom_instructions": agent_config.custom_instructions,
        "fallback_message": agent_config.fallback_message,
        "current_date": now.strftime("%a, %d %b %Y"),
    }
    
    return agent_graph.graph.invoke(input_dict, config=config, stream_mode="values")
```

### Tool Activation by Plan

```python
# In runnables.py — get_agent_runnable()

def get_agent_runnable(plan: str, client_key: str):
    tools = [
        get_retrieve_knowledge_tool(),       # all plans
        get_math_expression_evaluator_tool() # all plans
    ]
    
    if plan in ("starter", "pro", "enterprise"):
        tools.append(get_collect_lead_information_tool())
    
    if plan in ("pro", "enterprise"):
        tools.append(get_meeting_scheduling_tool())
    
    # Build prompt with tone + custom instructions
    prompt = ChatPromptTemplate.from_messages([
        ("system", dynamic_agent_prompt),
        MessagesPlaceholder("messages"),
    ])
    
    return prompt | llm.bind_tools(tools, tool_choice="auto", parallel_tool_calls=False)
```

---

## 15. Super Admin Panel

### Who Uses It

The platform owner (you/your team). Not accessible to clients.

### Access Control

Separate admin users table with `role = "super_admin"`. JWT-based with short expiry (1h). Accessible only from a specific IP range or VPN.

### Features

**Clients Overview**
- Table: all registered clients, plan, status, last active, message count this month
- Filter by plan, status, date
- Actions: View, Change Plan, Suspend, Delete

**Client Detail View**
- Full profile
- Usage stats: messages this month, sources count, storage used
- Override settings (e.g. temporarily increase file limit for enterprise negotiation)
- View their chat logs (for support purposes)

**Platform Stats Dashboard**
- Total clients by plan
- Total messages today / this month
- Active Celery jobs
- Milvus storage usage
- API error rate

**Billing Integration Hooks**
- Webhook endpoints for payment provider (Stripe) to auto-update plan on subscription events

### Routes

```
/admin                    ← stats overview
/admin/clients            ← all clients table
/admin/clients/{id}       ← client detail
/admin/system             ← job queue health, error log
```

---

## 16. Async Job Queue

### Celery Task

```python
# tasks/training_tasks.py

@celery_app.task(bind=True, max_retries=3, acks_late=True)
def run_training_job(self, job_id: str, source_id: str, client_id: str):
    try:
        source = get_source(source_id)
        
        update_job(job_id, status="scraping", progress=5,
                   stage_message="Starting data collection...")

        if source.type == "url":
            plan = get_client_plan(client_id)
            limits = PlanEnforcer.PLAN_LIMITS[plan]
            pages = scrape_website(
                root_url=source.root_url,
                max_depth=limits["depth"],
                max_pages=limits["pages"]
            )
            raw_text_chunks = [(p["url"], p["text"]) for p in pages]
            update_job(job_id, progress=35,
                       stage_message=f"Scraped {len(pages)} pages")
        else:
            file_path = download_from_minio(source.file_path)
            text = parse_document(file_path, source.type)
            raw_text_chunks = [(source.original_filename, text)]
            update_job(job_id, progress=35,
                       stage_message="Document parsed successfully")

        update_job(job_id, status="chunking", progress=45,
                   stage_message="Splitting into chunks...")
        all_chunks = []
        for source_name, text in raw_text_chunks:
            chunks = chunk_text(text, {
                "source_id": source_id,
                "client_id": client_id,
                "type": source.type,
                "name": source_name,
                "url": source_name if source.type == "url" else ""
            })
            all_chunks.extend(chunks)

        update_job(job_id, status="embedding", progress=60,
                   stage_message=f"Generating embeddings for {len(all_chunks)} chunks...")
        chunks_with_embeddings = embed_chunks(all_chunks)  # batched 100 at a time

        update_job(job_id, progress=85,
                   stage_message="Storing in vector database...")
        upsert_to_milvus(client_id, chunks_with_embeddings)

        update_source(source_id, status="trained", chunk_count=len(all_chunks))
        update_job(job_id, status="done", progress=100,
                   stage_message="Training complete!", chunks_created=len(all_chunks))

    except Exception as exc:
        update_job(job_id, status="failed", error_message=str(exc))
        update_source(source_id, status="failed", error_message=str(exc))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
```

### Redis Job Status Cache

```python
# Fast status for dashboard polling (avoids DB query every 3s)
redis.setex(
    f"job_status:{job_id}",
    86400,  # 24hr TTL
    json.dumps({
        "status": "embedding",
        "progress": 72,
        "stage_message": "Generating embeddings for 144 of 200 chunks..."
    })
)
```

### Queue Config

```python
CELERY_TASK_ROUTES = {
    "tasks.training_tasks.run_training_job": {"queue": "training"},
}
CELERY_WORKER_CONCURRENCY = 4
CELERY_TASK_TIME_LIMIT = 3600      # 1 hour max per job
CELERY_TASK_SOFT_TIME_LIMIT = 3300 # warn at 55 min
```

---

## 17. Security & Auth

### Auth Flow

```
Register → hash password (bcrypt cost=12) → create client + agent_config + widget_config records

Login → verify password → issue:
  - access_token (JWT RS256, exp: 15 min)
  - refresh_token (random 64 bytes, stored hashed in DB, exp: 30 days)

API call → Bearer access_token → middleware verifies signature + expiry → attaches client_id

Refresh → verify refresh_token → rotate (delete old, issue new) → return new access_token
```

### Security Rules

- Passwords: bcrypt, cost factor 12
- JWT: RS256 (asymmetric). Private key server-only.
- `client_key`: public-facing, not a secret. Protected by domain whitelist + rate limits.
- File uploads: server-side MIME validation, size check, malware scanning optional (ClamAV)
- SQL: SQLAlchemy ORM only, no raw string interpolation
- Widget CORS: `/api/chat/*` allows `*` (must — widget runs from client domains). All other endpoints restricted.
- Rate limits via Redis (see Section 12)
- Admin panel: IP whitelist + separate auth

### Rate Limits

| Endpoint | Limit |
|---|---|
| `POST /chat/message` | 20 req/min per session_id |
| `POST /sources/upload` | 10 req/hour per client |
| `POST /sources/url` | 3 req/hour per client |
| `POST /auth/login` | 10 req/min per IP |
| `GET /widget/config` | 60 req/min (Redis cache helps) |

---

## 18. Deployment Architecture

### Services

```
Internet
   │
Nginx (SSL termination, routing)
   ├── dashboard.yourcxplatform.com → Next.js (port 3000)
   ├── api.yourcxplatform.com       → FastAPI  (port 8000)
   ├── cdn.yourcxplatform.com       → widget.js static file
   └── admin.yourcxplatform.com     → Next.js admin (port 3001)

FastAPI → PostgreSQL
       → Redis
       → Milvus
       → MinIO

Celery Workers (4 workers) → PostgreSQL + Redis + Milvus + MinIO
```

### Docker Compose (Development)

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [postgres, redis, milvus, minio]

  dashboard:
    build: ./dashboard
    ports: ["3000:3000"]
    env_file: .env.local

  celery_worker:
    build: ./backend
    command: celery -A tasks worker -Q training -c 4 --loglevel=info
    env_file: .env
    depends_on: [redis, postgres, milvus, minio]

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
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes: ["minio_data:/data"]

volumes:
  pgdata:
  milvus_data:
  minio_data:
```

### Environment Variables

```bash
# .env (backend)
DATABASE_URL=postgresql+asyncpg://cx_user:pass@postgres:5432/cx_chatbot
REDIS_URL=redis://redis:6379/0
MILVUS_HOST=milvus
MILVUS_PORT=19530
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=cx-uploads

OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

JWT_PRIVATE_KEY=...
JWT_PUBLIC_KEY=...
JWT_ACCESS_EXPIRE_MINUTES=15
JWT_REFRESH_EXPIRE_DAYS=30

OPIK_API_KEY=...
CALCOM_API_KEY=...
USER_TIMEZONE=Asia/Kolkata

ADMIN_IP_WHITELIST=10.0.0.1,10.0.0.2
```

---

## 19. Implementation Phases & Task Checklist

### Phase 1 — Foundation (Week 1–2)

**Backend:**
- [ ] FastAPI project scaffold (`routers/`, `models/`, `schemas/`, `services/`, `tasks/`)
- [ ] PostgreSQL async setup (SQLAlchemy 2.0 async + asyncpg)
- [ ] Alembic migrations: all tables from Section 13
- [ ] Auth: register, login, refresh, logout endpoints
- [ ] JWT RS256 middleware
- [ ] Client creation + `client_key` generation
- [ ] `agent_configs` + `widget_configs` auto-created on client register
- [ ] Plan enforcer service

**Frontend:**
- [ ] Next.js 14 scaffold with Tailwind CSS + shadcn/ui
- [ ] Auth pages: login, register, forgot password
- [ ] JWT token storage (httpOnly cookies)
- [ ] Protected route guard
- [ ] Dashboard shell: sidebar + topbar layout

---

### Phase 2 — Agent Config & Widget (Week 3)

**Backend:**
- [ ] `GET/PUT /api/agent-config` endpoints
- [ ] Tone descriptions map
- [ ] Custom instructions length enforcement by plan
- [ ] `GET/PUT /api/widget/config` endpoints
- [ ] `GET/POST/DELETE /api/widget/domains` endpoints
- [ ] Domain validation logic (server-side on chat endpoint)
- [ ] `GET /api/widget/config` (public, Redis-cached)

**Frontend:**
- [ ] Agent Config page (bot name, company, tone dropdown, custom instructions, fallback)
- [ ] Plan-gate UI for custom instructions (disabled with tooltip on Free)
- [ ] Widget page (appearance config, embed code block, domain whitelist manager)
- [ ] Widget live preview (iframe)

**Widget:**
- [ ] `widget.js` base file (Shadow DOM, no dependencies)
- [ ] Floating button + chat panel HTML/CSS
- [ ] Config fetch on load
- [ ] Domain validation client-side
- [ ] `localStorage` session persistence
- [ ] Static file served from CDN path

---

### Phase 3 — Data Ingestion (Week 4–5)

**Backend:**
- [ ] MinIO client setup + bucket creation
- [ ] `POST /api/sources/url` — validate URL, check plan limits, queue job
- [ ] `POST /api/sources/upload` — validate type/size/count, save to MinIO, queue job
- [ ] `DELETE /api/sources/{id}` — delete from Milvus + MinIO + DB
- [ ] `POST /api/sources/{id}/retrain` — delete old vectors + re-queue
- [ ] Document parsers: PDF (`pymupdf`), DOCX (`python-docx`)
- [ ] Website scraper: `httpx` + `BeautifulSoup4` + `Playwright`
- [ ] Chunking service
- [ ] Embedding service (OpenAI batched)
- [ ] Milvus collection creation per client
- [ ] Full Celery training task with progress updates
- [ ] `GET /api/jobs` + `GET /api/jobs/{id}` endpoints

**Frontend:**
- [ ] Data Sources page (source table, status badges)
- [ ] Add Source modal: URL tab + File upload tab
- [ ] Plan limit bars on upload modal
- [ ] Training Jobs page with live polling
- [ ] Progress bar + stage message display
- [ ] Error expand panel

---

### Phase 4 — Chat Agent (Week 6–7)

**Backend:**
- [ ] Integrate existing LangGraph agent into FastAPI
- [ ] Wire `agent_config` (tone, instructions, fallback) into `execute_graph()`
- [ ] Plan-based tool activation in `get_agent_runnable()`
- [ ] `POST /api/chat/message` with SSE streaming
- [ ] Monthly message counter + limit enforcement
- [ ] Chat session creation/retrieval
- [ ] Chat message persistence to PostgreSQL
- [ ] Redis cache for recent messages per session
- [ ] Human handoff detection

**Widget:**
- [ ] SSE stream parsing in widget.js
- [ ] Progressive token rendering
- [ ] Typing indicator
- [ ] Error state display (limit reached, domain not allowed)
- [ ] Auto-scroll to latest message
- [ ] Mobile responsive layout

**Frontend:**
- [ ] Chat Logs page: session list
- [ ] Conversation detail view

---

### Phase 5 — Plans, Admin & Polish (Week 8–9)

**Backend:**
- [ ] Usage counter table + monthly reset Celery task
- [ ] `GET /api/clients/plan` — usage stats endpoint
- [ ] Super admin auth (separate JWT, IP whitelist)
- [ ] Admin API endpoints (clients list, detail, plan change, suspend)
- [ ] Stripe webhook handler (update plan on subscription event)

**Frontend:**
- [ ] Plan usage bars on Overview + Upload modal
- [ ] Upgrade CTA buttons throughout UI
- [ ] Settings page: profile edit, rotate key, account delete
- [ ] Super Admin panel: client table, client detail, platform stats

---

### Phase 6 — Production Hardening (Week 10)

- [ ] Rate limiting middleware (Redis-backed, all endpoints)
- [ ] CORS hardening (restrict non-chat endpoints to dashboard origin)
- [ ] Full Nginx config (routing + SSL via Let's Encrypt)
- [ ] Sentry error monitoring (backend + frontend)
- [ ] Structured JSON logging → log aggregator
- [ ] Celery dead-letter queue for failed jobs
- [ ] PostgreSQL automated daily backups
- [ ] Milvus snapshot strategy
- [ ] Load test: chat endpoint (locust), training job concurrency
- [ ] Security audit: SQL injection, XSS, SSRF (scraper URL validation)
- [ ] `robots.txt` compliance in scraper

---

## Appendix: Folder Structure

```
/cx-chatbot-platform
  /backend
    /app
      /routers
        auth.py
        sources.py
        jobs.py
        chat.py
        widget.py
        agent_config.py
        clients.py
        admin.py
      /models              ← SQLAlchemy ORM models
      /schemas             ← Pydantic request/response schemas
      /services
        plan_enforcer.py
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
          graph.py          ← existing LangGraph graph
          nodes.py          ← existing agent/tool/final nodes
          tools.py          ← existing 4 tools
          runnables.py
          state.py
          prompts.py
      /tasks
        training_tasks.py
        maintenance_tasks.py  ← monthly usage reset
      /core
        auth.py
        config.py
        database.py
        redis.py
        minio.py
    main.py
    celery_app.py
    requirements.txt

  /dashboard
    /app
      /auth
      /(protected)
        /overview
        /agent-config
        /data-sources
        /training
        /chat-logs
        /widget
        /settings
    /components
    /lib
    package.json

  /widget
    /src
      index.js
      ui.js
      api.js
      styles.js
    widget.js              ← built output (served from CDN)

  /admin
    /app                   ← Super admin Next.js app
    package.json

  /infra
    docker-compose.yml
    docker-compose.prod.yml
    /nginx
      nginx.conf
    /scripts
      init_milvus.py
      run_migrations.sh

  .env.example
  README.md
```

---

*CX Chatbot Platform Blueprint v2*
*Compatible with: LangGraph, FastAPI, Next.js 14, Milvus, PostgreSQL, Celery*
*Designed for use with AI coding tools: Claude Code, Cursor, Windsurf, GitHub Copilot Workspace*
