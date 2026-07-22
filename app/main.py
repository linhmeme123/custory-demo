from __future__ import annotations

import json
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Asset, AuditLog, Client, ClientBalance, RWAAsset, StakingPosition, User, Wallet, Withdrawal
from app.schemas import (
    ApprovalRequest,
    AssetActionRequest,
    DepositRequest,
    DepositConfirmationRequest,
    ProcessWithdrawalRequest,
    RWAConfirmCustodyDepositRequest,
    RWADeployRequest,
    RWAInvestorEligibilityRequest,
    RWAInvestorDepositTransferRequest,
    RWAMintRequest,
    RWARequest,
    StakingRequest,
    WhitelistWalletRequest,
    WithdrawalRequest,
)
from app.seed import reset_and_seed
from app.services.audit import append_audit
from app.services.authz import require_client_admin
from app.services.chain import ADAPTERS
from app.services.deposits import confirm_deposit, simulate_deposit
from app.services.kyt import MockKYTProvider
from app.services.ledger import client_liability_total, custody_onchain_total, get_asset
from app.services.reconciliation import reconcile
from app.services.rwa import issue_rwa
from app.services.rwa_onchain import (
    confirm_rwa_custody_deposit,
    deploy_rwa_contract,
    mint_rwa_tokens,
    onchain_config_status,
    rwa_custody_instructions,
    rwa_onchain_status,
    set_investor_eligibility,
    transfer_rwa_to_custody_from_investor,
)
from app.services.staking import create_staking_position
from app.services.technology_demo import run_technology_showcase, technology_catalog
from app.services.wallets import rebalance_wallets, sweep_deposit_wallets
from app.services.withdrawals import approve_withdrawal, create_withdrawal, process_withdrawal

Base.metadata.create_all(bind=engine)
app = FastAPI(
    title="Institutional Custody Technology Demo",
    version="1.0.0",
    description="",
)

@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)) -> dict:
    return reset_and_seed(db)


@app.get("/demo/context")
def demo_context(db: Session = Depends(get_db)) -> dict:
    users = db.scalars(select(User)).all()
    clients = db.scalars(select(Client)).all()
    external = db.scalars(select(Wallet).where(Wallet.kind == "EXTERNAL")).all()
    return {
        "clients": [{"id": c.id, "name": c.name} for c in clients],
        "users": [{"id": u.id, "name": u.name, "role": u.role, "scope": u.scope} for u in users],
        "external_wallets": [
            {"id": w.id, "label": w.label, "asset": w.asset.symbol, "status": w.status, "risk_score": w.risk_score}
            for w in external
        ],
    }


@app.get("/dashboard/{client_id}")
def dashboard(client_id: int, db: Session = Depends(get_db)) -> dict:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(404, "Client not found")
    balances = db.scalars(select(ClientBalance).where(ClientBalance.client_id == client_id)).all()
    withdrawals = db.scalars(select(Withdrawal).where(Withdrawal.client_id == client_id).order_by(Withdrawal.id.desc())).all()
    staking = db.scalars(select(StakingPosition).where(StakingPosition.client_id == client_id)).all()
    return {
        "client": client.name,
        "balances": [
            {
                "asset": b.asset.symbol,
                "available": str(b.available),
                "pending": str(b.pending),
                "locked": str(b.locked),
                "staked": str(b.staked),
                "total": str(Decimal(b.available) + Decimal(b.pending) + Decimal(b.locked) + Decimal(b.staked)),
            }
            for b in balances
        ],
        "withdrawals": [
            {"id": w.id, "asset": w.asset.symbol, "amount": str(w.amount), "state": w.state, "tx_hash": w.tx_hash}
            for w in withdrawals
        ],
        "staking": [
            {"id": s.id, "asset": db.get(Asset, s.asset_id).symbol, "amount": str(s.amount), "status": s.status}
            for s in staking
        ],
    }


@app.get("/wallets")
def wallets(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Wallet).order_by(Wallet.asset_id, Wallet.kind)).all()
    return [
        {
            "id": w.id,
            "asset": w.asset.symbol,
            "kind": w.kind,
            "label": w.label,
            "status": w.status,
            "balance": str(w.balance),
            "risk_score": w.risk_score,
        }
        for w in rows
    ]


@app.post("/wallets/whitelist")
def whitelist_wallet(request: WhitelistWalletRequest, db: Session = Depends(get_db)) -> dict:
    require_client_admin(db, request.actor_id, request.client_id)
    asset = get_asset(db, request.asset_symbol)
    kyt = MockKYTProvider().screen(request.address, request.risk_score)
    status = "REVIEW_REQUIRED" if kyt.score >= 80 else "WHITELISTED"
    wallet = Wallet(
        client_id=request.client_id,
        asset_id=asset.id,
        kind=request.kind,
        address=request.address,
        label=request.label,
        status=status,
        risk_score=kyt.score,
    )
    db.add(wallet)
    db.flush()
    append_audit(
        db,
        actor_id=request.actor_id,
        action="WALLET_SCREENED",
        entity_type="WALLET",
        entity_id=wallet.id,
        payload={"status": status, "kyt": kyt.__dict__},
    )
    db.commit()
    return {"id": wallet.id, "status": status, "kyt": kyt.__dict__}


@app.post("/deposits/simulate")
def deposit(request: DepositRequest, db: Session = Depends(get_db)) -> dict:
    return simulate_deposit(db, **request.model_dump())


@app.post("/deposits/{deposit_id}/confirm")
def deposit_confirm(deposit_id: int, request: DepositConfirmationRequest, db: Session = Depends(get_db)) -> dict:
    return confirm_deposit(db, deposit_id=deposit_id, **request.model_dump())


@app.post("/operations/sweep")
def sweep(request: AssetActionRequest, db: Session = Depends(get_db)) -> dict:
    return sweep_deposit_wallets(db, asset_symbol=request.asset_symbol, actor_id=request.actor_id)


@app.post("/operations/rebalance")
def rebalance(request: AssetActionRequest, db: Session = Depends(get_db)) -> dict:
    return rebalance_wallets(db, asset_symbol=request.asset_symbol, actor_id=request.actor_id)


@app.post("/withdrawals")
def withdrawals_create(request: WithdrawalRequest, db: Session = Depends(get_db)) -> dict:
    return create_withdrawal(db, **request.model_dump())


@app.post("/withdrawals/{withdrawal_id}/review")
def withdrawals_review(withdrawal_id: int, request: ApprovalRequest, db: Session = Depends(get_db)) -> dict:
    return approve_withdrawal(
        db,
        withdrawal_id=withdrawal_id,
        approver_id=request.approver_id,
        decision=request.decision,
    )


@app.post("/withdrawals/{withdrawal_id}/process")
def withdrawals_process(
    withdrawal_id: int,
    request: ProcessWithdrawalRequest,
    db: Session = Depends(get_db),
) -> dict:
    return process_withdrawal(db, withdrawal_id=withdrawal_id, actor_id=request.actor_id)


@app.post("/staking")
def staking(request: StakingRequest, db: Session = Depends(get_db)) -> dict:
    return create_staking_position(db, **request.model_dump())


@app.post("/rwa/issue")
def rwa_issue(request: RWARequest, db: Session = Depends(get_db)) -> dict:
    return issue_rwa(db, **request.model_dump())


@app.get("/rwa/onchain/config")
def rwa_onchain_config() -> dict:
    return onchain_config_status()


@app.post("/rwa/{rwa_asset_id}/onchain/deploy")
def rwa_deploy_contract(rwa_asset_id: int, request: RWADeployRequest, db: Session = Depends(get_db)) -> dict:
    return deploy_rwa_contract(db, rwa_asset_id=rwa_asset_id, **request.model_dump())


@app.post("/rwa/{rwa_asset_id}/onchain/investors")
def rwa_set_investor(
    rwa_asset_id: int,
    request: RWAInvestorEligibilityRequest,
    db: Session = Depends(get_db),
) -> dict:
    return set_investor_eligibility(db, rwa_asset_id=rwa_asset_id, **request.model_dump())


@app.post("/rwa/{rwa_asset_id}/onchain/mint")
def rwa_mint(rwa_asset_id: int, request: RWAMintRequest, db: Session = Depends(get_db)) -> dict:
    return mint_rwa_tokens(db, rwa_asset_id=rwa_asset_id, **request.model_dump())


@app.get("/rwa/{rwa_asset_id}/onchain/status")
def rwa_status(rwa_asset_id: int, db: Session = Depends(get_db)) -> dict:
    return rwa_onchain_status(db, rwa_asset_id=rwa_asset_id)


@app.get("/rwa/{rwa_asset_id}/custody/instructions")
def rwa_deposit_instructions(rwa_asset_id: int, db: Session = Depends(get_db)) -> dict:
    return rwa_custody_instructions(db, rwa_asset_id=rwa_asset_id)


@app.post("/rwa/{rwa_asset_id}/custody/deposits/confirm")
def rwa_confirm_deposit(
    rwa_asset_id: int,
    request: RWAConfirmCustodyDepositRequest,
    db: Session = Depends(get_db),
) -> dict:
    return confirm_rwa_custody_deposit(db, rwa_asset_id=rwa_asset_id, **request.model_dump())


@app.post("/rwa/{rwa_asset_id}/custody/deposits/transfer-from-investor")
def rwa_transfer_deposit_from_investor(
    rwa_asset_id: int,
    request: RWAInvestorDepositTransferRequest,
    db: Session = Depends(get_db),
) -> dict:
    return transfer_rwa_to_custody_from_investor(db, rwa_asset_id=rwa_asset_id, **request.model_dump())


@app.get("/reconciliation")
def reconciliation(db: Session = Depends(get_db)) -> list[dict]:
    return reconcile(db)


@app.get("/infrastructure/rpc-health")
def rpc_health() -> dict:
    return {symbol: adapter.health() for symbol, adapter in ADAPTERS.items()}


@app.get("/technology/catalog")
def technologies() -> list[dict]:
    return technology_catalog()


@app.get("/technology/showcase")
def technology_showcase() -> dict:
    return run_technology_showcase()


@app.get("/audit")
def audit(db: Session = Depends(get_db)) -> list[dict]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100)).all()
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "entity": f"{row.entity_type}:{row.entity_id}",
            "payload": json.loads(row.payload_json),
            "prev_hash": row.prev_hash,
            "entry_hash": row.entry_hash,
        }
        for row in logs
    ]
