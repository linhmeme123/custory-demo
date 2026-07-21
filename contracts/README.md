# RWA smart-contract demo

`InstitutionalRWA.sol` demonstrates:

- ERC-20 fungible units;
- role-separated minting and compliance;
- investor allowlisting;
- transfer restriction;
- emergency pause;
- a reserve-document reference.

## Quick test in Remix

1. Open Remix IDE.
2. Create `InstitutionalRWA.sol` and paste the contract.
3. Compile with Solidity 0.8.24 or a compatible newer 0.8.x compiler.
4. Deploy with name, symbol, admin address and a demo reserve reference.
5. Add a second account through `setInvestorEligibility`.
6. Mint to that account, transfer between eligible accounts, then pause and verify transfers fail.

## Backend testnet flow

The FastAPI demo can compile and deploy this contract directly when these
environment variables are configured:

```bash
EVM_TESTNET_RPC_URL=https://...
EVM_CHAIN_ID=11155111
EVM_DEPLOYER_PRIVATE_KEY=0x...
EVM_EXPLORER_TX_URL=https://sepolia.etherscan.io/tx
```

Use Swagger in this order:

1. `POST /rwa/issue`
2. `POST /rwa/{id}/onchain/deploy`
3. `POST /rwa/{id}/onchain/investors`
4. `POST /rwa/{id}/onchain/mint`
5. `GET /rwa/{id}/onchain/status`

This contract is educational and has not been independently audited. It does not make an off-chain asset legally enforceable by itself.
