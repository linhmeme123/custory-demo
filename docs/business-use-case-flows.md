# IDGX Custody — Use Case Flows

## 1. Quy ước và phạm vi

- **Client-side:** Root, Admin, Operator, Viewer của tổ chức sử dụng dịch vụ.
- **Custody-side:** Back-office Admin, Custody Operations, Compliance, Auditor.
- Các tỷ lệ, ngưỡng và quorum: `hot 5% / warm 15% / cold 80%`, KYT high-risk từ `80`, và phê duyệt rút tiền bởi `2` người khác nhau.

| ID | Business use case | Ghi chú chính |
|---|---|---|
| UC-01 | Onboarding tổ chức và phân quyền | Có mô hình Client, User, role và scope; onboarding/KYB và mời người dùng chưa có workflow |
| UC-02 | Khai báo, sàng lọc và whitelist ví nhận | Có RBAC, KYT và trạng thái `WHITELISTED`/`REVIEW_REQUIRED`; xử lý manual review chưa hoàn chỉnh |
| UC-03 | Nhận tiền, xác nhận và ghi có | Có pending, số confirmation theo tài sản, chống ghi có lặp và KYT đầu vào |
| UC-04 | Sweep và phân bổ hot/warm/cold | Sweep về omnibus và tái cân bằng 5/15/80; cold storage vật lý là mô phỏng |
| UC-05 | Rút tiền có kiểm soát | Whitelist, KYT, hạn mức, khóa số dư, Travel Rule, dual approval, quorum signing, broadcast |
| UC-06 | Xử lý lệnh đa chuỗi | Có BTC, EVM, SOL, XRP; RPC/signing production chưa có |
| UC-07 | Staking và quản lý lợi suất | Có tạo vị thế và ledger accounting; chưa có approval, validator execution, reward/unstake lifecycle |
| UC-08 | RWA issuance, investor eligibility và custody | Có contract testnet, allowlist, mint, custody deposit/withdrawal; pháp lý/reserve operations là off-chain |
| UC-09 | Reconciliation và xử lý chênh lệch | Có đối chiếu 3 số liệu và phát hiện break; chưa có case-management/remediation workflow |
| UC-10 | Audit, báo cáo và điều tra | Có hash-chained audit log; dashboard/reporting và evidence workflow chưa đầy đủ |
| UC-11 | Xử lý sự cố an toàn tài sản | Requirement đòi hỏi incident response; demo chưa có orchestration |

## 2. Bản đồ nghiệp vụ tổng thể

![Bản đồ nghiệp vụ tổng thể](diagrams/full-flow-custody.drawio.png)

## 3. UC-01 — Onboarding tổ chức và thiết lập quyền truy cập

- **Mục tiêu:** chỉ tổ chức đã hoàn tất KYB/KYC và được cấu hình đúng chính sách mới có thể sử dụng custody.
- **UBO — Ultimate Beneficial Owner:** chủ sở hữu hưởng lợi cuối cùng

![Bản đồ onboarding](diagrams/onboarding.drawio.png) 

```mermaid
flowchart TD
    A["Tổ chức nộp hồ sơ onboarding"] --> B["Business/Compliance kiểm tra pháp nhân, UBO, giấy phép và mục đích sử dụng"]
    B --> C{"Hồ sơ đầy đủ và chấp nhận được?"}
    C -- "Không" --> D["Yêu cầu bổ sung hoặc từ chối onboarding"]
    D --> E["Ghi nhận lý do và đóng hồ sơ"]

    C -- "Có" --> F["Chấm điểm rủi ro tổ chức và xác định mức due diligence"]
    F --> G{"Nằm trong risk appetite và phạm vi sandbox?"}
    G -- "Không" --> H["Escalate Compliance/Legal để quyết định ngoại lệ"]
    H --> I{"Ngoại lệ được duyệt?"}
    I -- "Không" --> E
    I -- "Có" --> J["Phê duyệt khách hàng"]
    G -- "Có" --> J

    J --> K["Tạo client entity và gán Client Root đầu tiên"]
    K --> L["Root mời Admin, Operator và Viewer"]
    L --> M["Áp dụng maker-checker, scope theo client và nguyên tắc least privilege"]
    M --> N["Bật danh mục tài sản/mạng được phép"]
    N --> O["Cấu hình hạn mức, số confirmation, chính sách whitelist và phê duyệt"]
    O --> P["Sinh/đăng ký ví nạp riêng cho từng client và asset"]
    P --> Q["Kiểm tra readiness: quyền, ví, policy, monitoring, báo cáo"]
    Q --> R{"Readiness đạt?"}
    R -- "Có" --> T["Kích hoạt khách hàng và bắt đầu giao dịch"]
    S --> Q
    R -- "Không" --> S["Khắc phục cấu hình và kiểm tra lại"]
```

**Điểm kiểm soát nghiệp vụ**

1. Client user không được nhìn hoặc thao tác dữ liệu của client khác.
2. Root/Admin quản trị người dùng và whitelist; Operator tạo giao dịch; Viewer chỉ đọc.
3. Quyền back-office phải tách khỏi quyền client. Production nên tách thêm Approver, Wallet Operator và Broadcaster; demo hiện dùng chung `BACKOFFICE_ADMIN`.
4. Phần KYB/KYC, invitation, MFA, user lifecycle và readiness gate là **TO-BE**; demo hiện seed sẵn client/user.

## 4. UC-02 — Khai báo, KYT và whitelist ví nhận

**Mục tiêu:** chỉ cho phép rút tiền đến đúng ví, đúng tài sản và đã qua kiểm soát rủi ro.

```mermaid
flowchart TD
    A["Client Root/Admin khai báo ví nhận"] --> B["Nhập asset/network, địa chỉ, nhãn và quan hệ sở hữu"]
    B --> C{"Người thao tác có quyền quản trị client?"}
    C -- "Không" --> D["Từ chối và ghi audit truy cập không hợp lệ"]
    C -- "Có" --> E["Chuẩn hóa và kiểm tra định dạng địa chỉ theo network"]
    E --> F{"Địa chỉ hợp lệ, chưa trùng và đúng network?"}
    F -- "Không" --> G["Từ chối, yêu cầu sửa thông tin"]
    F -- "Có" --> H["Sàng lọc KYT/AML địa chỉ"]
    H --> I{"Risk score từ 80 hoặc có exposure cấm?"}

    I -- "Có" --> J["Đặt trạng thái REVIEW_REQUIRED"]
    J --> K["Compliance mở case và thu thập nguồn tiền/mục đích/chủ sở hữu"]
    K --> L{"Manual review chấp thuận?"}
    L -- "Không" --> M["REJECTED/BLOCKED; không được dùng để rút"]
    L -- "Có" --> N["Compliance phê duyệt ngoại lệ có thời hạn"]
    N --> O["WHITELISTED"]

    I -- "Không" --> O
    O --> P["Áp dụng cooling period hoặc second approval nếu policy yêu cầu"]
    P --> Q["Ví sẵn sàng làm beneficiary của lệnh rút"]

    Q --> R["Theo dõi thay đổi risk signal định kỳ"]
    R --> S{"Rủi ro tăng hoặc thông tin ví thay đổi?"}
    S -- "Có" --> T["Tạm khóa whitelist và sàng lọc lại"]
    T --> H
    S -- "Không" --> R
```

**Trạng thái đề xuất:** `DRAFT → SCREENING → WHITELISTED`, hoặc `SCREENING → REVIEW_REQUIRED → WHITELISTED/REJECTED`, và `WHITELISTED → SUSPENDED` khi tái sàng lọc phát hiện rủi ro.

**Khoảng trống production:** demo đã có RBAC, KYT và `REVIEW_REQUIRED`, nhưng chưa có manual-review resolution, cooling period, re-screening, expiry và network-format validation hoàn chỉnh.

## 5. UC-03 — Nhận tài sản, xác nhận on-chain và ghi có

**Mục tiêu:** phát hiện tiền vào nhưng chỉ làm tăng số dư khả dụng sau khi vượt qua KYT và đạt finality theo từng tài sản.

```mermaid
sequenceDiagram
    autonumber
    participant C as Khách hàng
    participant P as Custody Platform
    participant K as KYT/AML
    participant N as Blockchain/Indexer
    participant L as Custody Ledger
    participant O as Custody Operations

    C->>P: Lấy địa chỉ nạp riêng theo client và asset
    C->>N: Chuyển tài sản đến địa chỉ nạp
    N-->>P: Phát hiện giao dịch và số confirmation hiện tại
    P->>P: Kiểm tra asset/network, địa chỉ đích và idempotency theo tx hash
    P->>K: Sàng lọc địa chỉ nguồn và exposure

    alt High risk hoặc exposure bị cấm
        K-->>P: HIGH RISK
        P->>P: Đặt hold / không ghi có
        P-->>O: Mở cảnh báo Compliance
    else Risk chấp nhận được
        K-->>P: LOW/MEDIUM
        P->>L: Tăng pending, trạng thái CONFIRMING
        loop Cho đến khi đạt required confirmations
            N-->>P: Cập nhật confirmations
            P->>P: Giữ funds ở pending
        end
        P->>P: Xác nhận đạt finality theo asset
        P->>L: Giảm pending, tăng available đúng một lần
        P->>P: Tăng balance của deposit wallet
        P-->>C: Thông báo nạp tiền thành công
        P-->>O: Deposit đủ điều kiện sweep
    end
```

```mermaid
stateDiagram-v2
    [*] --> DETECTED
    DETECTED --> HELD: KYT high risk
    DETECTED --> CONFIRMING: KYT accepted
    CONFIRMING --> CONFIRMING: Chưa đủ confirmations
    CONFIRMING --> CONFIRMED: Đạt required confirmations
    CONFIRMED --> SWEPT: Custody Operations sweep
    HELD --> CONFIRMING: Compliance release [TO-BE]
    HELD --> REJECTED: Compliance reject [TO-BE]
    CONFIRMED --> REVERSED: Chain reorg/invalid deposit [TO-BE]
```

**Quy tắc quan trọng**

1. Phát hiện giao dịch chỉ làm tăng `pending`; không được tăng `available` trước finality.
2. Số confirmation là cấu hình theo asset: demo seed BTC 3, ETH/AVAX 12, SOL/XRP 1, POL 128.
3. Confirmation chỉ tăng theo giá trị lớn nhất đã quan sát; gọi xác nhận lặp sau khi `CONFIRMED` không được ghi có thêm lần nữa.
4. KYT high-risk bị chặn trước khi tạo nghĩa vụ phải trả cho client.
5. Production cần xử lý reorg, wrong-network/wrong-token, memo/tag thiếu, chain outage, late detection và manual release của deposit hold.

## 6. UC-04 — Sweep và quản lý thanh khoản hot/warm/cold

**Mục tiêu:** thu gom tài sản khỏi ví nạp, duy trì thanh khoản vận hành và đảm bảo tối thiểu 80% nằm trong tầng cold theo requirement.

```mermaid
flowchart TD
    A["Deposit đã CONFIRMED"] --> B["Custody Operations chọn asset để sweep"]
    B --> C{"Người thao tác có quyền back-office?"}
    C -- "Không" --> D["Từ chối và ghi audit"]
    C -- "Có" --> E["Tổng hợp số dư các deposit wallet của asset"]
    E --> F{"Có số dư cần sweep?"}
    F -- "Không" --> G["Kết thúc, không phát sinh dịch chuyển"]
    F -- "Có" --> H["Chuyển toàn bộ số dư projection về omnibus"]
    H --> I["Tính tổng tài sản ở omnibus + hot + warm + cold"]
    I --> J["Tính target allocation: hot 5%, warm 15%, cold 80%"]
    J --> K["Tạo kế hoạch điều chuyển nội bộ"]
    K --> L{"Policy/approval cho cold transfer đạt? [TO-BE]"}
    L -- "Không" --> M["Giữ trạng thái pending và mở cảnh báo"]
    L -- "Có" --> N["Thực hiện điều chuyển và cập nhật wallet projection"]
    N --> O{"Cold ratio đạt tối thiểu 80%?"}
    O -- "Không" --> P["Escalate Treasury/Compliance"]
    O -- "Có" --> Q["Ghi audit và chuyển sang reconciliation"]
    P --> Q
```

### Bổ sung thanh khoản khi rút tiền

```mermaid
flowchart LR
    A["Lệnh rút đã được phê duyệt"] --> B{"Hot balance đủ?"}
    B -- "Có" --> F["Cho phép tạo giao dịch ký"]
    B -- "Không" --> C["Tính phần thiếu"]
    C --> D["Chuyển từ Warm sang Hot tối đa có thể"]
    D --> E{"Đã đủ?"}
    E -- "Có" --> F
    E -- "Không" --> G["Chuyển phần còn thiếu từ Cold sang Hot"]
    G --> H{"Đã đủ?"}
    H -- "Có" --> F
    H -- "Không" --> I["Dừng xử lý: thiếu thanh khoản vận hành"]
    F --> J["Ghi audit LIQUIDITY_TOP_UP nếu có điều chuyển"]
```

**Lưu ý:** demo cập nhật số dư wallet projection trong database. Production cần workflow ký/chuyển thật, approval riêng cho cold withdrawal, time lock, air-gapped ceremony, fee reserve và reconciliation với chain độc lập.

## 7. UC-05 — Rút tài sản có dual approval và ký quorum

**Mục tiêu:** ngăn rút sai người, sai ví hoặc vượt policy; tách người tạo lệnh, người phê duyệt và người thực thi.

```mermaid
flowchart TD
    A["Client Root/Admin/Operator tạo yêu cầu rút"] --> B{"User thuộc đúng client và có transaction role?"}
    B -- "Không" --> X1["Từ chối do RBAC"]
    B -- "Có" --> C["Kiểm tra asset, destination thuộc client và đúng asset"]
    C --> D{"Destination đang WHITELISTED?"}
    D -- "Không" --> X2["Từ chối; yêu cầu hoàn tất wallet review"]
    D -- "Có" --> E["Sàng lọc KYT destination tại thời điểm tạo lệnh"]
    E --> F{"KYT từ 80?"}
    F -- "Có" --> X3["Chặn và mở manual compliance investigation"]
    F -- "Không" --> G{"Available balance đủ?"}
    G -- "Không" --> X4["Từ chối do thiếu số dư"]
    G -- "Có" --> H{"Số tiền trong daily limit?"}
    H -- "Không" --> X5["Từ chối hoặc chuyển enhanced approval [TO-BE]"]
    H -- "Có" --> I["Nếu ví ngoài: tạo Travel Rule message"]
    I --> J["Chuyển amount từ available sang pending"]
    J --> K["Trạng thái PENDING_APPROVAL"]

    K --> L["Back-office Admin A review"]
    L --> M{"Quyết định A?"}
    M -- "Reject" --> R["REJECTED; trả pending về available"]
    M -- "Approve" --> N["Chờ Back-office Admin B khác người A"]
    N --> O{"Quyết định B?"}
    O -- "Reject" --> R
    O -- "Approve" --> P["APPROVED"]
    N -. "A tự duyệt lần hai" .-> X6["Chặn duplicate approver"]

    P --> Q["Custody Operator kiểm tra/bổ sung hot liquidity"]
    Q --> S{"Hot liquidity đủ?"}
    S -- "Không" --> X7["Dừng và mở treasury exception"]
    S -- "Có" --> T["Tạo transaction envelope theo chain"]
    T --> U["Ký với quorum 2-of-3 MPC/HSM"]
    U --> V{"Đạt quorum và policy ký?"}
    V -- "Không" --> X8["Dừng; không broadcast"]
    V -- "Có" --> W["Broadcast và theo dõi finality"]
    W --> Y{"Chain xác nhận thành công?"}
    Y -- "Không/timeout" --> X9["Giữ trạng thái xử lý; retry/replace/cancel theo chain [TO-BE]"]
    Y -- "Có" --> Z["Giảm hot wallet và xóa pending liability"]
    Z --> Z1["COMPLETED; lưu tx hash và audit evidence"]
```

```mermaid
stateDiagram-v2
    [*] --> PENDING_APPROVAL
    PENDING_APPROVAL --> REJECTED: Bất kỳ approver nào reject
    PENDING_APPROVAL --> PENDING_APPROVAL: Mới có 1 approval
    PENDING_APPROVAL --> APPROVED: 2 approver khác nhau approve
    APPROVED --> SIGNING: Custody Operator bắt đầu xử lý
    SIGNING --> BROADCASTING: Quorum ký đạt
    BROADCASTING --> COMPLETED: Finality đạt
    SIGNING --> FAILED: Signing/policy failure [TO-BE]
    BROADCASTING --> EXCEPTION: Timeout/reorg/revert [TO-BE]
    EXCEPTION --> BROADCASTING: Retry/replace được duyệt [TO-BE]
    REJECTED --> [*]
    COMPLETED --> [*]
```

**Phân tách nhiệm vụ đề xuất**

| Giai đoạn | Vai trò tạo/kiểm soát | Không nên kiêm nhiệm |
|---|---|---|
| Khởi tạo lệnh | Client Root/Admin/Operator | Back-office approver của chính lệnh |
| Phê duyệt 1 | Back-office Approver A | Approver B |
| Phê duyệt 2 | Back-office Approver B | Approver A |
| Chuẩn bị/broadcast | Wallet Operator/Broadcaster | Người giữ đủ quorum ký một mình |
| Giám sát và hậu kiểm | Auditor/Compliance | Người sửa dữ liệu giao dịch |

## 8. UC-06 — Xử lý lệnh chuyển tài sản đa chuỗi

**Mục tiêu:** giữ nguyên một quy trình phê duyệt kinh doanh, nhưng áp dụng đúng quy tắc giao dịch/finality của từng blockchain.

```mermaid
flowchart TD
    A["Lệnh chuyển đã qua business approval"] --> B["Xác định asset, network, amount và beneficiary"]
    B --> C{"Loại blockchain?"}

    C -- "Bitcoin" --> D["Chọn UTXO, tính fee, change, dust và RBF"]
    D --> E["Tạo PSBT chưa ký"]

    C -- "EVM: ETH/AVAX/POL/RWA" --> F["Kiểm tra chain ID, nonce, gas và contract allowlist"]
    F --> G["Tạo native/ERC transaction chưa ký"]

    C -- "Solana" --> H["Kiểm tra account/ATA, recent blockhash, compute và token program"]
    H --> I["Tạo Solana transaction chưa ký"]

    C -- "XRP Ledger" --> J["Kiểm tra destination tag, sequence, fee và last ledger"]
    J --> K["Tạo XRPL transaction chưa ký"]

    E --> L["Policy engine kiểm tra transaction envelope"]
    G --> L
    I --> L
    K --> L

    L --> M{"Envelope khớp business instruction?"}
    M -- "Không" --> N["Chặn ký và mở exception"]
    M -- "Có" --> O["MPC/HSM quorum ký"]
    O --> P["Broadcast qua node/RPC phù hợp"]
    P --> Q["Theo dõi confirmation/finality theo network"]
    Q --> R{"Đạt finality?"}
    R -- "Không" --> S["Theo dõi tiếp hoặc xử lý retry/replacement [TO-BE]"]
    S --> Q
    R -- "Có" --> T["Hoàn tất business transaction và reconciliation"]
```

**Ranh giới kiến trúc:** người dùng nghiệp vụ không cần biết adapter hoặc endpoint nào được gọi. Họ chỉ cần thấy cùng một lệnh rút, cùng policy/approval, trạng thái thực thi rõ ràng và bằng chứng finality nhất quán.

## 9. UC-07 — Staking và quản lý lợi suất

**Mục tiêu:** cho phép tổ chức đưa tài sản đủ điều kiện vào staking mà vẫn tách biệt available, staked, reward và withdrawal/unbonding.

```mermaid
flowchart TD
    A["Client tạo yêu cầu staking"] --> B{"User có transaction role đúng client?"}
    B -- "Không" --> X1["Từ chối RBAC"]
    B -- "Có" --> C{"Asset được phép staking?"}
    C -- "Không" --> X2["Từ chối: asset không hỗ trợ"]
    C -- "Có: ETH/SOL/AVAX trong demo" --> D{"Available balance đủ?"}
    D -- "Không" --> X3["Từ chối do thiếu số dư"]
    D -- "Có" --> E["Chọn validator/provider và điều khoản reward"]
    E --> F["Đánh giá validator risk, slashing, concentration và lock-up [TO-BE]"]
    F --> G{"Policy/approval đạt? [TO-BE]"}
    G -- "Không" --> X4["Từ chối hoặc yêu cầu thay validator"]
    G -- "Có" --> H["Chuyển amount từ available sang staked"]
    H --> I["Tạo staking position ACTIVE"]
    I --> J["Thực hiện staking on-chain/provider [TO-BE]"]
    J --> K["Theo dõi reward, validator health và slashing [TO-BE]"]
    K --> L["Ghi nhận reward vào ledger và báo cáo [TO-BE]"]
    L --> M{"Client yêu cầu unstake?"}
    M -- "Không" --> K
    M -- "Có" --> N["Tạo unbonding request và áp dụng approval [TO-BE]"]
    N --> O["Chờ unbonding/finality"]
    O --> P["Giảm staked, tăng available, hạch toán reward/fee"]
    P --> Q["Đóng position và reconciliation"]
```

**AS-IS:** dự án mới thực hiện đến bước tạo `ACTIVE` position và chuyển số dư `available → staked`. Phần provider execution, reward accrual, slashing, unbonding và settlement là **TO-BE**.

## 10. UC-08 — RWA issuance, investor eligibility và custody lifecycle

**Mục tiêu:** phát hành tài sản token hóa có kiểm soát, chỉ cho nhà đầu tư đủ điều kiện nắm giữ/chuyển nhượng, đồng thời đưa token vào custody ledger chuẩn.

```mermaid
flowchart TD
    A["Issuer hoàn tất onboarding và được cấp quyền RWA"] --> B["Chuẩn bị hồ sơ tài sản cơ sở, pháp lý, valuation và reserve reference"]
    B --> C{"Legal/Compliance phê duyệt cấu trúc trong sandbox? [TO-BE]"}
    C -- "Không" --> X1["Từ chối hoặc yêu cầu tái cấu trúc"]
    C -- "Có" --> D["Client Admin tạo RWA master record"]
    D --> E["Triển khai smart contract lên EVM testnet"]
    E --> F["Gán Admin, Minter, Compliance và Pauser roles"]
    F --> G["Tự động tạo asset custody và ví Deposit/Omnibus/Hot/Warm/Cold"]
    G --> H["Đưa custody address vào danh sách eligible investor"]

    H --> I["Nhà đầu tư nộp hồ sơ eligibility/KYC"]
    I --> J{"Compliance chấp thuận investor?"}
    J -- "Không" --> X2["Không allowlist; không thể mint/transfer"]
    J -- "Có" --> K["Đặt investor address = eligible"]
    K --> L["Minter mint token cho investor trong approved allocation"]
    L --> M["Investor nắm giữ/chuyển token theo transfer restriction"]

    M --> N{"Investor muốn đưa token vào custody?"}
    N -- "Có" --> O["Investor chuyển token đến custody deposit address"]
    O --> P["Platform đọc token balance on-chain độc lập"]
    P --> Q["Tính new deposit = observed balance - wallet projection"]
    Q --> R{"Có lượng mới lớn hơn 0?"}
    R -- "Không" --> S["NO_NEW_DEPOSIT; không ghi có"]
    R -- "Có" --> T["Ghi có deposit wallet và client available"]
    T --> U["Sweep/rebalance và reconciliation như tài sản custody khác"]

    M --> V{"Investor/client muốn rút RWA khỏi custody?"}
    V -- "Có" --> W["Whitelist destination và xác nhận destination vẫn eligible"]
    W --> Y["Đi qua flow rút tiền: policy + 2 approval + quorum signing"]
    Y --> Z["Smart contract transfer từ custody đến eligible destination"]
    Z --> Z1["Finality, ledger settlement và audit"]
```

### Kiểm soát vòng đời RWA

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> APPROVED: Legal/Compliance approval [TO-BE]
    APPROVED --> DEPLOYED: Contract deployment
    DEPLOYED --> LIVE: Roles, reserve reference và custody readiness đạt
    LIVE --> PAUSED: Emergency/Compliance pause
    PAUSED --> LIVE: Remediation và controlled unpause
    LIVE --> REDEMPTION: Issuer mở kỳ mua lại [TO-BE]
    REDEMPTION --> BURNED: Token về custody và burn
    BURNED --> CLOSED: Nghĩa vụ off-chain đã thanh toán [TO-BE]
```

**Điểm cần giữ ngoài smart contract:** quyền sở hữu pháp lý, kiểm chứng reserve, valuation, corporate actions, cash settlement, regulatory reporting và phê duyệt sandbox. Contract demo chỉ chứng minh role separation, eligible investor, transfer restriction, pause, mint/burn và reserve reference.

## 11. UC-09 — Reconciliation và xử lý chênh lệch

**Mục tiêu:** chứng minh tài sản quan sát độc lập trên chain khớp cả wallet projection lẫn tổng nghĩa vụ với client.

```mermaid
flowchart TD
    A["Khởi chạy reconciliation theo lịch hoặc sau sự kiện trọng yếu"] --> B["Lấy observed on-chain balance từ node/indexer độc lập"]
    B --> C["Tính wallet projection: Deposit + Omnibus + Hot + Warm + Cold"]
    C --> D["Tính client liability: Available + Pending + Locked + Staked"]
    D --> E["Tính Diff A = Observed - Wallet Projection"]
    E --> F["Tính Diff B = Observed - Client Liability"]
    F --> G{"Diff A = 0 và Diff B = 0?"}

    G -- "Có" --> H["MATCH"]
    H --> I["Lưu evidence, timestamp và audit result"]
    I --> J["Đóng kỳ đối chiếu / đưa vào báo cáo"]

    G -- "Không" --> K["BREAK"]
    K --> L{"Loại chênh lệch?"}
    L -- "Observed khác projection" --> M["Điều tra missed tx, fee, reorg, wrong address hoặc RPC/indexer"]
    L -- "Projection khớp observed nhưng khác liability" --> N["Điều tra ledger posting, duplicate/missing credit, pending/locked/staked"]
    L -- "Cả hai khác" --> O["Điều tra đồng thời chain và ledger; ưu tiên bảo toàn tài sản"]

    M --> P["Mở reconciliation case và gán owner [TO-BE]"]
    N --> P
    O --> P
    P --> Q["Tạm dừng nghiệp vụ có rủi ro theo asset/client [TO-BE]"]
    Q --> R["Thu thập tx, block, wallet movements, approvals và audit chain"]
    R --> S["Đề xuất rescan, fee posting hoặc controlled adjustment"]
    S --> T{"Adjustment được maker-checker phê duyệt? [TO-BE]"}
    T -- "Không" --> P
    T -- "Có" --> U["Thực hiện remediation, không sửa/xóa audit cũ"]
    U --> V["Chạy lại reconciliation"]
    V --> G
```

**AS-IS:** dự án tính đủ ba tổng và hai difference, trả `MATCH` hoặc `BREAK`. Case management, freeze, maker-checker adjustment, evidence package và SLA xử lý break là **TO-BE**.

## 12. UC-10 — Audit trail, báo cáo và điều tra

**Mục tiêu:** mọi quyết định và biến động tài sản phải truy nguyên được; sửa một bản ghi cũ phải làm đứt chuỗi bằng chứng.

```mermaid
flowchart TD
    A["Phát sinh business event"] --> B["Xác định actor, action, entity và payload chuẩn hóa"]
    B --> C["Đọc hash của audit entry gần nhất"]
    C --> D["Tính entry hash từ prev hash + actor + action + entity + payload"]
    D --> E["Ghi audit entry bất biến theo thứ tự"]
    E --> F["Business transaction commit"]

    F --> G["Auditor/Compliance yêu cầu báo cáo hoặc điều tra"]
    G --> H["Lọc theo client, asset, user, transaction, thời gian và trạng thái [TO-BE]"]
    H --> I["Xây dựng timeline: request → checks → approvals → signing → chain result"]
    I --> J["Kiểm tra liên tục của hash chain"]
    J --> K{"Chuỗi hash hợp lệ?"}
    K -- "Có" --> L["Xuất evidence/report và lưu dấu người truy cập"]
    K -- "Không" --> M["Kích hoạt security incident và bảo toàn bằng chứng"]

    L --> N{"Có exception hoặc giao dịch đáng ngờ?"}
    N -- "Không" --> O["Đóng review"]
    N -- "Có" --> P["Mở compliance/reconciliation case"]
```

**Các report business nên có trong Q3 target:** asset position theo client/entity, pending deposits, withdrawal approval aging, whitelist/KYT exceptions, hot-warm-cold ratio, reconciliation breaks, RWA investor/holding activity, staking position/reward, user access và audit integrity.

## 13. UC-11 — Xử lý sự cố an toàn tài sản (TO-BE)

**Mục tiêu:** khi có dấu hiệu compromise, ưu tiên ngăn thất thoát, bảo toàn bằng chứng, đáp ứng nghĩa vụ thông báo và chỉ mở lại sau reconciliation độc lập.

```mermaid
flowchart TD
    A["Phát hiện cảnh báo: key, account, withdrawal, chain hoặc data integrity"] --> B["Triage và phân loại severity"]
    B --> C{"Có nguy cơ thất thoát hoặc truy cập trái phép?"}
    C -- "Không" --> D["Tạo case thường, theo dõi SLA và điều tra"]
    C -- "Có" --> E["Kích hoạt incident commander"]
    E --> F["Tạm dừng withdrawal/signing hoặc pause RWA theo phạm vi"]
    F --> G["Khóa session/quyền bị nghi ngờ và cô lập integration"]
    G --> H["Bảo toàn log, audit hash chain, signing evidence và chain data"]
    H --> I["Xác định tài sản/client/network bị ảnh hưởng"]
    I --> J["Đối chiếu on-chain, wallet projection và liability"]
    J --> K{"Có giao dịch trái phép hoặc thiếu hụt?"}
    K -- "Có" --> L["Escalate Legal/Compliance, regulator, insurer và đối tác chain analytics"]
    K -- "Không" --> M["Khắc phục control gap và tăng monitoring"]
    L --> N["Thực hiện containment/recovery theo playbook và thẩm quyền"]
    M --> N
    N --> O["Thông báo khách hàng/regulator theo nghĩa vụ và mức ảnh hưởng"]
    O --> P["Independent validation, reconciliation và security sign-off"]
    P --> Q{"Đủ điều kiện mở lại?"}
    Q -- "Không" --> N
    Q -- "Có" --> R["Controlled resume theo asset/client/network"]
    R --> S["Post-incident review, corrective actions và board report"]
```

## 14. Các trạng thái dữ liệu

| Aggregate | Trạng thái |
|---|---|
| Client | `ONBOARDING`, `UNDER_REVIEW`, `ACTIVE`, `SUSPENDED`, `OFFBOARDED` |
| User | `INVITED`, `ACTIVE`, `LOCKED`, `DISABLED` |
| Wallet beneficiary | `DRAFT`, `SCREENING`, `REVIEW_REQUIRED`, `WHITELISTED`, `SUSPENDED`, `REJECTED` |
| Deposit | `DETECTED`, `HELD`, `CONFIRMING`, `CONFIRMED`, `SWEPT`, `REVERSED` |
| Withdrawal | `PENDING_APPROVAL`, `REJECTED`, `APPROVED`, `SIGNING`, `BROADCASTING`, `COMPLETED`, `EXCEPTION`, `FAILED` |
| Staking position | `REQUESTED`, `APPROVED`, `BONDING`, `ACTIVE`, `UNBONDING`, `CLOSED`, `SLASHED` |
| RWA | `DRAFT`, `APPROVED`, `DEPLOYED`, `LIVE`, `PAUSED`, `REDEMPTION`, `BURNED`, `CLOSED` |
| Reconciliation case | `OPEN`, `INVESTIGATING`, `PENDING_ADJUSTMENT_APPROVAL`, `REMEDIATED`, `CLOSED` |
| Security incident | `TRIAGE`, `CONTAINED`, `INVESTIGATING`, `RECOVERING`, `MONITORING`, `CLOSED` |

