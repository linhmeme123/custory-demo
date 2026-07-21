from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_high_risk_wallet_requires_review_and_cannot_be_withdrawn_to() -> None:
    ids = client.post("/demo/reset").json()
    screened = client.post(
        "/wallets/whitelist",
        json={
            "client_id": ids["client_id"],
            "asset_symbol": "BTC",
            "address": "bc1q-hacker-mixer-wallet",
            "label": "Suspicious destination",
            "actor_id": ids["client_admin_id"],
            "risk_score": 10,
        },
    ).json()
    assert screened["status"] == "REVIEW_REQUIRED"
    assert screened["kyt"]["level"] == "HIGH"

    withdrawal = client.post(
        "/withdrawals",
        json={
            "client_id": ids["client_id"],
            "asset_symbol": "BTC",
            "amount": "1",
            "destination_wallet_id": screened["id"],
            "actor_id": ids["operator_id"],
        },
    )
    assert withdrawal.status_code == 400


def test_high_risk_deposit_is_held_before_ledger_credit() -> None:
    ids = client.post("/demo/reset").json()
    response = client.post(
        "/deposits/simulate",
        json={
            "client_id": ids["client_id"],
            "asset_symbol": "BTC",
            "amount": "1",
            "actor_id": ids["operator_id"],
            "source_address": "bc1q-ransom-source",
            "risk_score": 5,
        },
    )
    assert response.status_code == 400
