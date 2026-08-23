"""주문에 브래킷(손절·익절)과 시장가 경로를 추가한다.

헤징 계좌에서는 주문 하나가 포지션 하나가 되고 각자 SL/TP를 갖는다. 그 값을 브로커
서버에 심어야 이 서버가 꺼져 있어도 손절이 작동하므로, 주문 인텐트가 처음부터 이
값을 실어 나를 수 있어야 한다.

`order_type`은 기존 행이 전부 지정가였으므로 `LIMIT`을 서버 기본값으로 채운다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_order_brackets"
down_revision: str | None = "0001_execution_core"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "order_intents",
        sa.Column("order_type", sa.String(16), nullable=False, server_default="LIMIT"),
    )
    op.add_column(
        "order_intents", sa.Column("reference_price", sa.Numeric(28, 10), nullable=True)
    )
    op.add_column("order_intents", sa.Column("stop_loss", sa.Numeric(28, 10), nullable=True))
    op.add_column("order_intents", sa.Column("take_profit", sa.Numeric(28, 10), nullable=True))
    op.add_column(
        "order_intents",
        sa.Column("reduce_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("order_intents", sa.Column("tranche_ref", sa.String(16), nullable=True))

    op.create_check_constraint(
        "ck_order_intents_reference_price_positive",
        "order_intents",
        "reference_price IS NULL OR reference_price > 0",
    )
    op.create_check_constraint(
        "ck_order_intents_stop_loss_positive",
        "order_intents",
        "stop_loss IS NULL OR stop_loss > 0",
    )
    op.create_check_constraint(
        "ck_order_intents_take_profit_positive",
        "order_intents",
        "take_profit IS NULL OR take_profit > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_order_intents_take_profit_positive", "order_intents", type_="check"
    )
    op.drop_constraint("ck_order_intents_stop_loss_positive", "order_intents", type_="check")
    op.drop_constraint(
        "ck_order_intents_reference_price_positive", "order_intents", type_="check"
    )
    op.drop_column("order_intents", "tranche_ref")
    op.drop_column("order_intents", "reduce_only")
    op.drop_column("order_intents", "take_profit")
    op.drop_column("order_intents", "stop_loss")
    op.drop_column("order_intents", "reference_price")
    op.drop_column("order_intents", "order_type")
