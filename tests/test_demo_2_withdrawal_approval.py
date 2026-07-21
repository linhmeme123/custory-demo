from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_withdrawal(ids: dict) -> dict:
    response = client.post(
        "/withdrawals",
        json={
            "client_id": ids["client_id"],
            "asset_symbol": "BTC",
            "amount": "10",
            "destination_wallet_id": ids["exchange_btc_wallet_id"],
            "actor_id": ids["operator_id"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_two_distinct_approvals_are_required_before_signing() -> None:
    ids = client.post("/demo/reset").json()
    withdrawal = _create_withdrawal(ids)

    blocked = client.post(
        f"/withdrawals/{withdrawal['id']}/process",
        json={"actor_id": ids["backoffice_admin_1_id"]},
    )
    assert blocked.status_code == 400

    first = client.post(
        f"/withdrawals/{withdrawal['id']}/review",
        json={"approver_id": ids["backoffice_admin_1_id"], "decision": "APPROVE"},
    ).json()
    assert first["state"] == "PENDING_APPROVAL"

    duplicate = client.post(
        f"/withdrawals/{withdrawal['id']}/review",
        json={"approver_id": ids["backoffice_admin_1_id"], "decision": "APPROVE"},
    )
    assert duplicate.status_code == 400

    second = client.post(
        f"/withdrawals/{withdrawal['id']}/review",
        json={"approver_id": ids["backoffice_admin_2_id"], "decision": "APPROVE"},
    ).json()
    assert second["state"] == "APPROVED"

    completed = client.post(
        f"/withdrawals/{withdrawal['id']}/process",
        json={"actor_id": ids["backoffice_admin_1_id"]},
    ).json()
    assert completed["state"] == "COMPLETED"
    assert completed["tx_hash"].startswith("0x")


def test_rejection_releases_pending_balance() -> None:
    ids = client.post("/demo/reset").json()
    withdrawal = _create_withdrawal(ids)
    rejected = client.post(
        f"/withdrawals/{withdrawal['id']}/review",
        json={"approver_id": ids["backoffice_admin_1_id"], "decision": "REJECT"},
    ).json()
    assert rejected["state"] == "REJECTED"
    dashboard = client.get(f"/dashboard/{ids['client_id']}").json()
    btc = next(row for row in dashboard["balances"] if row["asset"] == "BTC")
    assert btc["available"] == "100.000000000000000000"
    assert btc["pending"] == "0E-18"
