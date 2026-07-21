from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, ClientBalance, Wallet

CUSTODY_WALLET_KINDS = {"DEPOSIT", "OMNIBUS", "HOT", "WARM", "COLD"}


def get_asset(db: Session, symbol: str) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.symbol == symbol.upper()))
    if not asset:
        raise HTTPException(404, f"Asset {symbol} not found")
    if not asset.enabled:
        raise HTTPException(400, f"Asset {symbol} is disabled")
    return asset


def get_client_balance(db: Session, client_id: int, asset_id: int) -> ClientBalance:
    balance = db.scalar(
        select(ClientBalance).where(
            ClientBalance.client_id == client_id,
            ClientBalance.asset_id == asset_id,
        )
    )
    if not balance:
        balance = ClientBalance(client_id=client_id, asset_id=asset_id)
        db.add(balance)
        db.flush()
    return balance


def wallet_by_kind(db: Session, asset_id: int, kind: str, client_id: int | None = None) -> Wallet:
    query = select(Wallet).where(Wallet.asset_id == asset_id, Wallet.kind == kind)
    if client_id is None:
        query = query.where(Wallet.client_id.is_(None))
    else:
        query = query.where(Wallet.client_id == client_id)
    wallet = db.scalar(query.limit(1))
    if not wallet:
        raise HTTPException(404, f"{kind} wallet not found")
    return wallet


def custody_onchain_total(db: Session, asset_id: int) -> Decimal:
    wallets = db.scalars(select(Wallet).where(Wallet.asset_id == asset_id)).all()
    return sum((Decimal(w.balance) for w in wallets if w.kind in CUSTODY_WALLET_KINDS), Decimal("0"))


def client_liability_total(db: Session, asset_id: int) -> Decimal:
    balances = db.scalars(select(ClientBalance).where(ClientBalance.asset_id == asset_id)).all()
    return sum(
        (
            Decimal(b.available) + Decimal(b.pending) + Decimal(b.locked) + Decimal(b.staked)
            for b in balances
        ),
        Decimal("0"),
    )
