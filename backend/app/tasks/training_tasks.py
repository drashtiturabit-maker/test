import asyncio
import logging
from datetime import datetime, timezone

import httpx
from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models import Client, DataSource, TrainingJob
from app.services.pinecone_store import vector_store

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery("cx_training", broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)
celery_app.conf.task_routes = {"app.tasks.training_tasks.run_training_job": {"queue": "training"}}

sync_engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", ""))
SyncSession = sessionmaker(sync_engine)


def _update_job(db: Session, job_id: str, **kwargs):
    job = db.get(TrainingJob, job_id)
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
        db.commit()


@celery_app.task(bind=True, max_retries=3)
def run_training_job(self, job_id: str, source_id: str, client_id: str):
    db = SyncSession()
    try:
        source = db.get(DataSource, source_id)
        client = db.get(Client, client_id)
        if not source or not client:
            return

        _update_job(db, job_id, status="scraping", progress=5, stage_message="Collecting data...", started_at=datetime.now(timezone.utc))
        source.status = "processing"
        db.commit()

        raw_chunks: list[tuple[str, str]] = []

        if source.type == "url":
            with httpx.Client(timeout=300) as http:
                resp = http.post(
                    f"{settings.SCRAPER_SERVICE_URL}/scrape",
                    json={"root_url": source.root_url, "max_depth": 2, "max_pages": 50},
                )
                resp.raise_for_status()
                pages = resp.json().get("pages", [])
                source.pages_scraped = len(pages)
                raw_chunks = [(p["url"], p["text"]) for p in pages if p.get("text")]
                _update_job(db, job_id, progress=35, stage_message=f"Scraped {len(pages)} pages")
        else:
            with httpx.Client(timeout=300) as http:
                resp = http.post(
                    f"{settings.TRAINING_SERVICE_URL}/parse",
                    json={"file_path": source.file_path, "file_type": source.type},
                )
                resp.raise_for_status()
                text = resp.json().get("text", "")
                raw_chunks = [(source.original_filename or source.name, text)]
                _update_job(db, job_id, progress=35, stage_message="Document parsed")

        _update_job(db, job_id, status="chunking", progress=45, stage_message="Chunking text...")

        with httpx.Client(timeout=300) as http:
            all_chunks = []
            for source_name, text in raw_chunks:
                resp = http.post(
                    f"{settings.TRAINING_SERVICE_URL}/chunk",
                    json={
                        "text": text,
                        "source_meta": {
                            "source_id": source_id,
                            "client_id": client_id,
                            "type": source.type,
                            "name": source_name,
                            "url": source_name if source.type == "url" else "",
                        },
                    },
                )
                resp.raise_for_status()
                all_chunks.extend(resp.json().get("chunks", []))

        _update_job(db, job_id, status="embedding", progress=60, stage_message=f"Embedding {len(all_chunks)} chunks...")

        vector_store.delete_by_source(client.pinecone_namespace, source_id)
        count = vector_store.upsert_chunks(client.pinecone_namespace, all_chunks)

        source.status = "trained"
        source.chunk_count = count
        source.last_trained_at = datetime.now(timezone.utc)
        source.error_message = None
        db.commit()

        _update_job(
            db, job_id,
            status="done", progress=100,
            stage_message="Training complete!",
            chunks_created=count,
            completed_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        logger.exception("Training failed: %s", exc)
        source = db.get(DataSource, source_id)
        if source:
            source.status = "failed"
            source.error_message = str(exc)
            db.commit()
        _update_job(db, job_id, status="failed", error_message=str(exc), completed_at=datetime.now(timezone.utc))
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
