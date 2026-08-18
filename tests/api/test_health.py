import asyncio
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

import mtoss.api.app as app_module
from mtoss.api.app import create_app
from mtoss.config import Settings


def test_liveness(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_fails_closed_when_real_dependencies_are_absent(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "dependencies unavailable"}


def test_readiness_timeout_defaults_to_two_seconds(settings: Settings) -> None:
    assert settings.readiness_timeout_seconds == 2.0


@pytest.mark.parametrize("slow_probe", ["database", "redis"])
def test_readiness_times_out_each_hanging_probe(
    monkeypatch,
    settings: Settings,
    slow_probe: str,
) -> None:
    class FakeEngine:
        async def dispose(self) -> None:
            pass

    class FakeSession:
        async def execute(self, _statement: object) -> None:
            if slow_probe == "database":
                await asyncio.sleep(0.2)

    class FakeSessionFactory:
        def __init__(self) -> None:
            self.kw = {"bind": FakeEngine()}

        def __call__(self) -> "FakeSessionFactory":
            return self

        async def __aenter__(self) -> FakeSession:
            return FakeSession()

        async def __aexit__(self, *_args: object) -> None:
            pass

    class FakeRedis:
        async def ping(self) -> bool:
            if slow_probe == "redis":
                await asyncio.sleep(0.2)
            return True

        async def aclose(self) -> None:
            pass

    monkeypatch.setattr(app_module, "create_session_factory", lambda _url: FakeSessionFactory())
    monkeypatch.setattr(app_module.Redis, "from_url", lambda *_args, **_kwargs: FakeRedis())
    short_timeout = settings.model_copy(update={"readiness_timeout_seconds": 0.01})

    started = perf_counter()
    with TestClient(create_app(short_timeout)) as test_client:
        response = test_client.get("/health/ready")
    elapsed = perf_counter() - started

    assert response.status_code == 503
    assert response.json() == {"detail": "dependencies unavailable"}
    assert elapsed < 0.5


def test_app_lifespan_closes_redis_and_database_engine(
    monkeypatch, settings: Settings
) -> None:
    class FakeEngine:
        def __init__(self) -> None:
            self.disposed = False

        async def dispose(self) -> None:
            self.disposed = True

    class FakeSessionFactory:
        def __init__(self, engine: FakeEngine) -> None:
            self.kw = {"bind": engine}

    class FakeRedis:
        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    engine = FakeEngine()
    redis = FakeRedis()
    factory = FakeSessionFactory(engine)
    monkeypatch.setattr(app_module, "create_session_factory", lambda _url: factory)

    def from_url(*_args: object, **_kwargs: object) -> FakeRedis:
        return redis

    monkeypatch.setattr(app_module.Redis, "from_url", from_url)

    with TestClient(create_app(settings)):
        assert not engine.disposed
        assert not redis.closed

    assert engine.disposed
    assert redis.closed
