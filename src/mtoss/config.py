from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_internal_api_key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("internal_api_key must not be blank")
    return normalized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    internal_api_key: str
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, allow_inf_nan=False)

    @field_validator("internal_api_key")
    @classmethod
    def require_internal_api_key(cls, value: str) -> str:
        return validate_internal_api_key(value)
