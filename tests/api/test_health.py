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
