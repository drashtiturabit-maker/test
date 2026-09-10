import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import generate_client_key
from app.models import AgentConfig, Client, DataSource, WidgetConfig
from app.routers.auth import get_current_admin
from app.schemas import ClientCreate, ClientDetailResponse, ClientResponse

router = APIRouter(prefix="/admin/clients", tags=["admin-clients"])


def _namespace_from_id(client_id: uuid.UUID) -> str:
    return f"client_{str(client_id).replace('-', '_')}"


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(Client).order_by(Client.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    payload: ClientCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    client_id = uuid.uuid4()
    client = Client(
        id=client_id,
        company_name=payload.company_name,
        contact_email=payload.contact_email,
        client_key=generate_client_key(),
        pinecone_namespace=_namespace_from_id(client_id),
        max_websites=payload.max_websites,
        max_documents=payload.max_documents,
    )
    db.add(client)
    db.add(AgentConfig(client_id=client.id, company_name=payload.company_name))
    db.add(WidgetConfig(client_id=client.id))
    await db.flush()
    return client


@router.get("/{client_id}", response_model=ClientDetailResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    url_count = await db.execute(
        select(func.count()).select_from(DataSource).where(
            DataSource.client_id == client_id, DataSource.type == "url"
        )
    )
    doc_count = await db.execute(
        select(func.count()).select_from(DataSource).where(
            DataSource.client_id == client_id, DataSource.type.in_(["pdf", "docx", "doc", "txt"])
        )
    )
    chunk_sum = await db.execute(
        select(func.coalesce(func.sum(DataSource.chunk_count), 0)).where(DataSource.client_id == client_id)
    )

    return ClientDetailResponse(
        id=client.id,
        company_name=client.company_name,
        contact_email=client.contact_email,
        client_key=client.client_key,
        pinecone_namespace=client.pinecone_namespace,
        is_active=client.is_active,
        max_websites=client.max_websites,
        max_documents=client.max_documents,
        created_at=client.created_at,
        website_count=url_count.scalar() or 0,
        document_count=doc_count.scalar() or 0,
        chunk_count=chunk_sum.scalar() or 0,
    )


@router.delete("/{client_id}")
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    from app.services.pinecone_store import vector_store

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")
    vector_store.delete_namespace(client.pinecone_namespace)
    await db.delete(client)
    return {"message": "Client deleted"}
