# Scraper Service

Website crawling microservice for the CX RAG pipeline.

## Endpoints

- `POST /scrape` — Crawl a website and return extracted text per page
- `GET /health` — Health check

## Run

```bash
cd scraper-service
pip install -r requirements.txt
uvicorn app.main:app --port 8001
```

## Request Example

```json
{
  "root_url": "https://example.com",
  "max_depth": 2,
  "max_pages": 50
}
```
