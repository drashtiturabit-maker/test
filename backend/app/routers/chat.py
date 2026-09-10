import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.executor import stream_agent_response
from app.core.database import get_db
from app.core.security import generate_session_key
from app.models import AgentConfig, AllowedDomain, ChatSession, Client
from app.schemas import ChatRequest, SessionCreateResponse
from app.services.plan_enforcer import PlanEnforcer
from app.services.session_manager import get_client_by_key, get_or_create_session, get_recent_messages, save_message

router = APIRouter(prefix="/chat", tags=["chat"])


async def _validate_domain(db: AsyncSession, client: Client, request: Request):
    origin = request.headers.get("origin") or request.headers.get("referer", "")
    domain = PlanEnforcer.extract_domain_from_origin(origin)
    if not domain:
        return
    result = await db.execute(select(AllowedDomain).where(AllowedDomain.client_id == client.id))
    allowed = [d.domain for d in result.scalars().all()]
    if allowed and domain not in allowed and "localhost" not in domain:
        raise HTTPException(403, "Domain not authorized for this client key.")


@router.post("/session", response_model=SessionCreateResponse)
async def create_session(
    client_key: str = Query(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session. Called on each widget page load (including refresh)."""
    client = await get_client_by_key(db, client_key)
    if not client:
        raise HTTPException(404, "Invalid client key")
    await _validate_domain(db, client, request)

    session = await get_or_create_session(
        db,
        client,
        session_key=None,
        force_new=True,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return SessionCreateResponse(session_id=session.session_key)


@router.post("/message")
async def chat_message(
    payload: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client = await get_client_by_key(db, payload.client_key)
    if not client:
        raise HTTPException(404, "Invalid client key")
    await _validate_domain(db, client, request)

    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client.id))
    agent_config = result.scalar_one_or_none()
    if not agent_config:
        raise HTTPException(500, "Agent not configured")

    session = await get_or_create_session(
        db,
        client,
        payload.session_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        page_url=payload.page_url,
    )

    history = await get_recent_messages(db, session.id, limit=10)
    config_dict = {
        "bot_name": agent_config.bot_name,
        "company_name": agent_config.company_name or client.company_name,
        "tone": agent_config.tone,
        "custom_instructions": agent_config.custom_instructions,
        "fallback_message": agent_config.fallback_message,
    }

    await save_message(db, session, client.id, "user", payload.message)
    await db.commit()

    session_key = session.session_key
    session_uuid = session.id
    client_uuid = client.id

    async def event_stream():
        import json
        full_response = ""
        sources = []
        async for chunk in stream_agent_response(
            query=payload.message,
            thread_id=session_key,
            client_key=client.client_key,
            agent_config=config_dict,
            pinecone_namespace=client.pinecone_namespace,
            chat_history=history,
        ):
            data = json.loads(chunk.strip())
            if data.get("type") == "token":
                full_response += data.get("content", "")
            elif data.get("type") == "done":
                sources = data.get("sources", [])
            yield f"data: {chunk.strip()}\n\n"

        if full_response:
            from app.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as save_db:
                sess = await save_db.get(ChatSession, session_uuid)
                if sess:
                    await save_message(save_db, sess, client_uuid, "assistant", full_response, sources=sources)
                    await save_db.commit()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
