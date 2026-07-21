from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(30), default="CLIENT")
    # Python 3.9 compatibility: SQLAlchemy evaluates Mapped annotations at
    # runtime, so use Optional instead of the Python 3.10 `T | None` syntax.
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id"), nullable=True)
    client: Mapped[Optional[Client]] = relationship()


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True)
    network: Mapped[str] = mapped_column(String(80))
    decimals: Mapped[int] = mapped_column(Integer)
    confirmations_required: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("asset_id", "address", name="uq_asset_address"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clients.id"), nullable=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    kind: Mapped[str] = mapped_column(String(30))
    address: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    asset: Mapped[Asset] = relationship()
    client: Mapped[Optional[Client]] = relationship()


class ClientBalance(Base):
    __tablename__ = "client_balances"
    __table_args__ = (UniqueConstraint("client_id", "asset_id", name="uq_client_asset_balance"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    available: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    pending: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    locked: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    staked: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    client: Mapped[Client] = relationship()
    asset: Mapped[Asset] = relationship()


# FEASIBILITY DEMO 1: persistent chain-detection/confirmation state used by
# tests/test_demo_1_deposit_wallets.py. This is intentionally separate from
# ClientBalance so an unconfirmed deposit cannot become available funds.
class Deposit(Base):
    __tablename__ = "deposits"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    source_address: Mapped[str] = mapped_column(String(255))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(40), default="CONFIRMING")
    confirmations: Mapped[int] = mapped_column(Integer, default=0)
    required_confirmations: Mapped[int] = mapped_column(Integer)
    kyt_score: Mapped[int] = mapped_column(Integer, default=0)
    tx_hash: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    client: Mapped[Client] = relationship()
    asset: Mapped[Asset] = relationship()


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    destination_wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(40), default="PENDING_APPROVAL")
    kyt_score: Mapped[int] = mapped_column(Integer, default=0)
    travel_rule_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signing_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    client: Mapped[Client] = relationship()
    asset: Mapped[Asset] = relationship()
    destination_wallet: Mapped[Wallet] = relationship(foreign_keys=[destination_wallet_id])
    creator: Mapped[User] = relationship(foreign_keys=[created_by])


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (UniqueConstraint("withdrawal_id", "user_id", name="uq_withdrawal_approver"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    withdrawal_id: Mapped[int] = mapped_column(ForeignKey("withdrawals.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64), default="0" * 64)
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class StakingPosition(Base):
    __tablename__ = "staking_positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(36, 18))
    validator: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE")
    rewards: Mapped[Decimal] = mapped_column(Numeric(36, 18), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RWAAsset(Base):
    __tablename__ = "rwa_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    symbol: Mapped[str] = mapped_column(String(20), unique=True)
    total_units: Mapped[Decimal] = mapped_column(Numeric(36, 6))
    reserve_description: Mapped[str] = mapped_column(Text)
    issuer_client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    status: Mapped[str] = mapped_column(String(40), default="ISSUED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RWAContractDeployment(Base):
    __tablename__ = "rwa_contract_deployments"
    id: Mapped[int] = mapped_column(primary_key=True)
    rwa_asset_id: Mapped[int] = mapped_column(ForeignKey("rwa_assets.id"), unique=True)
    network: Mapped[str] = mapped_column(String(80))
    chain_id: Mapped[int] = mapped_column(Integer)
    contract_address: Mapped[str] = mapped_column(String(80), unique=True)
    deploy_tx_hash: Mapped[str] = mapped_column(String(80))
    deployed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="DEPLOYED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    rwa_asset: Mapped[RWAAsset] = relationship()
