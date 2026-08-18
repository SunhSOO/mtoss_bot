# mtoss_bot

Broker-independent execution core for the MT5 and Toss Securities trading platform.
The current phase is deliberately limited to `FakeBroker`: there are no MT5 or Toss broker
adapters, real-broker endpoints, or live order calls.

## Requirements

- Python 3.12 and `uv`
- Docker with Docker Compose for local PostgreSQL 16 and Redis

Docker is required for migrations and integration tests. Unit and API tests use local test
doubles and can run without the containers.

## Local start

1. Copy `.env.example` to `.env` and replace `INTERNAL_API_KEY` with a local secret.
2. Start the dependencies: `docker compose up -d db redis`.
3. Install the locked dependencies: `uv sync --all-groups --locked`.
4. Apply the database migration: `uv run alembic upgrade head`.
5. Start the API: `uv run uvicorn mtoss.api.app:create_app --factory --reload`.

Keep the local URLs from `.env.example` unless Docker is exposed elsewhere. The `.env` file is
ignored by Git and must not contain real broker credentials.

## Checks

With PostgreSQL and Redis running and the migration applied, run the complete suite:

```shell
uv run pytest tests -v
```

The individual checks used by CI are:

```shell
uv run pytest tests/integration -v
uv run pytest tests/unit tests/api -v
uv run ruff check .
uv run mypy src/mtoss
```

## Migration verification

Use the explicitly named disposable database below. It is separate from the `mtoss` development
database and is the only database these commands drop.

For Bash:

```bash
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
docker compose exec -T db createdb -U mtoss mtoss_ci_verify
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run alembic upgrade head
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run alembic downgrade base
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run alembic upgrade head
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
```

For PowerShell:

```powershell
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
docker compose exec -T db createdb -U mtoss mtoss_ci_verify
$env:DATABASE_URL = "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify"
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
Remove-Item Env:DATABASE_URL
```

## Stop

Run `docker compose down`. Add `-v` only when intentionally deleting local database data.

## Safety

This phase contains only `FakeBroker`; it cannot place real orders. Do not configure, store, or
commit real broker credentials. An order in `UNKNOWN` has an indeterminate broker outcome and must
be reconciled manually; never automatically retry or resubmit it.
