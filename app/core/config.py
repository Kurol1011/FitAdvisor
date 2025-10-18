from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@db:5432/fitadvisor"
    OPENAI_API_KEY: str | None = None
    VECTOR_BACKEND: str = "faiss"  # or chroma
    class Config:
        env_file = '.env'

settings = Settings()