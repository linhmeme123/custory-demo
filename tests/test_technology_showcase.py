from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_catalog_covers_all_requested_technology_groups() -> None:
    rows = client.get("/technology/catalog").json()
    assert len(rows) == 12
    assert {row["id"] for row in rows} == set(range(1, 13))


def test_showcase_exposes_chain_specific_blockchain_evidence() -> None:
    result = client.get("/technology/showcase").json()
    assert result["mpc_gk8_boundary"]["raw_private_key_present"] is False
    chains = result["chain_adapters"]
    assert chains["BTC"]["unsigned_transaction"]["workflow"] == "BIP-174-PSBT"
    assert chains["ETH"]["unsigned_transaction"]["gas_model"] == "EIP-1559"
    assert "TOKEN_2022" in chains["SOL"]["unsigned_transaction"]["token_programs"]
    assert chains["XRP"]["unsigned_transaction"]["DestinationTag"] == "10001"
