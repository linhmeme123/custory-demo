from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Deposit
from app.services.audit import append_audit
from app.services.authz import require_client_transaction_role
from app.services.kyt import MockKYTProvider
from app.services.ledger import get_asset, get_client_balance, wallet_by_kind


def simulate_deposit(
    db: Session,
    *,
    client_id: int,
    asset_symbol: str,
    amount: Decimal,
    actor_id: int,
    source_address: str,
    risk_score: int,
) -> dict:
    """FEASIBILITY DEMO 1: detect a deposit but do not credit available funds."""
    require_client_transaction_role(db, actor_id, client_id)
    asset = get_asset(db, asset_symbol)
    kyt = MockKYTProvider().screen(source_address, risk_score)
    if kyt.score >= 80:
        raise HTTPException(400, "Deposit held because KYT risk is HIGH")
    tx_hash = "0x" + hashlib.sha256(
        f"{client_id}|{asset.symbol}|{amount}|{source_address}".encode()
    ).hexdigest()
    balance = get_client_balance(db, client_id, asset.id)
    balance.pending = Decimal(balance.pending) + amount
    row = Deposit(
        client_id=client_id,
        asset_id=asset.id,
        amount=amount,
        source_address=source_address,
        created_by=actor_id,
        confirmations=0,
        required_confirmations=asset.confirmations_required,
        kyt_score=kyt.score,
        tx_hash=tx_hash,
    )
    db.add(row)
    db.flush()
    append_audit(
        db,
        actor_id=actor_id,
        action="DEPOSIT_DETECTED",
        entity_type="DEPOSIT",
        entity_id=row.id,
        payload={
            "amount": str(amount),
            "source_address": source_address,
            "kyt_score": kyt.score,
            "confirmations": 0,
            "required_confirmations": asset.confirmations_required,
        },
    )
    db.commit()
    return {
        "id": row.id,
        "status": row.state,
        "asset": asset.symbol,
        "amount": str(amount),
        "tx_hash": tx_hash,
        "confirmations": 0,
        "required_confirmations": asset.confirmations_required,
        "client_pending": str(balance.pending),
        "kyt": kyt.__dict__,
    }


def confirm_deposit(db: Session, *, deposit_id: int, confirmations: int, actor_id: int) -> dict:
    """FEASIBILITY DEMO 1: credit exactly once after the chain threshold."""
    row = db.get(Deposit, deposit_id)
    if not row:
        raise HTTPException(404, "Deposit not found")
    require_client_transaction_role(db, actor_id, row.client_id)
    if row.state == "CONFIRMED":
        return serialize_deposit(db, row)
    row.confirmations = max(row.confirmations, confirmations)
    if row.confirmations >= row.required_confirmations:
        wallet = wallet_by_kind(db, row.asset_id, "DEPOSIT", row.client_id)
        balance = get_client_balance(db, row.client_id, row.asset_id)
        wallet.balance = Decimal(wallet.balance) + Decimal(row.amount)
        balance.pending = Decimal(balance.pending) - Decimal(row.amount)
        balance.available = Decimal(balance.available) + Decimal(row.amount)
        row.state = "CONFIRMED"
        row.confirmed_at = datetime.now(timezone.utc)
        append_audit(
            db,
            actor_id=actor_id,
            action="DEPOSIT_CONFIRMED",
            entity_type="DEPOSIT",
            entity_id=row.id,
            payload={"tx_hash": row.tx_hash, "confirmations": row.confirmations},
        )
    db.commit()
    return serialize_deposit(db, row)


def serialize_deposit(db: Session, row: Deposit) -> dict:
    balance = get_client_balance(db, row.client_id, row.asset_id)
    wallet = wallet_by_kind(db, row.asset_id, "DEPOSIT", row.client_id)
    return {
        "id": row.id,
        "status": row.state,
        "asset": row.asset.symbol,
        "amount": str(row.amount),
        "tx_hash": row.tx_hash,
        "confirmations": row.confirmations,
        "required_confirmations": row.required_confirmations,
        "deposit_wallet_balance": str(wallet.balance),
        "client_pending": str(balance.pending),
        "client_available": str(balance.available),
    }
