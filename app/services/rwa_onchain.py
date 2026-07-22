from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, Deposit, RWAAsset, RWAContractDeployment, Wallet
from app.services.audit import append_audit
from app.services.authz import require_client_admin, require_client_transaction_role
from app.services.ledger import custody_onchain_total, get_client_balance, wallet_by_kind

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
        _, account = _web3_client()
        custody_asset = _ensure_custody_asset(db, asset, existing, asset.issuer_client_id, account.address)
        db.commit()
        return {
            **_deployment_response(existing, "ALREADY_DEPLOYED"),
            "custody": _custody_response(db, asset, existing, custody_asset, account.address),
        }

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
    custody_asset = _ensure_custody_asset(db, asset, deployment, asset.issuer_client_id, account.address)
    append_audit(
        db,
        actor_id=actor_id,
        action="RWA_CUSTODY_ENABLED",
        entity_type="RWA_ASSET",
        entity_id=asset.id,
        payload={
            "asset_symbol": custody_asset.symbol,
            "contract_address": deployment.contract_address,
            "custody_address": account.address,
            "mode": "AUTO_AFTER_DEPLOY",
        },
    )
    db.commit()
    return {
        **_deployment_response(deployment, "DEPLOYED"),
        "custody": _custody_response(db, asset, deployment, custody_asset, account.address),
    }


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


def rwa_custody_instructions(db: Session, *, rwa_asset_id: int) -> dict:
    rwa = _get_rwa_or_404(db, rwa_asset_id)
    deployment = _get_deployment(db, rwa.id)
    _, account = _web3_client()
    asset = db.scalar(select(Asset).where(Asset.symbol == rwa.symbol))
    return {
        "rwa_asset_id": rwa.id,
        "asset_symbol": rwa.symbol,
        "custody_enabled": asset is not None,
        "contract_address": deployment.contract_address,
        "deposit_address": account.address,
        "deposit_asset": rwa.symbol,
        "next_step": f"Transfer {rwa.symbol} on testnet to deposit_address, then call POST /rwa/{rwa.id}/custody/deposits/confirm.",
    }


def confirm_rwa_custody_deposit(db: Session, *, rwa_asset_id: int, client_id: int, actor_id: int) -> dict:
    """Observe testnet token balance and credit any newly received amount."""
    require_client_transaction_role(db, actor_id, client_id)
    rwa = _get_rwa_or_404(db, rwa_asset_id)
    deployment = _get_deployment(db, rwa.id)
    asset = db.scalar(select(Asset).where(Asset.symbol == rwa.symbol))
    if not asset:
        raise HTTPException(409, "Enable custody for this RWA before confirming deposits")
    client, account = _web3_client()
    custody_address = account.address
    observed = _token_balance_units(client, deployment.contract_address, custody_address)
    projected = custody_onchain_total(db, asset.id)
    amount = observed - projected
    if amount <= 0:
        return {
            "status": "NO_NEW_DEPOSIT",
            "asset": asset.symbol,
            "custody_address": custody_address,
            "observed_onchain_balance": str(observed),
            "wallet_projection_total": str(projected),
        }
    deposit_wallet = wallet_by_kind(db, asset.id, "DEPOSIT", client_id)
    balance = get_client_balance(db, client_id, asset.id)
    deposit_wallet.balance = Decimal(deposit_wallet.balance) + amount
    balance.available = Decimal(balance.available) + amount
    tx_hash = "0x" + hashlib.sha256(
        f"{rwa.id}|{client_id}|{custody_address}|{observed}|{projected}".encode()
    ).hexdigest()
    row = Deposit(
        client_id=client_id,
        asset_id=asset.id,
        amount=amount,
        source_address="EVM_TESTNET_TOKEN_TRANSFER",
        created_by=actor_id,
        state="CONFIRMED",
        confirmations=asset.confirmations_required,
        required_confirmations=asset.confirmations_required,
        kyt_score=0,
        tx_hash=tx_hash,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    append_audit(
        db,
        actor_id=actor_id,
        action="RWA_DEPOSIT_CONFIRMED_ONCHAIN",
        entity_type="DEPOSIT",
        entity_id=row.id,
        payload={
            "asset": asset.symbol,
            "amount": str(amount),
            "contract_address": deployment.contract_address,
            "custody_address": custody_address,
            "observed_onchain_balance": str(observed),
        },
    )
    db.commit()
    return {
        "id": row.id,
        "status": row.state,
        "asset": asset.symbol,
        "amount": str(amount),
        "custody_address": custody_address,
        "observed_onchain_balance": str(observed),
        "deposit_wallet_balance": str(deposit_wallet.balance),
        "client_available": str(balance.available),
    }


def transfer_rwa_to_custody_from_investor(
    db: Session,
    *,
    rwa_asset_id: int,
    investor_private_key: str,
    amount_units: Decimal,
) -> dict:
    """Testnet-only helper so the full investor deposit can be driven from Swagger."""
    rwa = _get_rwa_or_404(db, rwa_asset_id)
    deployment = _get_deployment(db, rwa.id)
    client, custody_account = _web3_client()
    investor_account = client.eth.account.from_key(investor_private_key)
    contract = _contract_at(client, deployment.contract_address)
    if not contract.functions.eligibleInvestor(client.to_checksum_address(custody_account.address)).call():
        raise HTTPException(409, "Custody address is not eligible on the RWA contract")
    amount_wei = int(amount_units * (Decimal(10) ** RWA_DECIMALS))
    tx = contract.functions.transfer(custody_account.address, amount_wei).build_transaction(
        _base_tx(client, investor_account.address)
    )
    receipt = _sign_send_wait(client, tx, investor_account)
    explorer = evm_settings().explorer_tx_url
    tx_hash = receipt.transactionHash.hex()
    return {
        "status": "CONFIRMED_ON_TESTNET",
        "rwa_asset_id": rwa.id,
        "asset_symbol": rwa.symbol,
        "from_investor": investor_account.address,
        "to_custody_deposit_address": custody_account.address,
        "amount_units": str(amount_units),
        "tx_hash": tx_hash,
        "explorer_tx_url": f"{explorer.rstrip('/')}/{tx_hash}" if explorer else None,
        "next_step": f"Call POST /rwa/{rwa.id}/custody/deposits/confirm to credit the custody ledger.",
    }


def is_rwa_custody_asset(db: Session, asset_symbol: str) -> bool:
    return db.scalar(select(RWAAsset).where(RWAAsset.symbol == asset_symbol.upper())) is not None


def transfer_rwa_from_custody(db: Session, *, asset_symbol: str, to_address: str, amount_units: Decimal) -> dict:
    rwa = db.scalar(select(RWAAsset).where(RWAAsset.symbol == asset_symbol.upper()))
    if not rwa:
        raise HTTPException(404, f"RWA asset {asset_symbol} not found")
    deployment = _get_deployment(db, rwa.id)
    client, account = _web3_client()
    contract = _contract_at(client, deployment.contract_address)
    checksum_to = client.to_checksum_address(to_address)
    if not contract.functions.eligibleInvestor(checksum_to).call():
        raise HTTPException(400, "Destination address is not eligible on the RWA contract")
    amount_wei = int(amount_units * (Decimal(10) ** RWA_DECIMALS))
    tx = contract.functions.transfer(checksum_to, amount_wei).build_transaction(_base_tx(client, account.address))
    receipt = _sign_send_wait(client, tx, account)
    return {
        "tx_hash": receipt.transactionHash.hex(),
        "status": "CONFIRMED_ON_TESTNET",
        "network_payload": {
            "model": "EVM_ERC20_RWA_TRANSFER",
            "contract_address": deployment.contract_address,
            "from": account.address,
            "to": checksum_to,
            "amount_units": str(amount_units),
            "chain_id": deployment.chain_id,
        },
    }


def _get_asset_for_admin(db: Session, rwa_asset_id: int, actor_id: int) -> RWAAsset:
    asset = _get_rwa_or_404(db, rwa_asset_id)
    require_client_admin(db, actor_id, asset.issuer_client_id)
    return asset


def _get_rwa_or_404(db: Session, rwa_asset_id: int) -> RWAAsset:
    asset = db.get(RWAAsset, rwa_asset_id)
    if not asset:
        raise HTTPException(404, "RWA asset not found")
    return asset


def _get_deployment(db: Session, rwa_asset_id: int) -> RWAContractDeployment:
    deployment = db.scalar(select(RWAContractDeployment).where(RWAContractDeployment.rwa_asset_id == rwa_asset_id))
    if not deployment:
        raise HTTPException(409, "RWA contract has not been deployed yet")
    return deployment


def _ensure_wallets(db: Session, asset: Asset, client_id: int, custody_address: str) -> None:
    rows = {
        ("DEPOSIT", client_id): (custody_address, f"{asset.symbol} testnet deposit"),
        ("OMNIBUS", None): (f"logical:{asset.symbol}:omnibus", f"{asset.symbol} omnibus"),
        ("HOT", None): (f"logical:{asset.symbol}:hot", f"{asset.symbol} hot"),
        ("WARM", None): (f"logical:{asset.symbol}:warm", f"{asset.symbol} warm"),
        ("COLD", None): (f"logical:{asset.symbol}:cold", f"{asset.symbol} cold"),
    }
    for (kind, wallet_client_id), (address, label) in rows.items():
        query = select(Wallet).where(Wallet.asset_id == asset.id, Wallet.kind == kind)
        if wallet_client_id is None:
            query = query.where(Wallet.client_id.is_(None))
        else:
            query = query.where(Wallet.client_id == wallet_client_id)
        if not db.scalar(query):
            db.add(
                Wallet(
                    client_id=wallet_client_id,
                    asset_id=asset.id,
                    kind=kind,
                    address=address,
                    label=label,
                    status="ACTIVE",
                )
            )
    get_client_balance(db, client_id, asset.id)
    db.flush()


def _ensure_custody_asset(
    db: Session,
    rwa: RWAAsset,
    deployment: RWAContractDeployment,
    client_id: int,
    custody_address: str,
) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.symbol == rwa.symbol))
    if not asset:
        asset = Asset(
            symbol=rwa.symbol,
            network=f"EVM:{deployment.network}",
            decimals=RWA_DECIMALS,
            confirmations_required=12,
        )
        db.add(asset)
        db.flush()
    _ensure_wallets(db, asset, client_id, custody_address)
    return asset


def _custody_response(
    db: Session,
    rwa: RWAAsset,
    deployment: RWAContractDeployment,
    asset: Asset,
    custody_address: str,
) -> dict:
    return {
        "status": "CUSTODY_ENABLED",
        "rwa_asset_id": rwa.id,
        "asset_symbol": asset.symbol,
        "contract_address": deployment.contract_address,
        "custody_deposit_address": custody_address,
        "wallets": [
            {"kind": wallet.kind, "address": wallet.address, "balance": str(wallet.balance)}
            for wallet in db.scalars(select(Wallet).where(Wallet.asset_id == asset.id)).all()
        ],
        "next_step": f"Transfer {asset.symbol} to custody_deposit_address, then call POST /rwa/{rwa.id}/custody/deposits/confirm.",
    }


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


def _token_balance_units(client: Any, contract_address: str, owner: str) -> Decimal:
    contract = _contract_at(client, contract_address)
    raw_balance = contract.functions.balanceOf(client.to_checksum_address(owner)).call()
    return Decimal(raw_balance) / (Decimal(10) ** RWA_DECIMALS)


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
