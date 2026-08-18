from mtoss.config import Settings


def test_settings_accept_explicit_urls() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
        redis_url="redis://localhost:6379/0",
        internal_api_key="test-key",
    )
    assert settings.database_url.endswith("/mtoss")
    assert settings.redis_url.startswith("redis://")
