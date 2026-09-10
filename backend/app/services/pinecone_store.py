import logging
from typing import Any

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PineconeVectorStore:
    """Pinecone vector store with per-client namespace isolation."""

    def __init__(self):
        self._pc: Pinecone | None = None
        self._index = None
        self._openai = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    def _ensure_client(self):
        if self._pc is None and settings.PINECONE_API_KEY:
            self._pc = Pinecone(api_key=settings.PINECONE_API_KEY)

    def ensure_index(self):
        self._ensure_client()
        if not self._pc:
            logger.warning("Pinecone not configured")
            return
        existing = [idx.name for idx in self._pc.list_indexes()]
        if settings.PINECONE_INDEX_NAME not in existing:
            self._pc.create_index(
                name=settings.PINECONE_INDEX_NAME,
                dimension=settings.EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud=settings.PINECONE_CLOUD, region=settings.PINECONE_REGION),
            )
        self._index = self._pc.Index(settings.PINECONE_INDEX_NAME)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not self._openai:
            raise RuntimeError("OpenAI API key not configured")
        response = self._openai.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]

    def upsert_chunks(self, namespace: str, chunks: list[dict[str, Any]]) -> int:
        self.ensure_index()
        if not self._index or not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self.embed_texts(texts)

        vectors = []
        for chunk, embedding in zip(chunks, embeddings):
            vectors.append({
                "id": chunk["chunk_id"],
                "values": embedding,
                "metadata": {
                    "client_id": chunk["client_id"],
                    "source_id": chunk["source_id"],
                    "source_type": chunk["source_type"],
                    "source_name": chunk["source_name"],
                    "source_url": chunk.get("source_url", ""),
                    "text": chunk["text"][:3500],
                    "chunk_index": chunk["chunk_index"],
                },
            })

        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            self._index.upsert(vectors=vectors[i : i + batch_size], namespace=namespace)
        return len(vectors)

    def query(self, namespace: str, query_text: str, top_k: int = 5) -> list[dict]:
        self.ensure_index()
        if not self._index:
            return []

        embedding = self.embed_query(query_text)
        results = self._index.query(
            vector=embedding,
            namespace=namespace,
            top_k=top_k,
            include_metadata=True,
        )
        matches = []
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            matches.append({
                "chunk_id": match.get("id"),
                "score": match.get("score", 0),
                "text": meta.get("text", ""),
                "source_url": meta.get("source_url", ""),
                "source_name": meta.get("source_name", ""),
            })
        return matches

    def delete_by_source(self, namespace: str, source_id: str):
        self.ensure_index()
        if not self._index:
            return
        self._index.delete(filter={"source_id": source_id}, namespace=namespace)

    def delete_namespace(self, namespace: str):
        self.ensure_index()
        if not self._index:
            return
        self._index.delete(delete_all=True, namespace=namespace)


vector_store = PineconeVectorStore()
