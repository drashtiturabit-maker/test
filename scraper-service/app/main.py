import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="CX Scraper Service")


class ScrapeRequest(BaseModel):
    root_url: str
    max_depth: int = 2
    max_pages: int = 50


class PageResult(BaseModel):
    url: str
    text: str
    depth: int


def get_domain(url: str) -> str:
    return urlparse(url).netloc


def normalize_url(base: str, link: str) -> str | None:
    full = urljoin(base, link)
    parsed = urlparse(full)
    if parsed.scheme not in ("http", "https"):
        return None
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/') or '/'}"
    if parsed.query:
        clean += f"?{parsed.query}"
    return clean


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["nav", "footer", "header", "script", "style", "aside", "form", "iframe", "noscript"]):
        tag.decompose()
    blocks = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote", "article"]):
        t = tag.get_text(" ", strip=True)
        if len(t) > 30:
            blocks.append(t)
    return "\n\n".join(blocks)


def extract_links(html: str, base_url: str, base_domain: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full = normalize_url(base_url, href)
        if full and urlparse(full).netloc == base_domain:
            links.add(full)
    return list(links)


async def scrape_website(root_url: str, max_depth: int, max_pages: int) -> list[dict]:
    visited: set[str] = set()
    results: list[dict] = []
    queue: list[tuple[str, int]] = [(root_url, 0)]
    base_domain = get_domain(root_url)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": "CXBot/1.0"}) as client:
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)
            try:
                resp = await client.get(url)
                if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                    continue
                text = extract_text(resp.text)
                if text.strip():
                    results.append({"url": url, "text": text, "depth": depth})
                if depth < max_depth:
                    for link in extract_links(resp.text, url, base_domain):
                        if link not in visited:
                            queue.append((link, depth + 1))
            except Exception:
                continue
    return results


@app.post("/scrape")
async def scrape(payload: ScrapeRequest):
    pages = await scrape_website(payload.root_url, payload.max_depth, payload.max_pages)
    return {"pages": pages, "total": len(pages)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "scraper"}
