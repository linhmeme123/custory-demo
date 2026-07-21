from decimal import Decimal

from app.database import SessionLocal
from app.seed import reset_and_seed
from app.services.reconciliation import reconcile


def test_reconciliation_matches_independent_chain_observation() -> None:
    with SessionLocal() as session:
        reset_and_seed(session)
    with SessionLocal() as session:
        rows = reconcile(session, {"BTC": Decimal("100"), "ETH": Decimal("1000")})
        assert next(row for row in rows if row["asset"] == "BTC")["status"] == "MATCH"
        assert next(row for row in rows if row["asset"] == "ETH")["status"] == "MATCH"


def test_reconciliation_detects_chain_projection_break() -> None:
    with SessionLocal() as session:
        reset_and_seed(session)
    with SessionLocal() as session:
        rows = reconcile(session, {"BTC": Decimal("99.5")})
        btc = next(row for row in rows if row["asset"] == "BTC")
        assert btc["status"] == "BREAK"
        assert Decimal(btc["chain_projection_difference"]) == Decimal("-0.5")
        assert Decimal(btc["difference"]) == Decimal("-0.5")
