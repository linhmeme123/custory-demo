from decimal import Decimal

import pytest

from app.services.chain import get_adapter
from app.services.signer import MockMPCSigner


@pytest.mark.parametrize(
    ("symbol", "destination", "expected_model"),
    [
        ("BTC", "bc1q-demo", "UTXO"),
        ("ETH", "0xabc", "ACCOUNT"),
        ("AVAX", "0xabc", "ACCOUNT"),
        ("POL", "0xabc", "ACCOUNT"),
        ("SOL", "solana-demo", "SOLANA_ACCOUNTS"),
        ("XRP", "rDemo:123", "XRPL_ACCOUNT"),
    ],
)
def test_each_chain_builds_signs_and_broadcasts_its_own_envelope(
    symbol: str, destination: str, expected_model: str
) -> None:
    adapter = get_adapter(symbol)
    payload = adapter.build_transaction(symbol=symbol, amount=Decimal("1.25"), destination=destination)
    assert payload["model"] == expected_model
    signed = MockMPCSigner().sign(str(payload), ["mpc-node-a", "mpc-node-b"])
    result = adapter.broadcast(signed.signature, 2, payload)
    assert result.status == "CONFIRMED"
    assert result.confirmations == 2
    assert result.tx_hash.startswith("0x")


def test_mpc_quorum_rejects_one_participant() -> None:
    with pytest.raises(ValueError, match="two unique"):
        MockMPCSigner().sign("payload", ["mpc-node-a"])
