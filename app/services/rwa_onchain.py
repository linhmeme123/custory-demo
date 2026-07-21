from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RWAAsset, RWAContractDeployment
from app.services.audit import append_audit
from app.services.authz import require_client_admin

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "contracts" / "InstitutionalRWA.sol"
SOLCX_INSTALL_PATH = Path(__file__).resolve().parents[2] / ".solcx"
SOLC_VERSION = "0.8.24"
SOLC_BINARY = SOLCX_INSTALL_PATH / f"solc-v{SOLC_VERSION}"
RWA_DECIMALS = 18


@dataclass(frozen=True)
class EVMSettings:
    rpc_url: str | None
    private_key: str | None
    chain_id: int | None
    explorer_tx_url: str | None
    auto_install_solc: bool


def evm_settings() -> EVMSettings:
    chain_id = os.getenv("EVM_CHAIN_ID")
    return EVMSettings(
        rpc_url=os.getenv("EVM_TESTNET_RPC_URL"),
        private_key=os.getenv("EVM_DEPLOYER_PRIVATE_KEY"),
        chain_id=int(chain_id) if chain_id else None,
        explorer_tx_url=os.getenv("EVM_EXPLORER_TX_URL"),
        auto_install_solc=os.getenv("RWA_AUTO_INSTALL_SOLC", "true").lower() == "true",
    )


def onchain_config_status() -> dict:
    settings = evm_settings()
    return {
        "configured": bool(settings.rpc_url and settings.private_key and settings.chain_id),
        "required_env": ["EVM_TESTNET_RPC_URL", "EVM_DEPLOYER_PRIVATE_KEY", "EVM_CHAIN_ID"],
        "optional_env": ["EVM_EXPLORER_TX_URL", "RWA_AUTO_INSTALL_SOLC"],
        "contract": str(CONTRACT_PATH),
        "compiler_install_path": str(SOLCX_INSTALL_PATH),
        "compiler": f"solc {SOLC_VERSION}",
        "private_key_loaded": bool(settings.private_key),
        "rpc_url_loaded": bool(settings.rpc_url),
        "chain_id": settings.chain_id,
    }


def deploy_rwa_contract(db: Session, *, rwa_asset_id: int, actor_id: int, network: str) -> dict:
    asset = _get_asset_for_admin(db, rwa_asset_id, actor_id)
    existing = db.scalar(select(RWAContractDeployment).where(RWAContractDeployment.rwa_asset_id == asset.id))
    if existing:
        return _deployment_response(existing, "ALREADY_DEPLOYED")

    client, account = _web3_client()
    artifact = _compile_contract()
    contract = client.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    tx = contract.constructor(asset.name, asset.symbol, account.address, asset.reserve_description).build_transaction(
        _base_tx(client, account.address)
    )
    receipt = _sign_send_wait(client, tx, account)
    deployment = RWAContractDeployment(
        rwa_asset_id=asset.id,
        network=network,
        chain_id=evm_settings().chain_id or client.eth.chain_id,
        contract_address=receipt.contractAddress,
        deploy_tx_hash=receipt.transactionHash.hex(),
        deployed_by=actor_id,
    )
    db.add(deployment)
    db.flush()
    append_audit(
        db,
        actor_id=actor_id,
        action="RWA_CONTRACT_DEPLOYED",
        entity_type="RWA_ASSET",
        entity_id=asset.id,
        payload={
            "network": network,
            "chain_id": deployment.chain_id,
            "contract_address": deployment.contract_address,
            "tx_hash": deployment.deploy_tx_hash,
        },
    )
    db.commit()
    return _deployment_response(deployment, "DEPLOYED")


def set_investor_eligibility(
    db: Session,
    *,
    rwa_asset_id: int,
    actor_id: int,
    investor_address: str,
    eligible: bool,
) -> dict:
    asset = _get_asset_for_admin(db, rwa_asset_id, actor_id)
    deployment = _get_deployment(db, asset.id)
    client, account = _web3_client()
    contract = _contract_at(client, deployment.contract_address)
    tx = contract.functions.setInvestorEligibility(
        client.to_checksum_address(investor_address),
        eligible,
    ).build_transaction(_base_tx(client, account.address))
    receipt = _sign_send_wait(client, tx, account)
    append_audit(
        db,
        actor_id=actor_id,
        action="RWA_INVESTOR_ELIGIBILITY_SET",
        entity_type="RWA_ASSET",
        entity_id=asset.id,
        payload={"investor": investor_address, "eligible": eligible, "tx_hash": receipt.transactionHash.hex()},
    )
    db.commit()
    return _tx_response(receipt.transactionHash.hex(), deployment, {"investor_address": investor_address, "eligible": eligible})


def mint_rwa_tokens(db: Session, *, rwa_asset_id: int, actor_id: int, to_address: str, amount_units: Decimal) -> dict:
    asset = _get_asset_for_admin(db, rwa_asset_id, actor_id)
    deployment = _get_deployment(db, asset.id)
    client, account = _web3_client()
    contract = _contract_at(client, deployment.contract_address)
    amount_wei = int(amount_units * (Decimal(10) ** RWA_DECIMALS))
    tx = contract.functions.mint(client.to_checksum_address(to_address), amount_wei).build_transaction(
        _base_tx(client, account.address)
    )
    receipt = _sign_send_wait(client, tx, account)
    append_audit(
        db,
        actor_id=actor_id,
        action="RWA_TOKENS_MINTED",
        entity_type="RWA_ASSET",
        entity_id=asset.id,
        payload={"to": to_address, "amount_units": str(amount_units), "tx_hash": receipt.transactionHash.hex()},
    )
    db.commit()
    return _tx_response(receipt.transactionHash.hex(), deployment, {"to_address": to_address, "amount_units": str(amount_units)})


def rwa_onchain_status(db: Session, *, rwa_asset_id: int) -> dict:
    asset = db.get(RWAAsset, rwa_asset_id)
    if not asset:
        raise HTTPException(404, "RWA asset not found")
    deployment = db.scalar(select(RWAContractDeployment).where(RWAContractDeployment.rwa_asset_id == asset.id))
    if not deployment:
        return {"rwa_asset_id": asset.id, "symbol": asset.symbol, "deployed": False}
    client, _ = _web3_client(require_private_key=False)
    contract = _contract_at(client, deployment.contract_address)
    return {
        **_deployment_response(deployment, "DEPLOYED"),
        "deployed": True,
        "name": contract.functions.name().call(),
        "symbol": contract.functions.symbol().call(),
        "decimals": contract.functions.decimals().call(),
        "total_supply_units": str(Decimal(contract.functions.totalSupply().call()) / (Decimal(10) ** RWA_DECIMALS)),
        "reserve_reference": contract.functions.reserveReference().call(),
        "paused": contract.functions.paused().call(),
    }


def _get_asset_for_admin(db: Session, rwa_asset_id: int, actor_id: int) -> RWAAsset:
    asset = db.get(RWAAsset, rwa_asset_id)
    if not asset:
        raise HTTPException(404, "RWA asset not found")
    require_client_admin(db, actor_id, asset.issuer_client_id)
    return asset


def _get_deployment(db: Session, rwa_asset_id: int) -> RWAContractDeployment:
    deployment = db.scalar(select(RWAContractDeployment).where(RWAContractDeployment.rwa_asset_id == rwa_asset_id))
    if not deployment:
        raise HTTPException(409, "RWA contract has not been deployed yet")
    return deployment


def _web3_client(*, require_private_key: bool = True) -> tuple[Any, Any | None]:
    settings = evm_settings()
    if not settings.rpc_url or not settings.chain_id or (require_private_key and not settings.private_key):
        raise HTTPException(503, {"message": "EVM testnet is not configured", **onchain_config_status()})
    try:
        from web3 import Web3
    except ImportError as exc:
        raise HTTPException(503, "Install web3 first: pip install -r requirements.txt") from exc

    client = Web3(Web3.HTTPProvider(settings.rpc_url))
    if not client.is_connected():
        raise HTTPException(503, "Cannot connect to EVM_TESTNET_RPC_URL")
    if client.eth.chain_id != settings.chain_id:
        raise HTTPException(409, f"RPC chain id {client.eth.chain_id} does not match EVM_CHAIN_ID {settings.chain_id}")
    account = client.eth.account.from_key(settings.private_key) if settings.private_key else None
    return client, account


def _compile_contract() -> dict:
    try:
        import solcx
    except ImportError as exc:
        raise HTTPException(503, "Install py-solc-x first: pip install -r requirements.txt") from exc

    SOLCX_INSTALL_PATH.mkdir(exist_ok=True)
    if not SOLC_BINARY.exists():
        if not evm_settings().auto_install_solc:
            raise HTTPException(503, f"solc {SOLC_VERSION} is not installed in {SOLCX_INSTALL_PATH}; set RWA_AUTO_INSTALL_SOLC=true or install it manually")
        try:
            solcx.install_solc(SOLC_VERSION, solcx_binary_path=SOLCX_INSTALL_PATH)
        except solcx.exceptions.SolcNotInstalled:
            if not SOLC_BINARY.exists():
                raise

    compiled = solcx.compile_standard(
        {
            "language": "Solidity",
            "sources": {"InstitutionalRWA.sol": {"content": CONTRACT_PATH.read_text()}},
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        },
        solc_binary=SOLC_BINARY,
    )
    contract = compiled["contracts"]["InstitutionalRWA.sol"]["InstitutionalRWA"]
    return {"abi": contract["abi"], "bytecode": contract["evm"]["bytecode"]["object"]}


def _contract_at(client: Any, address: str) -> Any:
    return client.eth.contract(address=client.to_checksum_address(address), abi=_compile_contract()["abi"])


def _base_tx(client: Any, sender: str) -> dict:
    tx = {
        "from": sender,
        "nonce": client.eth.get_transaction_count(sender),
        "chainId": evm_settings().chain_id or client.eth.chain_id,
    }
    latest = client.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas")
    if base_fee is not None:
        priority_fee = client.to_wei(2, "gwei")
        tx["maxPriorityFeePerGas"] = priority_fee
        tx["maxFeePerGas"] = int(base_fee * 2 + priority_fee)
    else:
        tx["gasPrice"] = client.eth.gas_price
    return tx


def _sign_send_wait(client: Any, tx: dict, account: Any) -> Any:
    tx.setdefault("gas", int(client.eth.estimate_gas(tx) * 1.2))
    signed = account.sign_transaction(tx)
    raw_transaction = signed.raw_transaction if hasattr(signed, "raw_transaction") else signed.rawTransaction
    tx_hash = client.eth.send_raw_transaction(raw_transaction)
    receipt = client.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status != 1:
        raise HTTPException(409, {"message": "Transaction reverted on testnet", "tx_hash": receipt.transactionHash.hex()})
    return receipt


def _deployment_response(deployment: RWAContractDeployment, status: str) -> dict:
    tx_hash = deployment.deploy_tx_hash
    explorer = evm_settings().explorer_tx_url
    return {
        "status": status,
        "rwa_asset_id": deployment.rwa_asset_id,
        "network": deployment.network,
        "chain_id": deployment.chain_id,
        "contract_address": deployment.contract_address,
        "deploy_tx_hash": tx_hash,
        "explorer_tx_url": f"{explorer.rstrip('/')}/{tx_hash}" if explorer else None,
    }


def _tx_response(tx_hash: str, deployment: RWAContractDeployment, payload: dict) -> dict:
    explorer = evm_settings().explorer_tx_url
    return {
        "status": "CONFIRMED_ON_TESTNET",
        "contract_address": deployment.contract_address,
        "chain_id": deployment.chain_id,
        "tx_hash": tx_hash,
        "explorer_tx_url": f"{explorer.rstrip('/')}/{tx_hash}" if explorer else None,
        "payload": payload,
    }
