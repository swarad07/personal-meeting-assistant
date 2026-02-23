from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meeting_assistant"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_max_concurrent: int = 3
    openai_daily_token_budget: int = 500_000

    granola_cache_path: str = "~/Library/Application Support/Granola/cache-v3.json"
    granola_mcp_url: str = "https://mcp.granola.ai/mcp"
    gcal_mcp_url: str = "http://gcal-mcp:8100"

    google_client_id: str = ""
    google_client_secret: str = ""

    primary_user_email: str = ""
    primary_user_name: str = ""

    sync_batch_size: int = 10
    sync_interval_minutes: int = 15
    encryption_key: str = "change-me-in-production-32bytes!"

    model_config = {"env_file": ["../.env", ".env"], "extra": "ignore"}


settings = Settings()
