from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import admin, auth, chat, jobs, sources, widget

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.pinecone_store import vector_store
    try:
        vector_store.ensure_index()
    except Exception:
        pass
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(admin.router, prefix=settings.API_PREFIX)
app.include_router(sources.router, prefix=settings.API_PREFIX)
app.include_router(jobs.router, prefix=settings.API_PREFIX)
app.include_router(chat.router, prefix=settings.API_PREFIX)
app.include_router(widget.router, prefix=settings.API_PREFIX)
app.include_router(widget.admin_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "cx-backend"}
