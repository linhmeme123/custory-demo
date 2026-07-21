# Institutional Custody Technology Demo

A runnable, educational control-plane demo for explaining an institutional digital-asset custody architecture to product and engineering leaders.

It demonstrates:

- Client/Back-office RBAC;
- institutional onboarding context;
- client deposit wallets, sweeping and omnibus wallets;
- hot/warm/cold allocation and warm-wallet liquidity top-up;
- asset registry and multi-chain adapter interfaces;
- custody ledger and blockchain reconciliation;
- wallet allowlisting and mock KYT screening;
- Travel Rule message construction;
- dual-admin withdrawal approval;
- a mock 2-of-3 MPC signing adapter;
- transaction broadcast/confirmation simulation;
- staking accounting;
- RWA issuance orchestration plus EVM testnet contract deployment/calls;
- tamper-evident, hash-chained audit logs.

## Important limitation

This is **not** a real custody system. It does not implement real MPC, an HSM, Elliptic, GK8 or production blockchain signing. The mock signer deliberately uses HMAC only to demonstrate the integration boundary. Never use it with real funds or private keys.

Open:

- Swagger: `http://localhost:8000/docs` (`/` redirects here)
- Blockchain technology showcase: `http://localhost:8000/technology/showcase`

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Tests

```bash
pytest -q
```

## Demo story for a leader

1. Reset data: ABC Fund owns 100 BTC and 1,000 ETH.
2. Simulate a clean 20 BTC deposit.
3. Sweep the client deposit wallet into the omnibus layer.
4. Rebalance to 5% hot, 15% warm and 80% cold.
5. The client Operator creates a 10 BTC withdrawal to a whitelisted exchange account.
6. KYT and policy checks run; Travel Rule data is constructed.
7. Two different back-office admins approve it.
8. If hot liquidity is insufficient, warm wallet tops it up.
9. The mock GK8/MPC adapter signs and the chain adapter broadcasts.
10. Ledger and wallet totals reconcile.
11. A 64 ETH staking position and an RWA issuance are demonstrated.
12. The technology showcase exposes chain-specific evidence for Bitcoin PSBT,
    EVM/EIP-1559, Solana token programs, XRP tags/finality, MPC/GK8 and KYT.

## Blockchain feasibility endpoints

- `GET /technology/catalog`: maps all 12 requested technology groups to the
  evidence level implemented by this repository.
- `GET /technology/showcase`: builds observable, chain-specific unsigned
  transaction envelopes, fee estimates and demo deposit addresses.
- `GET /infrastructure/rpc-health`: shows whether adapters use mock mode or a
  configured live EVM RPC.
- `POST /rwa/{id}/onchain/deploy`: compiles and deploys `contracts/InstitutionalRWA.sol`
  to an EVM testnet when RPC and deployer credentials are configured.
- `POST /rwa/{id}/onchain/investors`: allowlists or removes a testnet investor.
- `POST /rwa/{id}/onchain/mint`: mints RWA units to an eligible investor.
- `GET /rwa/{id}/onchain/status`: reads name, symbol, reserve reference,
  paused state and total supply from the deployed contract.

The showcase labels every result as `FUNCTIONAL`, `MOCK`, `ENVELOPE_MOCK`,
`LEDGER_MOCK`, `TESTNET_CAPABLE` or `BOUNDARY_ONLY`; it must not be interpreted
as vendor certification or production readiness.

## RWA testnet setup

Copy `.env.example` to `.env` or export the values in your shell:

```bash
export EVM_TESTNET_RPC_URL="https://..."
export EVM_CHAIN_ID=11155111
export EVM_DEPLOYER_PRIVATE_KEY="0x..."
export EVM_EXPLORER_TX_URL="https://sepolia.etherscan.io/tx"
```

The deployer key must hold testnet gas only. Do not use a wallet with mainnet
funds. The backend uses `py-solc-x` to compile Solidity 0.8.24 into the local
`.solcx/` folder; the first deploy can download the compiler when
`RWA_AUTO_INSTALL_SOLC=true`.

Suggested Swagger flow:

1. `POST /demo/reset`
2. `POST /rwa/issue`
3. `POST /rwa/{id}/onchain/deploy`
4. `POST /rwa/{id}/onchain/investors`
5. `POST /rwa/{id}/onchain/mint`
6. `GET /rwa/{id}/onchain/status`

## Map to production vendors

| Demo component | Production replacement |
|---|---|
| `MockMPCSigner` | GK8/Galaxy MPC or offline-vault API |
| `MockKYTProvider` | Elliptic/Chainalysis API and case management |
| Mock chain broadcast | Self-hosted nodes or managed RPC plus GK8 broadcast |
| SQLite | PostgreSQL with HA, backups and immutable event/audit storage |
| Simple role headers/IDs | Enterprise IAM, MFA, PAM and signed service identities |
| RWA testnet contract | Audited contracts plus legal registry and regulator-approved workflow |

## Official learning sources

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.x: https://docs.sqlalchemy.org/
- OpenZeppelin Contracts: https://docs.openzeppelin.com/contracts
- Ethereum token standards: https://ethereum.org/developers/docs/standards/tokens/
- Hardhat: https://hardhat.org/docs/getting-started
- pytest: https://docs.pytest.org/
