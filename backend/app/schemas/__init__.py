from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──────────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Clients ───────────────────────────────────────────────────────────────

class ClientCreate(BaseModel):
    company_name: str
    contact_email: Optional[EmailStr] = None
    max_websites: int = 3
    max_documents: int = 5


class ClientResponse(BaseModel):
    id: UUID
    company_name: str
    contact_email: Optional[str]
    client_key: str
    pinecone_namespace: str
    is_active: bool
    max_websites: int
    max_documents: int
    created_at: datetime

    class Config:
        from_attributes = True


class ClientDetailResponse(ClientResponse):
    website_count: int = 0
    document_count: int = 0
    chunk_count: int = 0


# ── Agent Config ──────────────────────────────────────────────────────────

class AgentConfigUpdate(BaseModel):
    bot_name: Optional[str] = None
    company_name: Optional[str] = None
    tone: Optional[str] = None
    custom_instructions: Optional[str] = None
    fallback_message: Optional[str] = None
    welcome_message: Optional[str] = None


class AgentConfigResponse(BaseModel):
    bot_name: str
    company_name: Optional[str]
    tone: str
    custom_instructions: str
    fallback_message: str
    welcome_message: str

    class Config:
        from_attributes = True


# ── Data Sources ──────────────────────────────────────────────────────────

class UrlSourceCreate(BaseModel):
    name: str
    root_url: str


class DataSourceResponse(BaseModel):
    id: UUID
    name: str
    type: str
    status: str
    root_url: Optional[str]
    original_filename: Optional[str]
    pages_scraped: int
    chunk_count: int
    last_trained_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Training Jobs ─────────────────────────────────────────────────────────

class TrainingJobResponse(BaseModel):
    id: UUID
    source_id: UUID
    status: str
    progress: int
    stage_message: Optional[str]
    chunks_created: int
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Widget ────────────────────────────────────────────────────────────────

class WidgetConfigUpdate(BaseModel):
    primary_color: Optional[str] = None
    is_enabled: Optional[bool] = None
    show_branding: Optional[bool] = None


class WidgetPublicConfig(BaseModel):
    bot_name: str
    welcome_message: str
    primary_color: str
    enabled: bool
    show_branding: bool
    allowed_domains: list[str]


class DomainCreate(BaseModel):
    domain: str


# ── Chat ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    client_key: str
    session_id: Optional[str] = None
    message: str
    page_url: Optional[str] = None


class SessionCreateResponse(BaseModel):
    session_id: str


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    sources: Optional[list[str]] = None
    created_at: datetime

    class Config:
        from_attributes = True
