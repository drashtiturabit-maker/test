import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_session_key
from app.models import ChatMessage, ChatSession, Client


async def get_or_create_session(
    db: AsyncSession,
    client: Client,
    session_key: str | None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    page_url: str | None = None,
    force_new: bool = False,
) -> ChatSession:
    """Create a new session. Each widget page load gets a fresh session."""
    if not force_new and session_key:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.session_key == session_key,
                ChatSession.client_id == client.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    new_key = generate_session_key()
    session = ChatSession(
        client_id=client.id,
        session_key=new_key,
        ip_address=ip_address,
        user_agent=user_agent,
        page_url=page_url,
    )
    db.add(session)
    await db.flush()
    return session


async def save_message(
    db: AsyncSession,
    session: ChatSession,
    client_id: uuid.UUID,
    role: str,
    content: str,
    sources: list[str] | None = None,
    tokens_used: int | None = None,
    latency_ms: int | None = None,
):
    msg = ChatMessage(
        session_id=session.id,
        client_id=client_id,
        role=role,
        content=content,
        sources=sources,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )
    db.add(msg)
    session.message_count += 1
    session.last_message_at = datetime.now(timezone.utc)
    await db.flush()


async def get_recent_messages(db: AsyncSession, session_id: uuid.UUID, limit: int = 12) -> list[dict]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


async def get_client_by_key(db: AsyncSession, client_key: str) -> Client | None:
    result = await db.execute(
        select(Client).where(Client.client_key == client_key, Client.is_active == True)
    )
    return result.scalar_one_or_none()
