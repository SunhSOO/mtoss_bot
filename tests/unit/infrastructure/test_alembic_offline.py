from io import StringIO

from alembic.config import Config

from alembic import command


def test_initial_migration_emits_order_decimal_check_constraints(monkeypatch) -> None:
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://mtoss:mtoss@localhost:5432/mtoss",
    )

    command.upgrade(config, "head", sql=True)

    sql = output.getvalue()
    for constraint_name in (
        "ck_order_intents_quantity_positive",
        "ck_order_intents_limit_price_positive",
        "ck_order_intents_filled_quantity_non_negative",
        "ck_order_intents_average_price_positive",
    ):
        assert f"CONSTRAINT {constraint_name} CHECK" in sql
