#!/usr/bin/env python3
"""
Test alpha-to-TAO swap and confirm receipt in Nova wallet.

Usage:
    python test_alpha_swap.py --netuid 60 --amount 0.01 [--real]
    
Options:
    --netuid: Subnet ID (default 60)
    --amount: Alpha amount to swap (default 0.01 TAO)
    --real: Execute real swap (default is dry-run)
    --wallet: Target wallet address (default from .env)

Example:
    # Dry-run test swap 0.01 alpha on SN60
    python test_alpha_swap.py --netuid 60 --amount 0.01
    
    # Real swap (requires confirmation)
    python test_alpha_swap.py --netuid 60 --amount 0.01 --real
"""

import argparse
import json
import os
import time
from datetime import datetime

from src.alpha_swap import AlphaSwap
from src.config import HarvesterConfig


def get_wallet_address() -> str:
    """Get wallet address from config or environment."""
    config = HarvesterConfig.from_env()
    validators = config.get_validator_list()
    return validators[0] if validators else os.getenv("HARVESTER_WALLET_ADDRESS", "")


def confirm_swap(alpha_amount: float, netuid: int, tao_estimate: float) -> bool:
    """Prompt user to confirm swap execution."""
    print(f"\n{'='*60}")
    print(f"SWAP CONFIRMATION")
    print(f"{'='*60}")
    print(f"Subnet:             SN{netuid}")
    print(f"Alpha to swap:      {alpha_amount:.9f} TAO")
    print(f"Estimated TAO out:  {tao_estimate:.9f}")
    print(f"Timestamp:          {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")
    
    resp = input("\nConfirm swap? (yes/no): ").strip().lower()
    return resp in ('yes', 'y')


def main():
    parser = argparse.ArgumentParser(
        description="Test alpha-to-TAO swap on Bittensor subnet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--netuid", type=int, default=60, help="Subnet ID (default 60)")
    parser.add_argument("--amount", type=float, default=0.01, help="Alpha to swap in TAO units (default 0.01)")
    parser.add_argument("--real", action="store_true", help="Execute real swap (default is dry-run)")
    parser.add_argument("--wallet", type=str, default="", help="Target wallet (default from config)")
    args = parser.parse_args()
    
    # Get wallet address
    wallet = args.wallet or get_wallet_address()
    if not wallet:
        print("ERROR: No wallet address provided. Set HARVESTER_WALLET_ADDRESS or use --wallet")
        return 1
    
    print(f"\n{'='*60}")
    print(f"ALPHA-TO-TAO SWAP TEST")
    print(f"{'='*60}")
    print(f"Subnet:         SN{args.netuid}")
    print(f"Wallet:         {wallet}")
    print(f"Alpha amount:   {args.amount:.9f} TAO")
    print(f"Mode:           {'REAL' if args.real else 'DRY-RUN'}")
    print(f"Timestamp:      {datetime.utcnow().isoformat()}")
    print(f"{'='*60}\n")
    
    # Create swap client
    swap = AlphaSwap(args.netuid, wallet)
    
    # Get estimated output
    est_tao = swap.estimate_tao_output(args.amount)
    rate = swap.get_swap_rate()
    
    print(f"Swap Rate:      1 alpha = {rate:.6f} TAO")
    print(f"TAO Output:     {est_tao:.9f} (estimated)\n")
    
    # Confirm if real
    if args.real and not confirm_swap(args.amount, args.netuid, est_tao):
        print("\nSwap cancelled.")
        return 0
    
    # Execute swap
    print(f"\nExecuting {'real' if args.real else 'dry-run'} swap...")
    result = swap.execute_swap(args.amount, dry_run=not args.real)
    
    print(f"\n{'='*60}")
    print(f"SWAP RESULT")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, default=str))
    print(f"{'='*60}\n")
    
    if result['status'] == 'dry_run':
        print("✓ Dry-run completed (no funds transferred)")
        print("\nNext steps to execute real swap:")
        print("  1. Use your wallet CLI/UI (e.g., subkey, Polkadot.js)")
        print("  2. Or provide signing credentials to this tool")
        print("  3. Confirm TAO receipt in Nova wallet after swap")
        return 0
    
    elif result['status'] == 'success':
        print(f"✓ Swap successful!")
        print(f"  TX Hash: {result['tx_hash']}")
        print(f"  TAO received: {result['tao_received']:.9f}")
        print(f"\nConfirming receipt in Nova wallet...")
        
        # TODO: Poll wallet for TAO receipt
        # For now, just show confirmation message
        print(f"  Wallet: {wallet}")
        print(f"  Check your Nova wallet for ~{est_tao:.9f} TAO incoming")
        print(f"  (may take a few seconds to a few minutes)")
        return 0
    
    else:
        print(f"✗ Swap failed: {result['error']}")
        return 1


if __name__ == "__main__":
    exit(main())
