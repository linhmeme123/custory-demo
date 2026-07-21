from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Wallet
from app.services.audit import append_audit
from app.services.authz import require_backoffice_operator
from app.services.ledger import get_asset, wallet_by_kind
from app.services.policy import ALLOCATION_POLICY


def sweep_deposit_wallets(db: Session, *, asset_symbol: str, actor_id: int) -> dict:
    """FEASIBILITY DEMO 1: authorized deposit-to-omnibus projection move."""
    require_backoffice_operator(db, actor_id)
    asset = get_asset(db, asset_symbol)
    omnibus = wallet_by_kind(db, asset.id, "OMNIBUS")
    deposits = db.scalars(select(Wallet).where(Wallet.asset_id == asset.id, Wallet.kind == "DEPOSIT")).all()
    moved = Decimal("0")
    for wallet in deposits:
        amount = Decimal(wallet.balance)
        if amount > 0:
            wallet.balance = Decimal("0")
            omnibus.balance = Decimal(omnibus.balance) + amount
            moved += amount
    append_audit(
        db,
        actor_id=actor_id,
        action="WALLET_SWEEP",
        entity_type="ASSET",
        entity_id=asset.symbol,
        payload={"moved": str(moved), "destination": omnibus.address},
    )
    db.commit()
    return {"asset": asset.symbol, "moved": str(moved), "omnibus_balance": str(omnibus.balance)}


def rebalance_wallets(db: Session, *, asset_symbol: str, actor_id: int) -> dict:
    """FEASIBILITY DEMO 1: authorized 5/15/80 hot/warm/cold allocation."""
    require_backoffice_operator(db, actor_id)
    asset = get_asset(db, asset_symbol)
    omnibus = wallet_by_kind(db, asset.id, "OMNIBUS")
    hot = wallet_by_kind(db, asset.id, "HOT")
    warm = wallet_by_kind(db, asset.id, "WARM")
    cold = wallet_by_kind(db, asset.id, "COLD")
    total = sum((Decimal(w.balance) for w in (omnibus, hot, warm, cold)), Decimal("0"))
    hot.balance = total * ALLOCATION_POLICY.hot
    warm.balance = total * ALLOCATION_POLICY.warm
    cold.balance = total - Decimal(hot.balance) - Decimal(warm.balance)
    omnibus.balance = Decimal("0")
    result = {
        "asset": asset.symbol,
        "total": str(total),
        "hot": str(hot.balance),
        "warm": str(warm.balance),
        "cold": str(cold.balance),
        "cold_ratio": str((Decimal(cold.balance) / total) if total else Decimal("0")),
    }
    append_audit(
        db,
        actor_id=actor_id,
        action="WALLET_REBALANCE",
        entity_type="ASSET",
        entity_id=asset.symbol,
        payload=result,
    )
    db.commit()
    return result


def ensure_hot_liquidity(db: Session, *, asset_id: int, amount: Decimal, actor_id: int) -> dict:
    hot = wallet_by_kind(db, asset_id, "HOT")
    warm = wallet_by_kind(db, asset_id, "WARM")
    cold = wallet_by_kind(db, asset_id, "COLD")
    transfers: list[dict] = []
    needed = amount - Decimal(hot.balance)
    if needed > 0:
        from_warm = min(needed, Decimal(warm.balance))
        if from_warm > 0:
            warm.balance = Decimal(warm.balance) - from_warm
            hot.balance = Decimal(hot.balance) + from_warm
            needed -= from_warm
            transfers.append({"from": "WARM", "to": "HOT", "amount": str(from_warm)})
    if needed > 0:
        from_cold = min(needed, Decimal(cold.balance))
        if from_cold > 0:
            cold.balance = Decimal(cold.balance) - from_cold
            hot.balance = Decimal(hot.balance) + from_cold
            needed -= from_cold
            transfers.append({"from": "COLD", "to": "HOT", "amount": str(from_cold)})
    if needed > 0:
        raise ValueError("Insufficient operational wallet liquidity")
    if transfers:
        append_audit(
            db,
            actor_id=actor_id,
            action="LIQUIDITY_TOP_UP",
            entity_type="ASSET",
            entity_id=asset_id,
            payload={"transfers": transfers},
        )
    return {"transfers": transfers, "hot_balance": str(hot.balance)}
