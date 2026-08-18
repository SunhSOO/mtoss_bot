from mtoss.infrastructure.db.models.order import OrderIntentRecord


def test_order_record_metadata_matches_the_postgresql_migration() -> None:
    columns = OrderIntentRecord.__table__.c

    assert columns.side.type.length == 16
    assert columns.state.type.length == 32
    assert columns.filled_quantity.server_default is not None
    assert str(columns.filled_quantity.server_default.arg) == "0"
