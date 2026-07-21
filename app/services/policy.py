from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException


@dataclass(frozen=True)
class WalletAllocationPolicy:
    hot: Decimal = Decimal("0.05")
    warm: Decimal = Decimal("0.15")
    cold: Decimal = Decimal("0.80")


ALLOCATION_POLICY = WalletAllocationPolicy()
DAILY_LIMITS = {
    "BTC": Decimal("25"),
    "ETH": Decimal("500"),
    "SOL": Decimal("10000"),
    "AVAX": Decimal("5000"),
    "XRP": Decimal("1000000"),
    "POL": Decimal("500000"),
}


def validate_withdrawal_policy(
    *,
    asset_symbol: str,
    amount: Decimal,
    available: Decimal,
    destination_status: str,
    kyt_score: int,
) -> dict:
    if destination_status != "WHITELISTED":
        raise HTTPException(400, "Destination wallet is not whitelisted")
    if amount > available:
        raise HTTPException(400, "Insufficient available balance")
    limit = DAILY_LIMITS.get(asset_symbol, Decimal("0"))
    if limit and amount > limit:
        raise HTTPException(400, f"Amount exceeds demo daily limit: {limit} {asset_symbol}")
    if kyt_score >= 80:
        raise HTTPException(400, "KYT risk is HIGH; manual compliance investigation required")
    return {
        "required_backoffice_approvals": 2,
        "large_transaction_verification": amount >= (limit * Decimal("0.50") if limit else amount + 1),
        "kyt_threshold": 80,
    }
