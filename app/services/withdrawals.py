from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Approval, Client, Withdrawal
from app.services.audit import append_audit
from app.services.authz import require_backoffice_approver, require_backoffice_operator, require_client_transaction_role
from app.services.chain import get_adapter
from app.services.kyt import MockKYTProvider
from app.services.ledger import get_asset, get_client_balance, wallet_by_kind
from app.services.policy import validate_withdrawal_policy
from app.services.rwa_onchain import is_rwa_custody_asset, transfer_rwa_from_custody
from app.services.signer import MockMPCSigner
from app.services.travel_rule import build_travel_rule_message
from app.services.wallets import ensure_hot_liquidity


def create_withdrawal(
    db: Session,
    *,
    client_id: int,
    asset_symbol: str,
    amount: Decimal,
    destination_wallet_id: int,
    actor_id: int,
) -> dict:
    """FEASIBILITY DEMOS 2/3: policy and KYT gate before locking funds."""
    require_client_transaction_role(db, actor_id, client_id)
    asset = get_asset(db, asset_symbol)
    destination = db.get(__import__("app.models", fromlist=["Wallet"]).Wallet, destination_wallet_id)
    if not destination or destination.asset_id != asset.id or destination.client_id != client_id:
        raise HTTPException(400, "Destination wallet does not match asset")
    kyt = MockKYTProvider().screen(destination.address, destination.risk_score)
    balance = get_client_balance(db, client_id, asset.id)
    policy = validate_withdrawal_policy(
        asset_symbol=asset.symbol,
        amount=amount,
        available=Decimal(balance.available),
        destination_status=destination.status,
        kyt_score=kyt.score,
    )
    client = db.get(Client, client_id)
    travel_rule = None
    if destination.kind == "EXTERNAL":
        travel_rule = build_travel_rule_message(
            client_name=client.name,
            destination_label=destination.label,
            asset=asset.symbol,
            amount=str(amount),
        )
    balance.available = Decimal(balance.available) - amount
    balance.pending = Decimal(balance.pending) + amount
    row = Withdrawal(
        client_id=client_id,
        asset_id=asset.id,
        amount=amount,
        destination_wallet_id=destination.id,
        created_by=actor_id,
        state="PENDING_APPROVAL",
        kyt_score=kyt.score,
        travel_rule_json=json.dumps(travel_rule) if travel_rule else None,
    )
    db.add(row)
    db.flush()
    append_audit(
        db,
        actor_id=actor_id,
        action="WITHDRAWAL_CREATED",
        entity_type="WITHDRAWAL",
        entity_id=row.id,
        payload={
            "asset": asset.symbol,
            "amount": str(amount),
            "destination": destination.address,
            "kyt": kyt.__dict__,
            "policy": policy,
        },
    )
    db.commit()
    return serialize_withdrawal(db, row.id)


def approve_withdrawal(db: Session, *, withdrawal_id: int, approver_id: int, decision: str) -> dict:
    """FEASIBILITY DEMO 2: require two distinct back-office approvals."""
    require_backoffice_approver(db, approver_id)
    row = db.get(Withdrawal, withdrawal_id)
    if not row:
        raise HTTPException(404, "Withdrawal not found")
    if row.state not in {"PENDING_APPROVAL", "APPROVED"}:
        raise HTTPException(400, f"Cannot approve withdrawal in state {row.state}")
    approval = Approval(withdrawal_id=row.id, user_id=approver_id, decision=decision)
    db.add(approval)
    try:
        db.flush()
    except Exception as exc:  # Unique constraint / repeated approver
        db.rollback()
        raise HTTPException(400, "This user has already reviewed the withdrawal") from exc
    if decision == "REJECT":
        row.state = "REJECTED"
        balance = get_client_balance(db, row.client_id, row.asset_id)
        balance.pending = Decimal(balance.pending) - Decimal(row.amount)
        balance.available = Decimal(balance.available) + Decimal(row.amount)
    else:
        count = db.scalar(
            select(func.count(Approval.id)).where(
                Approval.withdrawal_id == row.id,
                Approval.decision == "APPROVE",
            )
        )
        if int(count or 0) >= 2:
            row.state = "APPROVED"
    append_audit(
        db,
        actor_id=approver_id,
        action=f"WITHDRAWAL_{decision}",
        entity_type="WITHDRAWAL",
        entity_id=row.id,
        payload={"state": row.state},
    )
    db.commit()
    return serialize_withdrawal(db, row.id)


def process_withdrawal(db: Session, *, withdrawal_id: int, actor_id: int) -> dict:
    """FEASIBILITY DEMOS 2/4: quorum-sign and broadcast through a chain adapter."""
    require_backoffice_operator(db, actor_id)
    row = db.get(Withdrawal, withdrawal_id)
    if not row:
        raise HTTPException(404, "Withdrawal not found")
    if row.state != "APPROVED":
        raise HTTPException(400, "Two back-office approvals are required")
    asset = row.asset
    destination = row.destination_wallet
    amount = Decimal(row.amount)
    row.state = "SIGNING"
    liquidity = ensure_hot_liquidity(db, asset_id=asset.id, amount=amount, actor_id=actor_id)
    hot = wallet_by_kind(db, asset.id, "HOT")
    if is_rwa_custody_asset(db, asset.symbol):
        network_payload = {
            "model": "EVM_ERC20_RWA_TRANSFER_REQUEST",
            "asset": asset.symbol,
            "amount": str(amount),
            "destination": destination.address,
        }
    else:
        adapter = get_adapter(asset.symbol)
        network_payload = adapter.build_transaction(
            symbol=asset.symbol,
            amount=amount,
            destination=destination.address,
        )
    signing_payload = json.dumps(network_payload, sort_keys=True, default=str)
    signed = MockMPCSigner().sign(signing_payload, ["mpc-node-a", "mpc-node-b"])
    if is_rwa_custody_asset(db, asset.symbol):
        broadcast = transfer_rwa_from_custody(
            db,
            asset_symbol=asset.symbol,
            to_address=destination.address,
            amount_units=amount,
        )
        tx_hash = broadcast["tx_hash"]
        transaction_payload = broadcast
    else:
        broadcast = adapter.broadcast(signed.signature, asset.confirmations_required, network_payload)
        tx_hash = broadcast.tx_hash
        transaction_payload = broadcast.__dict__
    hot.balance = Decimal(hot.balance) - amount
    balance = get_client_balance(db, row.client_id, asset.id)
    balance.pending = Decimal(balance.pending) - amount
    row.signing_payload = signing_payload
    row.signature = signed.signature
    row.tx_hash = tx_hash
    row.state = "COMPLETED"
    row.completed_at = datetime.now(timezone.utc)
    append_audit(
        db,
        actor_id=actor_id,
        action="WITHDRAWAL_COMPLETED",
        entity_type="WITHDRAWAL",
        entity_id=row.id,
        payload={
            "liquidity": liquidity,
            "mpc": {
                "algorithm": signed.algorithm,
                "participants": signed.participating_nodes,
                "threshold": signed.threshold,
            },
            "transaction": transaction_payload,
        },
    )
    db.commit()
    return serialize_withdrawal(db, row.id)


def serialize_withdrawal(db: Session, withdrawal_id: int) -> dict:
    row = db.get(Withdrawal, withdrawal_id)
    approvals = db.scalars(select(Approval).where(Approval.withdrawal_id == withdrawal_id)).all()
    return {
        "id": row.id,
        "client": row.client.name,
        "asset": row.asset.symbol,
        "amount": str(row.amount),
        "destination": row.destination_wallet.label,
        "state": row.state,
        "kyt_score": row.kyt_score,
        "travel_rule": json.loads(row.travel_rule_json) if row.travel_rule_json else None,
        "approvals": [{"user_id": a.user_id, "decision": a.decision} for a in approvals],
        "tx_hash": row.tx_hash,
    }
