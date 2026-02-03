#!/usr/bin/env python3
"""
Monitor Nova wallet for TAO receipt from alpha swaps.

This script:
1. Polls your Nova wallet for balance changes
2. Tracks incoming TAO transactions
3. Correlates with swap timestamps

Usage:
    python monitor_wallet_tap.py --wallet <nova-wallet-address> [--poll-interval 10]
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

from src.taostats import TaostatsClient
from src.config import HarvesterConfig


class WalletMonitor:
    """Monitor wallet for TAO receipt from alpha swaps."""
    
    def __init__(self, wallet_address: str, taostats_api_key: str = ""):
        self.wallet_address = wallet_address
        self.taostats = TaostatsClient(api_key=taostats_api_key)
        
        # Track observed balances and transactions
        self.balance_history = []
        self.last_tao_balance = None
        
    def get_current_balance(self) -> Optional[float]:
        """Fetch current TAO balance from Taostats."""
        try:
            # Query Taostats for wallet balance
            # Note: This may need to be updated based on actual Taostats API
            result = self.taostats.get_wallet_info(self.wallet_address)
            if result and 'balance_tao' in result:
                return float(result['balance_tao'])
        except Exception as e:
            print(f"Warning: Could not fetch balance: {e}")
        
        return None
    
    def check_for_receipt(self, expected_amount: float, timeout_seconds: int = 300) -> Dict:
        """
        Monitor wallet for expected TAO receipt.
        
        Args:
            expected_amount: Expected TAO to receive
            timeout_seconds: How long to poll (default 5 min)
            
        Returns:
            {
                'received': bool,
                'amount_received': float,
                'timestamp': str,
                'tx_hash': str | None,
                'duration_seconds': int,
            }
        """
        print(f"\nMonitoring wallet for TAO receipt...")
        print(f"Expected: {expected_amount:.9f} TAO")
        print(f"Timeout:  {timeout_seconds}s")
        
        start_time = datetime.utcnow()
        start_balance = self.get_current_balance() or 0.0
        
        print(f"Starting balance: {start_balance:.9f} TAO\n")
        
        # Poll for balance changes
        poll_interval = 5  # seconds
        elapsed = 0
        
        while elapsed < timeout_seconds:
            time.sleep(poll_interval)
            current_balance = self.get_current_balance() or 0.0
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            
            balance_change = current_balance - start_balance
            
            if balance_change > 0:
                duration = int(elapsed)
                print(f"✓ Receipt detected!")
                print(f"  Balance change: +{balance_change:.9f} TAO")
                print(f"  Time elapsed:   {duration}s")
                print(f"  Current balance: {current_balance:.9f} TAO")
                
                return {
                    'received': True,
                    'amount_received': balance_change,
                    'timestamp': datetime.utcnow().isoformat(),
                    'tx_hash': None,  # TODO: Track actual tx hash from Taostats
                    'duration_seconds': duration,
                }
            
            progress = "." * min(10, int(elapsed / (timeout_seconds / 10)))
            print(f"\r[{progress:<10}] {elapsed:.0f}s elapsed, balance: {current_balance:.9f} TAO", end="")
        
        print()
        return {
            'received': False,
            'amount_received': 0.0,
            'timestamp': datetime.utcnow().isoformat(),
            'tx_hash': None,
            'duration_seconds': timeout_seconds,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Monitor Nova wallet for TAO receipt from alpha swaps"
    )
    parser.add_argument("--wallet", type=str, required=True, help="Nova wallet address (required)")
    parser.add_argument("--expected", type=float, default=0.001, help="Expected TAO amount (default 0.001)")
    parser.add_argument("--timeout", type=int, default=300, help="Monitor timeout in seconds (default 300)")
    parser.add_argument("--interval", type=int, default=5, help="Poll interval in seconds (default 5)")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"WALLET MONITOR")
    print(f"{'='*60}")
    print(f"Wallet:         {args.wallet}")
    print(f"Expected TAO:   {args.expected:.9f}")
    print(f"Monitor Time:   {args.timeout}s")
    print(f"Poll Interval:  {args.interval}s")
    print(f"{'='*60}")
    
    # Get API key from config
    config = HarvesterConfig.from_env()
    api_key = config.taostats_api_key or ""
    
    monitor = WalletMonitor(args.wallet, api_key)
    result = monitor.check_for_receipt(args.expected, timeout_seconds=args.timeout)
    
    print(f"\n{'='*60}")
    print(f"MONITOR RESULT")
    print(f"{'='*60}")
    print(json.dumps(result, indent=2, default=str))
    print(f"{'='*60}\n")
    
    if result['received']:
        print(f"✓ TAO receipt confirmed!")
        return 0
    else:
        print(f"✗ No TAO receipt detected within {args.timeout}s")
        print(f"  Please check:")
        print(f"  1. Swap was actually executed (not dry-run)")
        print(f"  2. Correct wallet address")
        print(f"  3. Network connectivity")
        return 1


if __name__ == "__main__":
    exit(main())
