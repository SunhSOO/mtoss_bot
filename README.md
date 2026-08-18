# mtoss_bot

Broker-independent execution core for the MT5 and Toss Securities trading platform.
The current phase is deliberately limited to `FakeBroker`: there are no MT5 or Toss broker
adapters, real-broker endpoints, or live order calls.

## Requirements

- Python 3.12 and `uv`
- Docker with a Docker Compose version that supports `--wait`, for local PostgreSQL 16 and Redis

Docker is required for migrations and integration tests. Unit and API tests use local test
doubles and can run without the containers.

## Local start

1. Copy `.env.example` to `.env` and replace `INTERNAL_API_KEY` with a local secret.
2. Start the dependencies and wait for their health checks:
   `docker compose up -d --wait db redis`.
3. Install the locked dependencies: `uv sync --all-groups --locked`.
4. Apply the database migration: `uv run --env-file .env alembic upgrade head`.
5. Start the API:
   `uv run --env-file .env uvicorn mtoss.api.app:create_app --factory --reload`.

Keep the local URLs from `.env.example` unless Docker is exposed elsewhere. The `.env` file is
ignored by Git and must not contain real broker credentials.

## Checks

With PostgreSQL and Redis running and the migration applied, run the complete suite:

```shell
uv run --env-file .env pytest tests -v
```

The individual checks used by CI are:

```shell
uv run --env-file .env pytest tests/integration -v
uv run --env-file .env pytest tests/unit tests/api -v
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
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run --env-file .env alembic upgrade head
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run --env-file .env alembic downgrade base
DATABASE_URL=postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify uv run --env-file .env alembic upgrade head
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
```

For PowerShell:

```powershell
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
docker compose exec -T db createdb -U mtoss mtoss_ci_verify
$env:DATABASE_URL = "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss_ci_verify"
uv run --env-file .env alembic upgrade head
uv run --env-file .env alembic downgrade base
uv run --env-file .env alembic upgrade head
docker compose exec -T db dropdb -U mtoss --if-exists mtoss_ci_verify
Remove-Item Env:DATABASE_URL
```

The disposable database mtoss_ci_verify contains no retained data: it exists only for this
migration check and is dropped intentionally when the round-trip finishes.

## Backup and recovery

Create a host-side backup before any operation that may remove the database volume. The `backups/`
directory is ignored by Git; protect and retain its contents separately if the local data matters.
Create it first with `mkdir -p backups` in Bash or
`New-Item -ItemType Directory -Force backups | Out-Null` in PowerShell.

```shell
docker compose exec -T db pg_dump -U mtoss -d mtoss --format=custom --file=/tmp/mtoss.dump
docker compose cp db:/tmp/mtoss.dump ./backups/mtoss.dump
docker compose exec -T db rm -f /tmp/mtoss.dump
```

To recover a fresh or existing local database, stop the API, start healthy dependencies, and
restore the dump. `pg_restore --clean` replaces the current local `mtoss` schema and data.

```shell
docker compose up -d --wait db redis
docker compose cp ./backups/mtoss.dump db:/tmp/mtoss.dump
docker compose exec -T db pg_restore -U mtoss -d mtoss --clean --if-exists --exit-on-error /tmp/mtoss.dump
docker compose exec -T db rm -f /tmp/mtoss.dump
uv run --env-file .env alembic upgrade head
```

## Stop and volume safety

Normal `docker compose down` stops and removes the containers but preserves the named
`postgres_data` volume, so the local database is available on the next startup. Running
`docker compose down -v` permanently deletes the local database volume; without a host-side backup,
that data cannot be restored. Use `-v` only for an intentional reset or after verifying the backup
and recovery procedure above.

## Safety

This phase contains only `FakeBroker`; it cannot place real orders. Do not configure, store, or
commit real broker credentials. An order in `UNKNOWN` has an indeterminate broker outcome and must
be reconciled manually; never automatically retry or resubmit it.
