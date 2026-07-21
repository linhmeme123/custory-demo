from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_deposit_confirmation_sweep_and_rebalance() -> None:
    ids = client.post("/demo/reset").json()
    detected = client.post(
        "/deposits/simulate",
        json={
            "client_id": ids["client_id"],
            "asset_symbol": "BTC",
            "amount": "20",
            "actor_id": ids["operator_id"],
            "source_address": "bc1q-clean-source",
            "risk_score": 8,
        },
    ).json()
    assert detected["status"] == "CONFIRMING"
    assert Decimal(detected["client_pending"]) == 20

    not_yet = client.post(
        f"/deposits/{detected['id']}/confirm",
        json={"confirmations": 2, "actor_id": ids["operator_id"]},
    ).json()
    assert not_yet["status"] == "CONFIRMING"
    assert Decimal(not_yet["deposit_wallet_balance"]) == 0

    confirmed = client.post(
        f"/deposits/{detected['id']}/confirm",
        json={"confirmations": 3, "actor_id": ids["operator_id"]},
    ).json()
    assert confirmed["status"] == "CONFIRMED"
    assert Decimal(confirmed["client_pending"]) == 0
    assert Decimal(confirmed["deposit_wallet_balance"]) == 20

    sweep = client.post(
        "/operations/sweep",
        json={"asset_symbol": "BTC", "actor_id": ids["backoffice_admin_1_id"]},
    ).json()
    assert Decimal(sweep["moved"]) == 20

    rebalance = client.post(
        "/operations/rebalance",
        json={"asset_symbol": "BTC", "actor_id": ids["backoffice_admin_1_id"]},
    ).json()
    assert Decimal(rebalance["hot"]) == Decimal("6")
    assert Decimal(rebalance["warm"]) == Decimal("18")
    assert Decimal(rebalance["cold"]) == Decimal("96")


def test_wallet_operations_require_backoffice_role() -> None:
    ids = client.post("/demo/reset").json()
    response = client.post(
        "/operations/rebalance",
        json={"asset_symbol": "BTC", "actor_id": ids["operator_id"]},
    )
    assert response.status_code == 403
