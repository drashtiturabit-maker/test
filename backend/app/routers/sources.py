import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Client, DataSource, TrainingJob
from app.routers.auth import get_current_admin
from app.schemas import DataSourceResponse, TrainingJobResponse, UrlSourceCreate
from app.services.plan_enforcer import PlanEnforcer
from app.tasks.training_tasks import run_training_job

router = APIRouter(prefix="/admin/clients/{client_id}/sources", tags=["sources"])
settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


@router.get("", response_model=list[DataSourceResponse])
async def list_sources(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(
        select(DataSource).where(DataSource.client_id == client_id).order_by(DataSource.created_at.desc())
    )
    return result.scalars().all()


@router.post("/url", response_model=dict)
async def add_url_source(
    client_id: uuid.UUID,
    payload: UrlSourceCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    ok, msg = PlanEnforcer.validate_url(payload.root_url)
    if not ok:
        raise HTTPException(400, msg)

    can, reason = await PlanEnforcer.can_add_website(db, client)
    if not can:
        raise HTTPException(402, reason)

    source = DataSource(
        client_id=client_id,
        name=payload.name,
        type="url",
        root_url=payload.root_url,
        status="pending",
    )
    db.add(source)
    await db.flush()

    job = TrainingJob(client_id=client_id, source_id=source.id, status="queued")
    db.add(job)
    await db.flush()

    run_training_job.delay(str(job.id), str(source.id), str(client_id))

    return {"source_id": str(source.id), "job_id": str(job.id), "status": "queued"}


@router.post("/upload", response_model=dict)
async def upload_document(
    client_id: uuid.UUID,
    name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client not found")

    can, reason = await PlanEnforcer.can_add_document(db, client)
    if not can:
        raise HTTPException(402, reason)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "File exceeds 25MB limit")

    upload_dir = Path(settings.UPLOAD_DIR) / str(client_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4()
    file_path = upload_dir / f"{file_id}{ext}"

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    doc_type = ext.lstrip(".")
    if doc_type == "doc":
        doc_type = "doc"

    source = DataSource(
        client_id=client_id,
        name=name,
        type=doc_type,
        file_path=str(file_path),
        file_size_bytes=len(content),
        original_filename=file.filename,
        status="pending",
    )
    db.add(source)
    await db.flush()

    job = TrainingJob(client_id=client_id, source_id=source.id, status="queued")
    db.add(job)
    await db.flush()

    run_training_job.delay(str(job.id), str(source.id), str(client_id))

    return {
        "source_id": str(source.id),
        "job_id": str(job.id),
        "status": "queued",
        "filename": file.filename,
    }


@router.delete("/{source_id}")
async def delete_source(
    client_id: uuid.UUID,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    from app.services.pinecone_store import vector_store

    result = await db.execute(
        select(DataSource, Client)
        .join(Client, Client.id == DataSource.client_id)
        .where(DataSource.id == source_id, DataSource.client_id == client_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Source not found")
    source, client = row

    vector_store.delete_by_source(client.pinecone_namespace, str(source_id))
    if source.file_path and os.path.exists(source.file_path):
        os.remove(source.file_path)
    await db.delete(source)
    return {"message": "Source deleted"}


@router.post("/{source_id}/retrain")
async def retrain_source(
    client_id: uuid.UUID,
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    from app.services.pinecone_store import vector_store

    result = await db.execute(
        select(DataSource, Client)
        .join(Client, Client.id == DataSource.client_id)
        .where(DataSource.id == source_id, DataSource.client_id == client_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Source not found")
    source, client = row

    vector_store.delete_by_source(client.pinecone_namespace, str(source_id))
    source.status = "pending"
    job = TrainingJob(client_id=client_id, source_id=source.id, status="queued")
    db.add(job)
    await db.flush()
    run_training_job.delay(str(job.id), str(source.id), str(client_id))
    return {"job_id": str(job.id), "status": "queued"}
