from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset
from app.services.ledger import client_liability_total, custody_onchain_total


def reconcile(
    db: Session,
    observed_chain_balances: dict[str, Decimal] | None = None,
) -> list[dict]:
    """Compare an independent chain observation with the custody ledger.

    When no observation is supplied the local wallet projection acts as the
    mock-node source. Public-testnet adapters should supply RPC observations.
    """
    result: list[dict] = []
    for asset in db.scalars(select(Asset)).all():
        projected = custody_onchain_total(db, asset.id)
        observed = (
            Decimal(observed_chain_balances[asset.symbol])
            if observed_chain_balances and asset.symbol in observed_chain_balances
            else projected
        )
        liability = client_liability_total(db, asset.id)
        chain_projection_difference = observed - projected
        custody_difference = observed - liability
        result.append(
            {
                "asset": asset.symbol,
                "observed_chain_total": str(observed),
                "wallet_projection_total": str(projected),
                "client_liability_total": str(liability),
                "chain_projection_difference": str(chain_projection_difference),
                "difference": str(custody_difference),
                "status": "MATCH" if chain_projection_difference == 0 and custody_difference == 0 else "BREAK",
            }
        )
    return result
