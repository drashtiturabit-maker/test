import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import TrainingJob
from app.routers.auth import get_current_admin
from app.schemas import TrainingJobResponse

router = APIRouter(prefix="/admin/clients/{client_id}/jobs", tags=["jobs"])


@router.get("", response_model=list[TrainingJobResponse])
async def list_jobs(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(
        select(TrainingJob)
        .where(TrainingJob.client_id == client_id)
        .order_by(TrainingJob.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=TrainingJobResponse)
async def get_job(
    client_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(
        select(TrainingJob).where(TrainingJob.id == job_id, TrainingJob.client_id == client_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    return job
