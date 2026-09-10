from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.models import AdminUser
from app.schemas import AdminLoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    try:
        from app.core.security import decode_token
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
        admin_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id, AdminUser.is_active == True))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Admin not found")
    return admin


@router.post("/login", response_model=TokenResponse)
async def login(payload: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).where(AdminUser.email == payload.email))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(str(admin.id), {"role": admin.role})
    return TokenResponse(access_token=token)


@router.post("/seed-admin")
async def seed_admin(db: AsyncSession = Depends(get_db)):
    """Create default admin if none exists. Disable in production."""
    result = await db.execute(select(AdminUser).limit(1))
    if result.scalar_one_or_none():
        return {"message": "Admin already exists"}
    admin = AdminUser(
        email="admin@trivighna.com",
        password_hash=hash_password("admin123"),
        full_name="Trivighna Admin",
        role="super_admin",
    )
    db.add(admin)
    await db.flush()
    return {"message": "Default admin created", "email": "admin@trivighna.com"}
