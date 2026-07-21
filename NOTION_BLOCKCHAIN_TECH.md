# Blockchain Technology – IDGX Custody

> Mục tiêu của phần Notion này không phải liệt kê mọi thuật ngữ blockchain. Mục tiêu là trả lời ba câu hỏi: **hệ thống cần làm gì, demo chứng minh được gì, và còn thiếu gì trước production**.

## 0. Executive summary

- BDACS/GK8 cung cấp wallet/key/signing backbone.
- Tech Partner xây custody control plane cho Việt Nam: ledger, policy, approval, compliance, API, reporting và các adapter.
- PoC nên chứng minh end-to-end flow trước; không tự xây MPC thật hoặc kết nối tiền thật.
- Demo repo đi kèm cho thấy một withdrawal từ Operator đến blockchain qua toàn bộ lớp kiểm soát.

## 1. End-to-end custody flow

### Câu hỏi cần trả lời
- Client thao tác ở đâu?
- Ai được tạo, duyệt và ký giao dịch?
- Số dư client được ghi ở đâu?
- KYT/Travel Rule tham gia lúc nào?
- GK8 tham gia từ bước nào?

### Flow

```text
Client Dashboard
→ RBAC & Approval
→ Ledger & Policy
→ KYT/AML & Travel Rule
→ GK8/MPC signing
→ Blockchain
→ Confirmation & Reconciliation
```

### Demo
Chạy từng endpoint nghiệp vụ trực tiếp trong Swagger tại `/docs`.

---

# PHẦN A — CORE CUSTODY ENGINE

## 2. Key management: MPC, HSM và GK8

### Vai trò
- Bảo vệ quyền ký blockchain.
- Không để application backend giữ raw private key.
- Thực thi signing policy và recovery.

### Trong dự án
- GK8/Galaxy là provider chính.
- Tech Partner xây adapter, request signing, status handling và reconciliation.

### Demo
`app/services/signer.py` mô phỏng threshold 2-of-3.

### Kết luận khả thi
- **Khả thi về kiến trúc:** có interface rõ ràng.
- **Chưa chứng minh production:** cần sandbox/API, key ceremony, recovery, SLA và security review của GK8.

## 3. Wallet architecture: deposit, omnibus, hot/warm/cold

### Vai trò
- Deposit wallet nhận diện client.
- Sweeping gom tài sản về operational layer.
- Hot phục vụ giao dịch nhanh.
- Warm là lớp đệm thanh khoản có kiểm soát.
- Cold giữ phần lớn tài sản.

### Demo
- `/deposits/simulate`
- `/operations/sweep`
- `/operations/rebalance`
- Withdrawal 10 BTC sẽ tự top-up hot từ warm nếu thiếu.

### Chỉ số cần theo dõi
- Cold-storage ratio.
- Hot exposure.
- Số lần cold operation.
- Withdrawal SLA.

## 4. HD wallet và address management

### Vai trò
- Sinh nhiều deposit address theo client/account.
- Quản lý address rotation, xpub/watch-only và network-specific memo/tag.

### PoC hiện tại
- Demo dùng address giả định để tập trung vào control plane.

### PoC tiếp theo
- Bitcoin testnet derivation.
- EVM address derivation.
- XRP destination tag và Solana token account mapping.

---

# PHẦN B — MULTI-CHAIN CONNECTIVITY

## 5. Blockchain adapter framework

### Vai trò
Chuẩn hóa các hàm:
- validate address;
- build transaction;
- estimate fee;
- sign request;
- broadcast;
- confirmations;
- health check.

### Demo
`app/services/chain.py` có adapter riêng cho BTC, EVM, Solana và XRP.

### Lợi ích
Thêm blockchain mới mà không sửa ledger, approval hoặc compliance flow.

## 6. Tích hợp từng blockchain

| Nhóm | Điểm khác biệt cần chứng minh |
|---|---|
| Bitcoin | UTXO, coin selection, change, fee, confirmations, PSBT |
| Ethereum/EVM | nonce, gas EIP-1559, token contract, event logs |
| Solana | accounts, instructions, recent blockhash, SPL token |
| XRP | sequence, validated ledger, destination tag |
| Avalanche/Polygon | EVM common layer nhưng network/finality/bridge riêng |

### Demo hiện tại
Transaction envelope khác nhau theo adapter.

### Demo testnet nên làm tiếp
Ưu tiên EVM Sepolia trước, sau đó Bitcoin regtest/testnet và Solana devnet.

## 7. Node, RPC, indexer và monitoring

### Vai trò
- Đọc block/transaction.
- Phát hiện deposit.
- Theo dõi confirmation/reorg.
- Đối chiếu dữ liệu từ nhiều provider.

### Demo
`GET /infrastructure/rpc-health`.
Nếu đặt `EVM_TESTNET_RPC_URL`, health check gọi `eth_chainId`; nếu không thì chạy mock mode.

### Production gap
- Multi-RPC failover.
- Historical rescan.
- Reorg rollback.
- Node version management.

## 8. Asset registry và allowlisting

### Vai trò
Mỗi asset phải có network, decimals, contract/mint, confirmation, trạng thái deposit/withdrawal và risk policy.

### Demo
Asset registry được seed cho BTC, ETH, SOL, AVAX, XRP và POL.

---

# PHẦN C — TRANSACTION CONTROL & ACCOUNTING

## 9. Transaction orchestration và policy engine

### Vai trò
Quản lý state machine:

```text
PENDING_APPROVAL → APPROVED → SIGNING → COMPLETED
```

Áp dụng:
- whitelist;
- daily limit;
- KYT threshold;
- dual approval;
- network/asset enablement;
- idempotency và failure recovery.

### Demo
`app/services/withdrawals.py` và `policy.py`.

## 10. Custody ledger và reconciliation

### Vai trò
- Ghi beneficial balance của từng client.
- Tách available, pending, locked và staked.
- Đối chiếu tổng liability với on-chain custody wallets.

### Demo
`GET /reconciliation` phải trả `MATCH` hoặc difference bằng 0.

### Production gap
- Double-entry journal đầy đủ.
- PostgreSQL HA.
- Intraday và end-of-day reconciliation.
- Exception case management.

---

# PHẦN D — COMPLIANCE

## 11. KYT/AML, wallet screening và Travel Rule

### Vai trò
- Screen source/destination.
- Chặn sanctions/hacker/mixer exposure.
- Lưu decision evidence.
- Trao đổi originator/beneficiary data giữa VASP.

### Demo
- `MockKYTProvider` đánh risk theo address/risk score.
- Ví chứa `hacker` hoặc `mixer` bị chuyển sang review.
- Withdrawal tới exchange tạo Travel Rule object.

### Production gap
- Elliptic sandbox/API.
- Local watchlists.
- Case-management workflow.
- Travel Rule provider/protocol.

---

# PHẦN E — VALUE-ADDED SERVICES

## 12. Staking và yield

### Vai trò
- Chuyển available balance sang staked.
- Tích hợp validator.
- Theo dõi activation, rewards, fees, unstaking và slashing.

### Demo
`POST /staking` stake 64 ETH và cập nhật ledger.

### Production gap
- Galaxy/validator API.
- Reward reconciliation.
- Slashing liability và legal consent.

## 13. RWA tokenization

### Vai trò
- Asset/legal registry.
- Investor eligibility.
- Mint/burn, transfer restriction, freeze và redemption.

### Demo
- `POST /rwa/issue` cho orchestration.
- `POST /rwa/{id}/onchain/deploy` compile và deploy `contracts/InstitutionalRWA.sol` lên EVM testnet.
- `POST /rwa/{id}/onchain/investors` cho on-chain allowlist.
- `POST /rwa/{id}/onchain/mint` cho on-chain mint.
- `GET /rwa/{id}/onchain/status` đọc trạng thái contract từ testnet.

### Production gap
- Legal enforceability.
- Contract audit.
- Custodian/registrar responsibilities.
- Corporate actions và reserve verification.

---

# PHẦN F — SECURITY & FEASIBILITY

## 14. Security architecture

### Các lớp
- IAM/MFA/PAM.
- API security và mTLS.
- Secrets management.
- Key-provider isolation.
- Immutable/tamper-evident logs.
- SIEM, alerting và incident response.
- Pen test và smart-contract audit.

### Demo
Audit log dùng hash chain để phát hiện chỉnh sửa lịch sử.

## 15. Feasibility matrix

| Hạng mục | PoC hiện tại | Cần vendor/production proof | Đánh giá |
|---|---|---|---|
| RBAC/approval | Có | IAM/PAM/MFA | Khả thi cao |
| Ledger/reconciliation | Có | Double-entry + HA | Khả thi cao |
| Hot/warm/cold policy | Có | GK8 wallet mapping | Khả thi cao |
| Multi-chain adapters | Có mock | Testnet + GK8 support matrix | Khả thi, cần kiểm thử chain |
| MPC/HSM | Interface mock | GK8 sandbox/key ceremony | Phụ thuộc vendor |
| KYT/AML | Rule mock | Elliptic data/API | Phụ thuộc vendor/data |
| Travel Rule | Message mock | Provider + legal rule | Chưa chốt |
| Staking | Ledger mock | Validator API | Khả thi, có counterparty risk |
| RWA | API + EVM testnet contract | Legal design + audit | Kỹ thuật khả thi, pháp lý quyết định |

## 16. Template bắt buộc cho mỗi trang Notion

Mỗi công nghệ chỉ nên có 7 mục:

1. **Vấn đề cần giải quyết**
2. **Nó nằm ở đâu trong architecture**
3. **Input/Output**
4. **Flow thực tế**
5. **Demo và cách chạy**
6. **Kết quả feasibility**
7. **Production gaps / câu hỏi cần BDACS trả lời**

Cách này giúp Notion không biến thành glossary lan man.
