# Training Service

Document parsing and text chunking for the RAG pipeline.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /parse` | Extract text from PDF, DOCX, DOC, TXT |
| `POST /chunk` | Split text into overlapping chunks with metadata |
| `GET /health` | Health check |

## Run

```bash
cd training-service
pip install -r requirements.txt
uvicorn app.main:app --port 8002
```

## Pipeline Flow

```
Document file → /parse → raw text → /chunk → chunk list → Pinecone upsert
```
