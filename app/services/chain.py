from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx


@dataclass(frozen=True)
class BroadcastResult:
    tx_hash: str
    confirmations: int
    status: str
    network_payload: dict[str, Any]


class BlockchainAdapter:
    network = "UNKNOWN"

    def generate_address(self, *, client_reference: str, index: int = 0) -> dict:
        material = hashlib.sha256(f"{self.network}|{client_reference}|{index}".encode()).hexdigest()
        return {
            "address": f"demo-{self.network.lower()}-{material[:24]}",
            "derivation_reference": f"m/demo/{index}",
            "mode": "WATCH_ONLY_DEMO",
        }

    def get_balance(self, *, address: str) -> dict:
        return {"address": address, "balance": "0", "source": "MOCK_RPC"}

    def estimate_fee(self, *, amount: Decimal, destination: str) -> dict:
        return {"fee": "0", "unit": "NETWORK_NATIVE", "mode": "MOCK"}

    def get_transaction_status(self, *, tx_hash: str, confirmations_required: int) -> dict:
        return {
            "tx_hash": tx_hash,
            "state": "CONFIRMED",
            "confirmations": confirmations_required,
            "final": True,
            "source": "MOCK_RPC",
        }

    def build_transaction(self, *, symbol: str, amount: Decimal, destination: str, memo: str | None = None) -> dict:
        raise NotImplementedError

    def broadcast(self, signed_payload: str, confirmations_required: int, network_payload: dict) -> BroadcastResult:
        material = json.dumps(network_payload, sort_keys=True, default=str) + signed_payload
        tx_hash = "0x" + hashlib.sha256(material.encode()).hexdigest()
        return BroadcastResult(
            tx_hash=tx_hash,
            confirmations=confirmations_required,
            status="CONFIRMED",
            network_payload=network_payload,
        )

    def health(self) -> dict:
        return {"mode": "MOCK", "healthy": True}


class BitcoinAdapter(BlockchainAdapter):
    network = "BITCOIN"

    def generate_address(self, *, client_reference: str, index: int = 0) -> dict:
        result = super().generate_address(client_reference=client_reference, index=index)
        result.update({"address": "bc1q" + hashlib.sha256(f"{client_reference}|{index}".encode()).hexdigest()[:38], "format": "SEGWIT_V0", "taproot_supported": True})
        return result

    def estimate_fee(self, *, amount: Decimal, destination: str) -> dict:
        return {"fee_rate_sat_vb": 8, "estimated_vbytes": 141, "estimated_fee_sat": 1128, "rbf_allowed": True}

    def build_transaction(self, *, symbol: str, amount: Decimal, destination: str, memo: str | None = None) -> dict:
        return {
            "model": "UTXO",
            "workflow": "BIP-174-PSBT",
            "asset": symbol,
            "inputs": [{"txid": "demo-utxo", "vout": 0, "amount": str(amount + Decimal('0.001'))}],
            "outputs": [{"address": destination, "amount": str(amount)}],
            "coin_selection": "largest-first-demo",
            "change_address": "bc1q-demo-change",
            "fee_rate_sat_vb": 8,
            "dust_policy": "REJECT_DUST_OUTPUTS",
            "rbf": True,
            "psbt_state": "UNSIGNED",
        }


class EVMAdapter(BlockchainAdapter):
    network = "EVM"

    def generate_address(self, *, client_reference: str, index: int = 0) -> dict:
        result = super().generate_address(client_reference=client_reference, index=index)
        result.update({"address": "0x" + hashlib.sha256(f"{client_reference}|{index}".encode()).hexdigest()[:40], "format": "EIP-55-DEMO"})
        return result

    def estimate_fee(self, *, amount: Decimal, destination: str) -> dict:
        return {"gas_limit": 21000, "max_fee_per_gas_gwei": 20, "max_priority_fee_gwei": 2, "model": "EIP-1559"}

    def build_transaction(self, *, symbol: str, amount: Decimal, destination: str, memo: str | None = None) -> dict:
        return {
            "model": "ACCOUNT",
            "asset": symbol,
            "to": destination,
            "value": str(amount),
            "nonce": 1,
            "chain_id": "CONFIGURED_PER_NETWORK",
            "gas_model": "EIP-1559",
            "max_fee_per_gas_gwei": 20,
            "supports": ["NATIVE", "ERC-20", "ERC-721", "ERC-1155", "ERC-3643"],
            "contract_allowlist_required": True,
        }

    def health(self) -> dict:
        rpc_url = os.getenv("EVM_TESTNET_RPC_URL") or os.getenv("EVM_RPC_URL")
        if not rpc_url:
            return super().health()
        try:
            response = httpx.post(
                rpc_url,
                json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
                timeout=5,
            )
            response.raise_for_status()
            return {"mode": "LIVE_RPC", "healthy": True, "chain_id": response.json().get("result")}
        except Exception as exc:  # noqa: BLE001 - health endpoint should report, not crash
            return {"mode": "LIVE_RPC", "healthy": False, "error": str(exc)}


class SolanaAdapter(BlockchainAdapter):
    network = "SOLANA"

    def estimate_fee(self, *, amount: Decimal, destination: str) -> dict:
        return {"base_fee_lamports": 5000, "priority_fee_micro_lamports": 1000, "compute_unit_limit": 200000}

    def build_transaction(self, *, symbol: str, amount: Decimal, destination: str, memo: str | None = None) -> dict:
        return {
            "model": "SOLANA_ACCOUNTS",
            "asset": symbol,
            "destination_account": destination,
            "lamports_or_token_units": str(amount),
            "recent_blockhash": "demo-recent-blockhash",
            "compute_unit_limit": 200000,
            "priority_fee_micro_lamports": 1000,
            "token_programs": ["SPL_TOKEN", "TOKEN_2022"],
            "associated_token_account": True,
            "commitment": "finalized",
        }


class XRPAdapter(BlockchainAdapter):
    network = "XRPL"

    def estimate_fee(self, *, amount: Decimal, destination: str) -> dict:
        return {"fee_drops": "12", "account_reserve_checked": True}

    def build_transaction(self, *, symbol: str, amount: Decimal, destination: str, memo: str | None = None) -> dict:
        destination_tag = None
        if ":" in destination:
            destination, destination_tag = destination.split(":", 1)
        return {
            "model": "XRPL_ACCOUNT",
            "asset": symbol,
            "Destination": destination,
            "DestinationTag": destination_tag,
            "Amount": str(amount),
            "Sequence": 1,
            "Fee": "12",
            "LastLedgerSequence": "current+20-demo",
            "partial_payment_rejected": True,
            "finality": "VALIDATED_LEDGER",
        }


ADAPTERS = {
    "BTC": BitcoinAdapter(),
    "ETH": EVMAdapter(),
    "AVAX": EVMAdapter(),
    "POL": EVMAdapter(),
    "SOL": SolanaAdapter(),
    "XRP": XRPAdapter(),
}


def get_adapter(symbol: str) -> BlockchainAdapter:
    try:
        return ADAPTERS[symbol]
    except KeyError as exc:
        raise ValueError(f"No adapter configured for {symbol}") from exc
