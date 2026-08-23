from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_internal_api_key(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("internal_api_key must not be blank")
    return normalized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str | None = None
    """선택 사항. 실행 경로는 PostgreSQL 아웃박스만 쓰므로 Redis가 없어도 주문이 나간다."""

    internal_api_key: str
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, allow_inf_nan=False)
    console_stub_enabled: bool = False

    mt5_enabled: bool = False
    mt5_terminal_path: str | None = None
    mt5_login: int | None = None
    mt5_password: SecretStr | None = None
    mt5_server: str | None = None

    mt5_submit_enabled: bool = False
    """섀도 모드 스위치. `False`면 `order_send`만 막고 나머지는 전부 실제로 돈다.

    실계좌에 붙이기 전 마지막 안전장치라 기본값이 꺼짐이다."""

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: int | None = None
    """알림을 받고 **버튼을 누를 수 있는 유일한 계정.**

    이 값을 비워 두면 텔레그램 기능 전체가 꺼진다. 채워 두면 이 id에서 온 콜백만
    받아들인다 — 없으면 봇을 찾은 누구나 실계좌 진입 버튼을 누를 수 있다."""

    @field_validator("internal_api_key")
    @classmethod
    def require_internal_api_key(cls, value: str) -> str:
        return validate_internal_api_key(value)

    @model_validator(mode="after")
    def require_mt5_before_submitting(self) -> "Settings":
        if self.mt5_submit_enabled and not self.mt5_enabled:
            raise ValueError("mt5_submit_enabled requires mt5_enabled")
        return self

    @model_validator(mode="after")
    def require_chat_id_with_token(self) -> "Settings":
        if self.telegram_bot_token is not None and self.telegram_chat_id is None:
            raise ValueError("telegram_bot_token requires telegram_chat_id to lock responses down")
        return self

    @property
    def telegram_enabled(self) -> bool:
        return self.telegram_bot_token is not None and self.telegram_chat_id is not None
