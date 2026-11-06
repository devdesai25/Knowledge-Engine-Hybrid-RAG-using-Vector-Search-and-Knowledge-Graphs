from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict, BaseSettings

class Settings(BaseSettings):
    hf_token: str
    QDRANT_URL: str
    QDRANT_API_KEY: str
    gemini_api_key: SecretStr
    neo4j_db_uri: str
    neo4j_username: str
    neo4j_password: SecretStr
    supabase_uri: str
    expire_minutes: int
    secret_key: str
    secret_algorithm: str
    deepseek_api_key: SecretStr
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

setting = Settings()