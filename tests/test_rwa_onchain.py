from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_rwa_onchain_config_is_visible_without_testnet_credentials() -> None:
    result = client.get("/rwa/onchain/config").json()

    assert result["configured"] is False
    assert "EVM_TESTNET_RPC_URL" in result["required_env"]
    assert result["contract"].endswith("contracts/InstitutionalRWA.sol")


def test_rwa_contract_source_contains_testnet_controls() -> None:
    source = client.get("/technology/catalog").json()
    rwa = next(row for row in source if row["technology"] == "RWA tokenization")

    assert rwa["level"] == "TESTNET_CAPABLE"
    assert "deploy" in rwa["evidence"]
