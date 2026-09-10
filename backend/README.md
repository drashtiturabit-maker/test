# Backend API Service

FastAPI application serving the CX Chatbot Platform.

## Structure

```
backend/app/
├── main.py              # FastAPI app entry
├── core/
│   ├── config.py        # Settings from .env
│   ├── database.py      # Async SQLAlchemy
│   └── security.py      # JWT, passwords, keys
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response
├── routers/
│   ├── auth.py          # Admin authentication
│   ├── admin.py         # Client CRUD
│   ├── sources.py       # Data source upload/URL
│   ├── jobs.py          # Training job status
│   ├── chat.py          # Chat SSE + sessions
│   └── widget.py        # Widget config (public + admin)
├── services/
│   ├── pinecone_store.py   # Vector DB operations
│   ├── plan_enforcer.py    # 3 websites / 5 docs limits
│   └── session_manager.py  # Chat session handling
├── agent/               # LangGraph CX agent (see agent/README.md)
└── tasks/
    └── training_tasks.py   # Celery training pipeline
```

## Run

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Celery Worker

```bash
celery -A app.tasks.training_tasks.celery_app worker -Q training -l info
```

## Key Endpoints

- `GET /health` — Health check
- `POST /api/auth/login` — Admin login
- `POST /api/chat/message` — SSE chat stream
- `GET /api/widget/config?key=...` — Public widget config
