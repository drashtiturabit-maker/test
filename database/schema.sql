-- CX Chatbot Platform — PostgreSQL Schema
-- Multi-tenant B2B: Trivighna (platform) manages client companies

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Platform admin users (Trivighna staff)
CREATE TABLE admin_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(32) DEFAULT 'admin',  -- admin | super_admin
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- B2B client companies (Company A, Company B, ...)
CREATE TABLE clients (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name        VARCHAR(255) NOT NULL,
    contact_email       VARCHAR(255),
    client_key          VARCHAR(64) UNIQUE NOT NULL,
    pinecone_namespace  VARCHAR(128) UNIQUE NOT NULL,
    plan                VARCHAR(32) DEFAULT 'standard',
    is_active           BOOLEAN DEFAULT TRUE,
    max_websites        INT DEFAULT 3,
    max_documents       INT DEFAULT 5,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_clients_key ON clients(client_key);
CREATE INDEX idx_clients_namespace ON clients(pinecone_namespace);

-- Agent behavior per client
CREATE TABLE agent_configs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id            UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    bot_name             VARCHAR(100) DEFAULT 'Assistant',
    company_name         VARCHAR(255),
    tone                 VARCHAR(32) DEFAULT 'professional',
    custom_instructions  TEXT DEFAULT '',
    fallback_message     TEXT DEFAULT 'I don''t have that information right now. Would you like to connect with our team?',
    welcome_message      TEXT DEFAULT 'Hi! How can I help you today?',
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Widget appearance + embed settings
CREATE TABLE widget_configs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         UUID UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    primary_color     VARCHAR(16) DEFAULT '#4F46E5',
    is_enabled        BOOLEAN DEFAULT TRUE,
    show_branding     BOOLEAN DEFAULT TRUE,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Domains allowed to embed widget
CREATE TABLE allowed_domains (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    domain      VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, domain)
);
CREATE INDEX idx_allowed_domains_client ON allowed_domains(client_id);

-- Training data sources (websites + documents)
CREATE TABLE data_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id           UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    type                VARCHAR(16) NOT NULL,          -- url | pdf | docx | doc | txt
    status              VARCHAR(32) DEFAULT 'pending', -- pending|processing|trained|failed
    root_url            VARCHAR(2048),
    scrape_config       JSONB DEFAULT '{}',
    pages_scraped       INT DEFAULT 0,
    file_path           VARCHAR(512),
    file_size_bytes     BIGINT,
    original_filename   VARCHAR(255),
    chunk_count         INT DEFAULT 0,
    last_trained_at     TIMESTAMPTZ,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_data_sources_client ON data_sources(client_id);

-- Async training jobs
CREATE TABLE training_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    source_id       UUID NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    status          VARCHAR(32) DEFAULT 'queued',
    progress        INT DEFAULT 0,
    stage_message   VARCHAR(255),
    chunks_created  INT DEFAULT 0,
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_training_jobs_client ON training_jobs(client_id);

-- Chat sessions (new session per widget load)
CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    session_key     VARCHAR(128) UNIQUE NOT NULL,
    ip_address      INET,
    user_agent      TEXT,
    page_url        VARCHAR(2048),
    message_count   INT DEFAULT 0,
    last_message_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sessions_client ON chat_sessions(client_id);
CREATE INDEX idx_sessions_key ON chat_sessions(session_key);

-- Individual chat messages
CREATE TABLE chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    role        VARCHAR(16) NOT NULL,
    content     TEXT NOT NULL,
    sources     TEXT[],
    tokens_used INT,
    latency_ms  INT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_messages_session ON chat_messages(session_id);

-- Lead capture from chatbot
CREATE TABLE leads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES chat_sessions(id) ON DELETE SET NULL,
    name            VARCHAR(255),
    email           VARCHAR(255),
    company_name    VARCHAR(255),
    mobile_no       VARCHAR(64),
    intents         TEXT[],
    raw_payload     JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_leads_client ON leads(client_id);

-- Admin refresh tokens
CREATE TABLE admin_refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id    UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Monthly usage tracking
CREATE TABLE usage_counters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    month_year  VARCHAR(7) NOT NULL,
    msg_count   INT DEFAULT 0,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, month_year)
);
