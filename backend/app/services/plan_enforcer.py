import re
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, DataSource


DOC_TYPES = {"pdf", "docx", "doc", "txt"}
URL_TYPES = {"url"}


class PlanEnforcer:
    @staticmethod
    async def count_sources(db: AsyncSession, client_id, source_type: str) -> int:
        q = select(func.count()).select_from(DataSource).where(
            DataSource.client_id == client_id,
            DataSource.type == source_type if source_type == "url" else DataSource.type.in_(DOC_TYPES),
        )
        if source_type != "url":
            q = select(func.count()).select_from(DataSource).where(
                DataSource.client_id == client_id,
                DataSource.type.in_(DOC_TYPES),
            )
        else:
            q = select(func.count()).select_from(DataSource).where(
                DataSource.client_id == client_id,
                DataSource.type == "url",
            )
        result = await db.execute(q)
        return result.scalar() or 0

    @staticmethod
    async def can_add_website(db: AsyncSession, client: Client) -> tuple[bool, str]:
        count = await PlanEnforcer.count_sources(db, client.id, "url")
        if count >= client.max_websites:
            return False, f"Maximum {client.max_websites} website(s) allowed for this client."
        return True, "OK"

    @staticmethod
    async def can_add_document(db: AsyncSession, client: Client) -> tuple[bool, str]:
        count = await PlanEnforcer.count_sources(db, client.id, "document")
        if count >= client.max_documents:
            return False, f"Maximum {client.max_documents} document(s) allowed for this client."
        return True, "OK"

    @staticmethod
    def validate_url(url: str) -> tuple[bool, str]:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False, "URL must start with http:// or https://"
            if not parsed.netloc:
                return False, "Invalid URL format."
            return True, "OK"
        except Exception:
            return False, "Invalid URL."

    @staticmethod
    def validate_domain(domain: str) -> tuple[bool, str]:
        domain = domain.strip().lower()
        if domain.startswith("http"):
            return False, "Enter hostname only, without http://"
        if not re.match(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)*$", domain):
            return False, "Invalid domain format."
        return True, domain

    @staticmethod
    def extract_domain_from_origin(origin: str) -> str:
        if not origin:
            return ""
        parsed = urlparse(origin if "://" in origin else f"https://{origin}")
        return parsed.hostname or ""
