# Hướng dẫn test demo Custody Blockchain

> File này là tài liệu theo dõi chính cho phần feasibility test. Mỗi khi thêm
> hoặc sửa một module phục vụ demo, danh sách **Thay đổi source code** bên
> dưới phải được cập nhật để người đọc repo biết chính xác thay đổi nằm ở đâu.

## 1. Phạm vi cần chứng minh

| Demo | Luồng cần test | Tiêu chí pass |
|---|---|---|
| Demo 1 | Deposit → confirmation → sweep → rebalance | Deposit chỉ được ghi `available` sau đủ confirmation; sweep không thay đổi liability; hot/warm/cold đạt 5%/15%/80% |
| Demo 2 | Withdrawal → dual approval → MPC signing → broadcast | Hai back-office admin khác nhau phải approve; thiếu approval hoặc thiếu MPC quorum phải bị từ chối |
| Demo 3 | KYT risk decision | Ví/source HIGH risk phải bị hold hoặc `REVIEW_REQUIRED`, không được dùng để withdrawal |
| Demo 4 | Multi-chain adapter | BTC, EVM, Solana và XRP tạo đúng transaction envelope riêng và trả kết quả broadcast |
| Demo 5 | Reconciliation | Chain observation, wallet projection và client liability khớp; sai lệch phải trả `BREAK` |
| Demo 6 | RWA EVM testnet | Issue RWA off-chain, deploy contract, allowlist investor, mint token và đọc status on-chain |

## 2. Tạo môi trường test local

Yêu cầu: Python 3.9 trở lên. Python 3.12 được khuyến nghị.

Chạy từ thư mục gốc của dự án:

```bash
cd /Users/hoangthuylinh/Documents/custody-tech-demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Kiểm tra môi trường:

```bash
python --version
python -c "import fastapi, sqlalchemy, pytest; print('Test environment OK')"
```

## 3. Lệnh chạy test

### Chạy toàn bộ test suite

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -q
```

Chạy có tên từng test và thông tin chi tiết hơn:

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -vv
```

### Chạy riêng Demo 1

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -q tests/test_demo_1_deposit_wallets.py
```

### Chạy riêng Demo 2

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -q tests/test_demo_2_withdrawal_approval.py
```

### Chạy riêng Demo 3

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -q tests/test_demo_3_kyt.py
```

### Chạy riêng Demo 4

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -q tests/test_demo_4_multichain.py
```

### Chạy riêng Demo 5

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -q tests/test_demo_5_reconciliation.py
```

### Chạy một test case cụ thể

```bash
DATABASE_URL=sqlite:///./custody_test.db python -m pytest -vv \
  tests/test_demo_2_withdrawal_approval.py::test_two_distinct_approvals_are_required_before_signing
```

## 4. Chạy API và test từng flow trong Swagger

Terminal thứ nhất:

```bash
source .venv/bin/activate
DATABASE_URL=sqlite:///./custody_demo.db uvicorn app.main:app --reload
```

Các URL hữu ích:

- Swagger/OpenAPI: `http://localhost:8000/docs` (`/` tự chuyển hướng tới đây)
- Reconciliation: `http://localhost:8000/reconciliation`
- RPC/adapter health: `http://localhost:8000/infrastructure/rpc-health`
- Audit log: `http://localhost:8000/audit`
- RWA testnet config: `http://localhost:8000/rwa/onchain/config`

Luồng RWA testnet trong Swagger:

1. `POST /rwa/issue`
2. `POST /rwa/{id}/onchain/deploy`
3. `POST /rwa/{id}/onchain/investors`
4. `POST /rwa/{id}/onchain/mint`
5. `GET /rwa/{id}/onchain/status`

Trước khi deploy lên testnet, cần export:

```bash
export EVM_TESTNET_RPC_URL="https://..."
export EVM_CHAIN_ID=11155111
export EVM_DEPLOYER_PRIVATE_KEY="0x..."
export EVM_EXPLORER_TX_URL="https://sepolia.etherscan.io/tx"
```

Private key này chỉ dùng ví testnet có ít gas, không dùng ví mainnet.

## 5. Kết quả mong đợi

Khi toàn bộ test pass, kết quả cuối sẽ tương tự:

```text
...................                                              [100%]
19 passed
```

Số lượng test có thể tăng khi bổ sung thêm case. Điều kiện quan trọng là không
có `failed` hoặc `error`.

## 6. Thay đổi source code phục vụ test

### File đã thêm

- `app/services/technology_demo.py`
  - Ánh xạ đủ 12 nhóm công nghệ trong requirement sang bằng chứng demo.
  - Tạo showcase cho MPC/GK8 boundary, KYT và transaction envelope từng chain.
- `tests/test_technology_showcase.py`
  - Kiểm tra catalog đủ 12 nhóm công nghệ.
  - Kiểm tra bằng chứng PSBT, EIP-1559, Token-2022 và XRP destination tag.
- `app/services/rwa_onchain.py`
  - Compile `contracts/InstitutionalRWA.sol`, deploy lên EVM testnet, allowlist
    investor, mint token và đọc trạng thái contract.
- `tests/test_rwa_onchain.py`
  - Kiểm tra endpoint config on-chain hiện trong Swagger mà không yêu cầu RPC thật.
  - Kiểm tra RWA catalog đã chuyển sang mức `TESTNET_CAPABLE`.

- `app/services/reconciliation.py`
  - Tách reconciliation thành service riêng.
  - Cho phép truyền số dư quan sát độc lập từ blockchain/RPC mock.
  - Phân biệt `observed_chain_total`, `wallet_projection_total` và
    `client_liability_total`.
- `tests/test_demo_1_deposit_wallets.py`
  - Test confirmation, sweeping, rebalancing và quyền back-office.
- `tests/test_demo_2_withdrawal_approval.py`
  - Test dual approval, chống approve trùng, process trước approval và reject.
- `tests/test_demo_3_kyt.py`
  - Test high-risk deposit và high-risk destination.
- `tests/test_demo_4_multichain.py`
  - Test BTC, ETH, AVAX, POL, SOL, XRP adapter và MPC quorum.
- `tests/test_demo_5_reconciliation.py`
  - Test trạng thái `MATCH` và phát hiện `BREAK`.
- `TESTING_GUIDE.md`
  - File hướng dẫn hiện tại.

### File đã sửa

- `app/models.py`
  - Thêm model `Deposit` có trạng thái, confirmation, KYT score và tx hash.
  - Dùng `Optional[T]` cho SQLAlchemy mapped fields để chạy được trên Python 3.9;
    không dùng `T | None` vì SQLAlchemy phải đánh giá annotation lúc runtime.
- `app/schemas.py`
  - Thêm request cập nhật deposit confirmation và request process withdrawal có actor.
- `app/services/deposits.py`
  - Tách deposit detection khỏi deposit confirmation.
  - Chỉ chuyển pending sang available khi đủ confirmation.
- `app/services/authz.py`
  - Thêm kiểm tra quyền cho back-office wallet/broadcast operation.
- `app/services/wallets.py`
  - Bắt buộc quyền back-office khi sweep hoặc rebalance.
- `app/services/withdrawals.py`
  - Kiểm tra destination thuộc đúng client.
  - Bắt buộc actor back-office khi ký và broadcast.
- `app/main.py`
  - Thêm endpoint confirm deposit.
  - Process withdrawal nhận actor để authorization.
  - Thêm `/technology/catalog` và `/technology/showcase` để test riêng trong Swagger.
  - Thêm nhóm endpoint `/rwa/{id}/onchain/*` cho EVM testnet.
- `app/services/chain.py`
  - Mở rộng interface với address generation, balance, fee estimation và transaction status.
  - Làm rõ envelope riêng cho Bitcoin/PSBT, EVM, Solana và XRP Ledger.
## 7. Mock và tích hợp thật

Các test hiện tại chứng minh kiến trúc và control flow, không chứng minh vendor
hoặc public blockchain thực sự hoạt động:

- `MockMPCSigner` chỉ chứng minh threshold/quorum boundary, không phải GK8/MPC thật.
- `MockKYTProvider` chỉ chứng minh policy decision, không gọi Elliptic.
- Adapter broadcast tạo transaction hash mô phỏng, không gửi tài sản thật.
- Independent chain balance trong Demo 5 là dữ liệu RPC mock do test cung cấp.
- Riêng RWA có thể deploy/call contract thật trên EVM testnet khi cấu hình
  `EVM_TESTNET_RPC_URL`, `EVM_CHAIN_ID` và `EVM_DEPLOYER_PRIVATE_KEY`.

Giai đoạn tiếp theo nên tạo một nhóm test integration riêng, có marker
`integration`, để kết nối GK8 sandbox, Elliptic sandbox, Bitcoin regtest,
EVM testnet, Solana devnet và XRP testnet. Không nên làm các unit test hiện tại
phụ thuộc mạng vì sẽ khiến kết quả feasibility không ổn định.
