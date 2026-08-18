from mtoss.infrastructure.db.models.order import OrderIntentRecord


def test_order_record_metadata_matches_the_postgresql_migration() -> None:
    columns = OrderIntentRecord.__table__.c

    assert columns.side.type.length == 16
    assert columns.state.type.length == 32
    assert columns.filled_quantity.server_default is not None
    assert str(columns.filled_quantity.server_default.arg) == "0"
    for name in ("quantity", "limit_price", "filled_quantity", "average_price"):
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
    }
