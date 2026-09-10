# Database Schema

PostgreSQL 15+ schema for the CX Chatbot B2B platform.

## Overview

| Table | Purpose |
|---|---|
| `admin_users` | Trivighna platform operators |
| `clients` | B2B tenant companies (each gets `client_key` + Pinecone namespace) |
| `agent_configs` | Bot name, tone, instructions per client |
| `widget_configs` | Widget colors, enable/disable |
| `allowed_domains` | Domains authorized to embed the chat widget |
| `data_sources` | Websites (max 3) and documents (max 5) per client |
| `training_jobs` | Async RAG training pipeline status |
| `chat_sessions` | One session per widget page load |
| `chat_messages` | Conversation history |
| `leads` | Captured lead information |
| `usage_counters` | Monthly message counts |

## Apply Schema

```bash
psql -U cx_user -d cx_chatbot -f database/schema.sql
```

## Multi-Tenant Isolation

- Every `client_id` foreign key scopes data to one company.
- `clients.pinecone_namespace` maps 1:1 to a Pinecone namespace.
- `clients.client_key` is the public embed key used by the webchat widget.

## Limits (enforced in application layer)

- `max_websites`: default 3
- `max_documents`: default 5
