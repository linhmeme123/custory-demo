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

## Traceability về requirement và dự án

| Nhóm yêu cầu | Flow liên quan | Bằng chứng trong dự án |
|---|---|---|
| Institutional onboarding, RBAC Root/Admin/Operator/Viewer | UC-01 | `Client`, `User`, role/scope checks trong `authz.py`; seed users trong `seed.py` |
| AML/KYC/KYT wallet screening | UC-02, UC-03, UC-05 | `kyt.py`, wallet whitelist và deposit/withdrawal gates |
| 80% cold storage policy | UC-04 | `policy.py` và `rebalance_wallets()` |
| Dual-admin withdrawal approval | UC-05 | `Approval` unique approver constraint và `approve_withdrawal()` |
| HSM/MPC key management boundary | UC-05, UC-06 | `MockMPCSigner`, quorum 2-of-3; demo HMAC không phải MPC thật |
| Multi-chain BTC/ETH/SOL/AVAX/XRP/MATIC(POL) | UC-06 | Chain adapters và tests cho UTXO/EVM/Solana/XRPL |
| Staking infrastructure | UC-07 | `StakingPosition` và `create_staking_position()` |
| RWA tokenization | UC-08 | `InstitutionalRWA.sol`, `rwa.py`, `rwa_onchain.py` |
| Audit trail và reporting | UC-09, UC-10 | `AuditLog`, hash chaining trong `audit.py`, dashboard/reconciliation views |
| Incident response | UC-11 | Requirement có yêu cầu; chưa có workflow trong demo |

## Ranh giới demo và production

1. `MockMPCSigner` dùng HMAC cho minh họa, không phải MPC/HSM và không được dùng với tiền thật.
2. KYT là provider mock, không gọi Elliptic/CertiK/Chainalysis thật.
3. Hot/warm/cold và sweep chủ yếu là wallet projection; chưa có key ceremony, air gap hoặc on-chain transfer thật cho tài sản thường.
4. Blockchain adapters mô phỏng build/broadcast/finality, ngoại trừ RWA có khả năng chạy EVM testnet khi cấu hình.
5. Audit hash chain giúp phát hiện chỉnh sửa theo chuỗi, nhưng production vẫn cần WORM storage, access controls, retention, external anchoring và SIEM.
6. Onboarding, KYB, regulator reporting, case management, incident response và đa ngôn ngữ UI chưa được triển khai trong demo.
