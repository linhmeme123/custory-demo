# Institutional Custody Technology Demo

This demo demonstrates:

- client deposit wallets, sweeping and omnibus wallets;
- hot/warm/cold allocation and warm-wallet liquidity top-up;
- asset registry and multi-chain adapter interfaces;
- custody ledger and blockchain reconciliation;
- wallet allowlisting and KYT screening;
- Travel Rule message construction;
- dual-admin withdrawal approval;
- a 2-of-3 MPC signing adapter;
- transaction broadcast/confirmation simulation;
- staking accounting;
- RWA issuance orchestration plus EVM testnet contract deployment/calls and
  custody deposit/withdrawal flow;
- tamper-evident, hash-chained audit logs.

## Important limitation

This is **not** a real custody system. It does not implement real MPC, an HSM, Elliptic, GK8 or production blockchain signing. The mock signer deliberately uses HMAC only to demonstrate the integration boundary. Never use it with real funds or private keys.

Open:

- Swagger: `http://localhost:8000/docs`

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

## RWA testnet setup

The deployer key must hold testnet gas only. Do not use a wallet with mainnet
funds. The backend uses `py-solc-x` to compile Solidity 0.8.24 into the local
`.solcx/` folder; the first deploy can download the compiler when
`RWA_AUTO_INSTALL_SOLC=true`.

Swagger flow:

1. `POST /demo/reset`
2. `POST /rwa/issue`
3. `POST /rwa/{id}/onchain/deploy`
4. `POST /rwa/{id}/onchain/investors`
5. `POST /rwa/{id}/onchain/mint`
6. `GET /rwa/{id}/custody/instructions`
7. `POST /rwa/{id}/custody/deposits/transfer-from-investor`
8. `POST /rwa/{id}/custody/deposits/confirm`
9. `POST /operations/sweep`
10. `POST /operations/rebalance`
11. `POST /wallets/whitelist`
12. `POST /withdrawals`
13. `POST /withdrawals/{id}/review` twice with two different back-office admins
14. `POST /withdrawals/{id}/process`
15. `GET /rwa/{id}/onchain/status`

For the Swagger-only investor deposit helper, use a testnet investor private key
only. It signs an ERC-20 transfer from the investor address into the configured
custody deposit address, then the confirm endpoint observes the token balance
and credits the custody ledger.
