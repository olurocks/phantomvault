#!/usr/bin/env python3

import importlib
import subprocess
import sys
from pprint import pprint

# List of required packages
REQUIRED_PACKAGES = [
    "web3",
    "eth_account",
    "dotenv",       # python-dotenv
    "solcx",        # py-solc-x
]

def check_and_install(packages):
    """Ensure required packages are installed. Install if missing."""
    for pkg in packages:
        try:
            importlib.import_module(pkg)
        except ImportError:
            print(f"⚠️  Package '{pkg}' not found. Installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

# Pre-flight check
check_and_install(REQUIRED_PACKAGES)

# Now safe to import phase modules
from phase1.phase1 import run_phase1_from_env
from phase2.phase2 import run_phase2_from_env


def main():
    print("=== Running Phase 1 ===")
    try:
        p1_result = run_phase1_from_env()
        pprint(p1_result)
    except Exception as e:
        print(f" Phase 1 failed: {e}")
        return

    print("\n \n=== Running Phase 2 ===")
    try:
        p2_result = run_phase2_from_env()
        pprint(p2_result)
    except Exception as e:
        print(f" Phase 2 failed: {e}")
        return

    print("\n✅ All phases completed successfully")


if __name__ == "__main__":
    main()
