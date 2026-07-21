# Feasibility test plan

## Mức 1 — Functional simulation

Mục tiêu: chứng minh business flow và ranh giới component, không cần vendor credential.

- RBAC và dual approval.
- Wallet tiers và rebalancing.
- Ledger và reconciliation.
- KYT/policy decision.
- Travel Rule payload.
- Signer/chain adapter interfaces.
- Staking và RWA off-chain orchestration.

**Trạng thái:** repo này đáp ứng.

## Mức 2 — Public testnet / local chain

Mục tiêu: chứng minh transaction thật nhưng không dùng tiền thật.

1. EVM Sepolia: build/sign/broadcast và receipt.
2. Bitcoin regtest hoặc testnet: UTXO/PSBT/confirmations.
3. Solana devnet: SOL/SPL transfer.
4. XRP testnet: destination tag và validated ledger.
5. RWA EVM testnet: deploy contract, investor allowlist, mint và read status.

**Tiêu chí pass:**
- idempotent retry;
- no duplicate broadcast;
- fee estimation trong ngưỡng;
- confirmation/reorg handling;
- ledger vẫn reconcile.

## Mức 3 — Vendor sandbox

Mục tiêu: chứng minh tích hợp sản phẩm thực.

- GK8 wallet/address creation.
- GK8 signing request và webhook/polling.
- Elliptic address/transaction screening.
- Validator/staking API.
- Travel Rule provider.

**Phụ thuộc:** NDA, API docs, credential, support contacts và vendor SLA.

## Mức 4 — Production readiness

- Threat model.
- Key ceremony và recovery drill.
- HA/DR, RTO/RPO.
- SOC/ISO control mapping.
- Pen test và smart-contract audit.
- Load/soak test.
- Incident simulation.
- Legal/compliance sign-off.
