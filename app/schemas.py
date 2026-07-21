from __future__ import annotations

from decimal import Decimal
from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    client_id: int
    asset_symbol: str
    amount: Decimal = Field(gt=0)
    actor_id: int
    source_address: str = "external-client-wallet"
    risk_score: int = Field(default=10, ge=0, le=100)


# FEASIBILITY DEMO 1: mock node/indexer confirmation update.
class DepositConfirmationRequest(BaseModel):
    confirmations: int = Field(ge=0)
    actor_id: int


class AssetActionRequest(BaseModel):
    asset_symbol: str
    actor_id: int


class WithdrawalRequest(BaseModel):
    client_id: int
    asset_symbol: str
    amount: Decimal = Field(gt=0)
    destination_wallet_id: int
    actor_id: int


class ApprovalRequest(BaseModel):
    approver_id: int
    decision: str = Field(pattern="^(APPROVE|REJECT)$")


# FEASIBILITY DEMO 2: identifies the authorized back-office broadcast actor.
class ProcessWithdrawalRequest(BaseModel):
    actor_id: int


class StakingRequest(BaseModel):
    client_id: int
    asset_symbol: str
    amount: Decimal = Field(gt=0)
    actor_id: int
    validator: str = "mock-validator-01"


class RWARequest(BaseModel):
    issuer_client_id: int
    actor_id: int
    name: str
    symbol: str
    total_units: Decimal = Field(gt=0)
    reserve_description: str


class RWADeployRequest(BaseModel):
    actor_id: int
    network: str = "sepolia"


class RWAInvestorEligibilityRequest(BaseModel):
    actor_id: int
    investor_address: str
    eligible: bool = True


class RWAMintRequest(BaseModel):
    actor_id: int
    to_address: str
    amount_units: Decimal = Field(gt=0)


class WhitelistWalletRequest(BaseModel):
    client_id: int
    asset_symbol: str
    address: str
    label: str
    actor_id: int
    kind: str = "EXTERNAL"
    risk_score: int = Field(default=10, ge=0, le=100)
