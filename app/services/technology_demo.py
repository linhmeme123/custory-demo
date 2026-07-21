from __future__ import annotations

from decimal import Decimal

from app.services.chain import ADAPTERS
from app.services.kyt import MockKYTProvider
from app.services.signer import MockMPCSigner


def technology_catalog() -> list[dict]:
    """Trace every requested technology to observable demo evidence."""
    return [
        {"id": 1, "technology": "MPC/HSM + GK8", "level": "MOCK", "evidence": "2-of-3 quorum, provider boundary, no raw private key"},
        {"id": 2, "technology": "Hot/warm/cold wallet", "level": "FUNCTIONAL", "evidence": "deposit sweep, 5/15/80 allocation, liquidity top-up"},
        {"id": 3, "technology": "Custody ledger & workflow", "level": "FUNCTIONAL", "evidence": "available/pending/locked/staked balances and withdrawal states"},
        {"id": 4, "technology": "Bitcoin UTXO/PSBT", "level": "ENVELOPE_MOCK", "evidence": "UTXO input/output, change, fee, dust, RBF and BIP-174 state"},
        {"id": 5, "technology": "Ethereum/EVM", "level": "ENVELOPE_MOCK", "evidence": "nonce, chain ID, EIP-1559 and ERC-20/721/1155/3643 support boundary"},
        {"id": 6, "technology": "Solana", "level": "ENVELOPE_MOCK", "evidence": "accounts, blockhash, compute units, priority fee, SPL and Token-2022"},
        {"id": 7, "technology": "XRP Ledger", "level": "ENVELOPE_MOCK", "evidence": "sequence, destination tag, fee, LastLedgerSequence and validated-ledger finality"},
        {"id": 8, "technology": "KYT/AML + Travel Rule", "level": "MOCK", "evidence": "Elliptic-compatible risk result, blocking policy and Travel Rule payload"},
        {"id": 9, "technology": "API integration", "level": "FUNCTIONAL", "evidence": "FastAPI/OpenAPI endpoints and adapter interfaces"},
        {"id": 10, "technology": "Staking", "level": "LEDGER_MOCK", "evidence": "stakeable asset validation and available-to-staked accounting"},
        {"id": 11, "technology": "RWA tokenization", "level": "TESTNET_CAPABLE", "evidence": "ERC-20 contract deploy, investor eligibility, mint and status endpoints for EVM testnet"},
        {"id": 12, "technology": "Security hardening", "level": "BOUNDARY_ONLY", "evidence": "RBAC, maker-checker, hash-chained audit; pen test/FIPS/DR remain production gaps"},
    ]


def run_technology_showcase() -> dict:
    signer = MockMPCSigner()
    signing = signer.sign("institutional-custody-demo", ["mpc-node-a", "mpc-node-b"])
    chains = {}
    destinations = {"BTC": "bc1q-demo", "ETH": "0xabc", "AVAX": "0xabc", "POL": "0xabc", "SOL": "sol-demo", "XRP": "rDemo:10001"}
    for symbol, adapter in ADAPTERS.items():
        destination = destinations[symbol]
        chains[symbol] = {
            "generated_address": adapter.generate_address(client_reference="ABC-FUND", index=0),
            "fee_estimate": adapter.estimate_fee(amount=Decimal("1.25"), destination=destination),
            "unsigned_transaction": adapter.build_transaction(symbol=symbol, amount=Decimal("1.25"), destination=destination),
        }
    return {
        "warning": "Feasibility simulation: no real key, vendor credential or funds.",
        "mpc_gk8_boundary": {
            "provider": "MOCK_GK8_ADAPTER",
            "threshold": signing.threshold,
            "participants": signing.participating_nodes,
            "algorithm": signing.algorithm,
            "raw_private_key_present": False,
            "hsm_production_requirement": "FIPS 140-3 validation and vendor key ceremony",
        },
        "kyt_elliptic_boundary": MockKYTProvider().screen("bc1q-clean-demo", 8).__dict__,
        "chain_adapters": chains,
        "token_standards": ["ERC-20", "ERC-721", "ERC-1155", "ERC-3643", "SPL Token", "Token-2022"],
        "catalog": technology_catalog(),
    }
