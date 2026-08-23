from mtoss.infrastructure.db.models.order import OrderIntentRecord


def test_order_record_metadata_matches_the_postgresql_migration() -> None:
    columns = OrderIntentRecord.__table__.c

    assert columns.side.type.length == 16
    assert columns.order_type.type.length == 16
    assert columns.tranche_ref.type.length == 16
    assert columns.state.type.length == 32
    assert columns.filled_quantity.server_default is not None
    assert str(columns.filled_quantity.server_default.arg) == "0"
    assert columns.order_type.server_default is not None
    assert str(columns.order_type.server_default.arg) == "LIMIT"
    assert columns.reduce_only.server_default is not None

    money_columns = (
        "quantity",
        "limit_price",
        "reference_price",
        "stop_loss",
        "take_profit",
        "filled_quantity",
        "average_price",
    )
    for name in money_columns:
        assert columns[name].type.precision == 28
        assert columns[name].type.scale == 10

    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in OrderIntentRecord.__table__.constraints
        if hasattr(constraint, "sqltext")
    }
    assert check_constraints == {
        "ck_order_intents_quantity_positive": "quantity > 0",
        "ck_order_intents_limit_price_positive": (
            "limit_price IS NULL OR limit_price > 0"
        ),
        "ck_order_intents_filled_quantity_non_negative": "filled_quantity >= 0",
        "ck_order_intents_average_price_positive": (
            "average_price IS NULL OR average_price > 0"
        ),
        "ck_order_intents_reference_price_positive": (
            "reference_price IS NULL OR reference_price > 0"
        ),
        "ck_order_intents_stop_loss_positive": "stop_loss IS NULL OR stop_loss > 0",
        "ck_order_intents_take_profit_positive": (
            "take_profit IS NULL OR take_profit > 0"
        ),
    }
