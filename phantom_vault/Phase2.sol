// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

interface IFlashLoanReceiver {
    function executeOperation(uint256 amount) external;
}

contract EmergencyVIPGateway is ReentrancyGuard {
    struct LoanRecord {
        uint256 amount;
        uint256 balanceBefore;
        uint256 expected; // balanceBefore + fee if any
        bool active;
    }

    // State variables
    mapping(address => uint256) public deposits;
    mapping(address => bool) public whitelisted;
    mapping(address => bool) public hasExploited;
    mapping(address => uint256) public lastFlashLoanBlock;
    mapping(address => LoanRecord) public loanRecords;
    event FlashLoanCallbackFailed(address indexed borrower, string reason);
    event FlashLoanRepaidBy(address indexed borrower, uint256 amount);

    uint256 public immutable INITIAL_BALANCE;
    uint256 public reservedLiquidity;

    address public owner;

    uint256 public constant INDIVIDUAL_CAP_PERCENT = 10; 
    uint256 public constant VIP_THRESHOLD_PERCENT = 50; 
    uint256 public constant FLASH_LOAN_MAX_PERCENT = 90;

    event RecordAction(address indexed exploiter, uint256 timestamp);
    event EmergencyVIPAction(
        address indexed vipUser,
        string action,
        uint256 timestamp
    );
    event FlashLoanInitiated(address indexed borrower, uint256 amount);
    event DepositMade(address indexed user, uint256 amount);
    event WhitelistUpdated(address indexed user, bool status);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier onlyOwnerOrDuringFlashLoan() {
        require(
            msg.sender == owner || loanRecords[msg.sender].active,
            "Only owner or during active flash loan"
        );
        _;
    }

    constructor() payable {
        require(
            msg.value >= 0.1 ether,
            "Need at least 0.1 ETH initial liquidity"
        );
        owner = msg.sender;
        INITIAL_BALANCE = msg.value;

        whitelisted[owner] = true;
        emit WhitelistUpdated(owner, true);
    }

    function _toString(uint256 value) internal pure returns (string memory) {
        if (value == 0) {
            return "0";
        }
        uint256 temp = value;
        uint256 digits;
        while (temp != 0) {
            digits++;
            temp /= 10;
        }
        bytes memory buffer = new bytes(digits);
        while (value != 0) {
            digits -= 1;
            buffer[digits] = bytes1(uint8(48 + uint256(value % 10)));
            value /= 10;
        }
        return string(buffer);
    }

    /**
     * @dev Deposit function with individual cap for non-whitelisted users
     */
    function deposit() external payable {
        require(msg.value > 0, "Must deposit something");

        if (!whitelisted[msg.sender]) {
            uint256 individualCap = (INITIAL_BALANCE * INDIVIDUAL_CAP_PERCENT) /
                100;
            require(
                deposits[msg.sender] + msg.value <= individualCap,
                "Individual deposit cap exceeded"
            );
        }

        deposits[msg.sender] += msg.value;
        emit DepositMade(msg.sender, msg.value);
    }

    /**
     * @dev Emergency VIP action
     */
    function emergencyVIPAction(
        string calldata action
    ) external onlyOwnerOrDuringFlashLoan {
        if (msg.sender != owner) {
            require(
                _hasVIPThreshold(msg.sender),
                "Insufficient deposits for VIP action"
            );

            if (loanRecords[msg.sender].active && !hasExploited[msg.sender]) {
                hasExploited[msg.sender] = true;
                //remember to rename
                emit RecordAction(msg.sender, block.timestamp);
            }
        }

        emit EmergencyVIPAction(msg.sender, action, block.timestamp);
    }

    /**
     * @dev Flash loan function
     */
    function requestFlashLoan(uint256 amount) external {
        require(amount > 0, "Amount must be greater than 0");
        uint256 available = address(this).balance - reservedLiquidity;

        require(
            amount <= (available * FLASH_LOAN_MAX_PERCENT) / 100,
            "Amount exceeds maximum"
        );
        require(
            !loanRecords[msg.sender].active,
            "Flash loan already active for this caller"
        );

        require(
            lastFlashLoanBlock[msg.sender] < block.number,
            "One flash loan per block"
        );

        reservedLiquidity += amount;
        loanRecords[msg.sender] = LoanRecord({
            amount: amount,
            balanceBefore: address(this).balance,
            expected: address(this).balance,
            active: true
        });

        emit FlashLoanInitiated(msg.sender, amount);
        lastFlashLoanBlock[msg.sender] = block.number;

        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Flash loan transfer failed");

        try IFlashLoanReceiver(msg.sender).executeOperation(amount) {
            // success path – nothing special
        } catch Error(string memory reason) {
            require(
                reservedLiquidity >= amount,
                string(
                    abi.encodePacked(
                        "Reserved liquidity mismatch. reservedLiquidity=",
                        _toString(reservedLiquidity),
                        " amount=",
                        _toString(amount)
                    )
                )
            );
            if (loanRecords[msg.sender].active) {
                loanRecords[msg.sender].active = false;
                reservedLiquidity -= amount;
            }
            emit FlashLoanCallbackFailed(msg.sender, reason);
            revert(reason);
        } catch {
            require(
                reservedLiquidity >= amount,
                string(
                    abi.encodePacked(
                        "Reserved liquidity mismatch. reservedLiquidity=",
                        _toString(reservedLiquidity),
                        " amount=",
                        _toString(amount)
                    )
                )
            );
            if (loanRecords[msg.sender].active) {
                loanRecords[msg.sender].active = false;
                reservedLiquidity -= amount;
            }
            emit FlashLoanCallbackFailed(msg.sender, "callback failed");
            revert("callback failed");
        }

        LoanRecord storage recStorage = loanRecords[msg.sender];

        if (recStorage.active) {
            require(
                reservedLiquidity >= recStorage.amount,
                "Reserved liquidity mismatch"
            );

            // cleanup and revert
            recStorage.active = false;
            reservedLiquidity -= recStorage.amount;
            revert("Flash loan not repaid during callback");
        }

    }

    /**
     * @dev Withdraw deposits
     */
    function withdraw(uint256 amount) external nonReentrant {
        require(amount > 0, "Amount must be greater than 0");
        require(deposits[msg.sender] >= amount, "Insufficient deposit balance");
        require(
            !loanRecords[msg.sender].active,
            "Cannot withdraw during active flash loan"
        );

        deposits[msg.sender] -= amount;

        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Withdrawal failed");
    }

    /**
     * @dev Owner functions
     */
    function updateWhitelist(address user, bool status) external onlyOwner {
        whitelisted[user] = status;
        emit WhitelistUpdated(user, status);
    }

    function ownerWithdrawAll() external nonReentrant onlyOwner {
        require(reservedLiquidity == 0, "Cannot withdraw while loans active");
        uint256 balance = address(this).balance;
        require(balance > 0, "No funds to withdraw");

        (bool success, ) = msg.sender.call{value: balance}("");
        require(success, "Owner withdrawal failed");
    }

    /**
     * @dev Internal helper functions
     */
    function _hasVIPThreshold(address user) internal view returns (bool) {
        uint256 required = (address(this).balance * VIP_THRESHOLD_PERCENT) /
            100;
        return deposits[user] >= required;
    }

    /**
     * @dev View functions for verification
     */
    function getUserInfo(
        address user
    )
        external
        view
        returns (uint256 userDeposits, bool exploited, bool userIsWhitelisted)
    {
        return (deposits[user], hasExploited[user], whitelisted[user]);
    }

    function getContractInfo()
        external
        view
        returns (
            uint256 totalBalance,
            uint256 initialBalance,
            uint256 individualCapAmount
        )
    {
        return (
            address(this).balance,
            INITIAL_BALANCE,
            (INITIAL_BALANCE * INDIVIDUAL_CAP_PERCENT) / 100
        );
    }

    function getVIPThreshold() external view returns (uint256) {
        return (address(this).balance * VIP_THRESHOLD_PERCENT) / 100;
    }

    function checkIfExploited(
        address contractAddress
    ) external view returns (bool exploited) {
        return hasExploited[contractAddress];
    }

    function repay() external payable nonReentrant {
        LoanRecord storage rec = loanRecords[msg.sender];
        require(rec.active, "No active loan for caller");
        require(msg.value > 0, "Must send repayment");

        require(msg.value >= rec.amount, "Insufficient repayment amount");

        require(reservedLiquidity >= rec.amount, "Reserved liquidity mismatch");

        rec.active = false;

        uint256 loanAmt = rec.amount;
        rec.amount = 0;

        reservedLiquidity -= loanAmt;

        uint256 excess = msg.value - loanAmt;
        if (excess > 0) {
            (bool refunded, ) = payable(msg.sender).call{value: excess}("");
            require(refunded, "Refund failed");
        }

        emit FlashLoanRepaidBy(msg.sender, msg.value);
    }

    receive() external payable {
        revert("Use Deposit() to make deposits");
    }
}
