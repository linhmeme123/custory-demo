from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import StakingPosition
from app.services.audit import append_audit
from app.services.authz import require_client_transaction_role
from app.services.ledger import get_asset, get_client_balance

STAKABLE = {"ETH", "SOL", "AVAX"}


def create_staking_position(
    db: Session,
    *,
    client_id: int,
    asset_symbol: str,
    amount: Decimal,
    actor_id: int,
    validator: str,
) -> dict:
    require_client_transaction_role(db, actor_id, client_id)
    asset = get_asset(db, asset_symbol)
    if asset.symbol not in STAKABLE:
        raise HTTPException(400, f"{asset.symbol} is not enabled for staking in this demo")
    balance = get_client_balance(db, client_id, asset.id)
    if Decimal(balance.available) < amount:
        raise HTTPException(400, "Insufficient available balance")
    balance.available = Decimal(balance.available) - amount
    balance.staked = Decimal(balance.staked) + amount
    position = StakingPosition(
        client_id=client_id,
        asset_id=asset.id,
        amount=amount,
        validator=validator,
    )
    db.add(position)
    db.flush()
    append_audit(
        db,
        actor_id=actor_id,
        action="STAKING_CREATED",
        entity_type="STAKING_POSITION",
        entity_id=position.id,
        payload={"asset": asset.symbol, "amount": str(amount), "validator": validator},
    )
    db.commit()
    return {
        "id": position.id,
        "asset": asset.symbol,
        "amount": str(position.amount),
        "validator": position.validator,
        "status": position.status,
    }
