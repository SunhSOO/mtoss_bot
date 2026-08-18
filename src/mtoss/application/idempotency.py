import hashlib
from uuid import UUID

from mtoss.domain.enums import OrderSide


def build_intent_key(
    account_id: UUID,
    signal_id: UUID,
    target_version: int,
    symbol: str,
    side: OrderSide,
) -> str:
    canonical = "|".join(
        [str(account_id), str(signal_id), str(target_version), symbol.upper(), side.value]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
