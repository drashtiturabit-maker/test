import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import AgentConfig, AllowedDomain, Client, WidgetConfig
from app.routers.auth import get_current_admin
from app.schemas import AgentConfigResponse, AgentConfigUpdate, DomainCreate, WidgetConfigUpdate, WidgetPublicConfig

router = APIRouter(tags=["widget-config"])


@router.get("/widget/config", response_model=WidgetPublicConfig)
async def get_widget_config_public(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client, AgentConfig, WidgetConfig)
        .outerjoin(AgentConfig, AgentConfig.client_id == Client.id)
        .outerjoin(WidgetConfig, WidgetConfig.client_id == Client.id)
        .where(Client.client_key == key, Client.is_active == True)
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Client not found")
    client, agent_cfg, widget_cfg = row

    domains_result = await db.execute(select(AllowedDomain).where(AllowedDomain.client_id == client.id))
    domains = [d.domain for d in domains_result.scalars().all()]

    return WidgetPublicConfig(
        bot_name=agent_cfg.bot_name if agent_cfg else "Assistant",
        welcome_message=agent_cfg.welcome_message if agent_cfg else "Hi! How can I help?",
        primary_color=widget_cfg.primary_color if widget_cfg else "#4F46E5",
        enabled=widget_cfg.is_enabled if widget_cfg else True,
        show_branding=widget_cfg.show_branding if widget_cfg else True,
        allowed_domains=domains,
    )


admin_router = APIRouter(prefix="/admin/clients/{client_id}", tags=["admin-config"])


@admin_router.get("/agent-config", response_model=AgentConfigResponse)
async def get_agent_config(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Config not found")
    return cfg


@admin_router.put("/agent-config", response_model=AgentConfigResponse)
async def update_agent_config(
    client_id: uuid.UUID,
    payload: AgentConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(AgentConfig).where(AgentConfig.client_id == client_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Config not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    await db.flush()
    return cfg


@admin_router.get("/domains")
async def list_domains(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(AllowedDomain).where(AllowedDomain.client_id == client_id))
    return [{"id": str(d.id), "domain": d.domain} for d in result.scalars().all()]


@admin_router.post("/domains")
async def add_domain(
    client_id: uuid.UUID,
    payload: DomainCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    from app.services.plan_enforcer import PlanEnforcer
    ok, result = PlanEnforcer.validate_domain(payload.domain)
    if not ok:
        raise HTTPException(400, result)
    domain = AllowedDomain(client_id=client_id, domain=result)
    db.add(domain)
    await db.flush()
    return {"id": str(domain.id), "domain": domain.domain}


@admin_router.delete("/domains/{domain_id}")
async def remove_domain(
    client_id: uuid.UUID,
    domain_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(
        select(AllowedDomain).where(AllowedDomain.id == domain_id, AllowedDomain.client_id == client_id)
    )
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(404, "Domain not found")
    await db.delete(domain)
    return {"message": "Removed"}


@admin_router.put("/widget-config")
async def update_widget_config(
    client_id: uuid.UUID,
    payload: WidgetConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    result = await db.execute(select(WidgetConfig).where(WidgetConfig.client_id == client_id))
    cfg = result.scalar_one_or_none()
    if not cfg:
        raise HTTPException(404, "Widget config not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    await db.flush()
    return {"message": "Updated"}
