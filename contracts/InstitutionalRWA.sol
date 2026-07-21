// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Educational RWA token for testnet feasibility demos. It includes
/// ERC-20 style balances, role-separated controls, investor allowlisting,
/// transfer restriction and emergency pause. Legal ownership, reserve
/// verification and regulatory approval remain off-chain responsibilities.
contract InstitutionalRWA {
    bytes32 public constant DEFAULT_ADMIN_ROLE = 0x00;
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");
    bytes32 public constant COMPLIANCE_ROLE = keccak256("COMPLIANCE_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");

    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    string public reserveReference;
    bool public paused;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    mapping(address => bool) public eligibleInvestor;
    mapping(bytes32 => mapping(address => bool)) public hasRole;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);
    event InvestorEligibilityChanged(address indexed investor, bool eligible);
    event ReserveReferenceChanged(string newReference);
    event Paused(address indexed account);
    event Unpaused(address indexed account);

    modifier onlyRole(bytes32 role) {
        require(hasRole[role][msg.sender], "missing role");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "token is paused");
        _;
    }

    constructor(
        string memory name_,
        string memory symbol_,
        address admin_,
        string memory reserveReference_
    ) {
        require(admin_ != address(0), "admin is zero address");
        name = name_;
        symbol = symbol_;
        reserveReference = reserveReference_;
        eligibleInvestor[admin_] = true;
        _grantRole(DEFAULT_ADMIN_ROLE, admin_);
        _grantRole(MINTER_ROLE, admin_);
        _grantRole(COMPLIANCE_ROLE, admin_);
        _grantRole(PAUSER_ROLE, admin_);
    }

    function grantRole(bytes32 role, address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _grantRole(role, account);
    }

    function revokeRole(bytes32 role, address account) external onlyRole(DEFAULT_ADMIN_ROLE) {
        hasRole[role][account] = false;
        emit RoleRevoked(role, account, msg.sender);
    }

    function setInvestorEligibility(address investor, bool eligible)
        external
        onlyRole(COMPLIANCE_ROLE)
    {
        eligibleInvestor[investor] = eligible;
        emit InvestorEligibilityChanged(investor, eligible);
    }

    function setReserveReference(string calldata newReference)
        external
        onlyRole(COMPLIANCE_ROLE)
    {
        reserveReference = newReference;
        emit ReserveReferenceChanged(newReference);
    }

    function mint(address to, uint256 amount) external onlyRole(MINTER_ROLE) whenNotPaused {
        require(eligibleInvestor[to], "recipient is not eligible");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function burnFromCustody(address from, uint256 amount)
        external
        onlyRole(MINTER_ROLE)
        whenNotPaused
    {
        require(balanceOf[from] >= amount, "insufficient balance");
        balanceOf[from] -= amount;
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 currentAllowance = allowance[from][msg.sender];
        require(currentAllowance >= amount, "insufficient allowance");
        allowance[from][msg.sender] = currentAllowance - amount;
        _transfer(from, to, amount);
        return true;
    }

    function pause() external onlyRole(PAUSER_ROLE) {
        paused = true;
        emit Paused(msg.sender);
    }

    function unpause() external onlyRole(PAUSER_ROLE) {
        paused = false;
        emit Unpaused(msg.sender);
    }

    function _transfer(address from, address to, uint256 amount) internal whenNotPaused {
        require(to != address(0), "recipient is zero address");
        require(eligibleInvestor[from], "sender is not eligible");
        require(eligibleInvestor[to], "recipient is not eligible");
        require(balanceOf[from] >= amount, "insufficient balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }

    function _grantRole(bytes32 role, address account) internal {
        require(account != address(0), "account is zero address");
        if (!hasRole[role][account]) {
            hasRole[role][account] = true;
            emit RoleGranted(role, account, msg.sender);
        }
    }
}
