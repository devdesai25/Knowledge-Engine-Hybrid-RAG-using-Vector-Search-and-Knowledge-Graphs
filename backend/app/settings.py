from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict, BaseSettings

class Settings(BaseSettings):
    hf_token: str
    QDRANT_URL: str
    QDRANT_API_KEY: str
    gemini_api_key: SecretStr

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

setting = Settings()