from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CX Chatbot Platform"
    API_PREFIX: str = "/api"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://cx_user:cx_pass@localhost:5432/cx_chatbot"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = "change-me-in-production-use-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 30

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536

    PINECONE_API_KEY: str = ""
    PINECONE_INDEX_NAME: str = "cx-chatbot"
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"

    SCRAPER_SERVICE_URL: str = "http://localhost:8001"
    TRAINING_SERVICE_URL: str = "http://localhost:8002"

    UPLOAD_DIR: str = "./uploads"
    MAX_WEBSITES_DEFAULT: int = 3
    MAX_DOCUMENTS_DEFAULT: int = 5

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
