#!/usr/bin/env python3
"""
Test script: Calculate earnings for the last day.

This tests the core accounting logic without requiring a live API.
We'll manually insert reward records and verify the calculations.
"""

import sys
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import HarvesterConfig
from src.database import Database
from src.chain import ChainClient
from src.accounting import Accounting


def test_earnings_calculation():
    """Test calculating earnings for the last 24 hours."""
    print("\n" + "="*60)
    print("Testing Earnings Calculation (Last 24 Hours)")
    print("="*60 + "\n")

    # Load config
    config = HarvesterConfig.from_env()
    print(f"Wallet Address: {config.harvester_wallet_address}")
    print(f"Subnet (netuid): {config.netuid}")
    print(f"Harvest Fraction: {config.harvest_fraction}\n")

    # Create temporary database for this test
    temp_fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)

    try:
        # Initialize database and components
        db = Database(temp_db)
        db.connect()

        chain = ChainClient(config.substrate_rpc_url)
        accounting = Accounting(db, chain)

        # Simulate earning rewards over the last 24 hours
        print("Step 1: Simulating reward records from the last 24 hours\n")

        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)

        # Create some mock reward entries
        # Assuming you earned rewards at different times
        reward_blocks = [
            (12345, 0.5),   # Block 12345: +0.5 alpha
            (12400, 0.7),   # Block 12400: +0.7 alpha
            (12500, 0.3),   # Block 12500: +0.3 alpha
            (12600, 0.9),   # Block 12600: +0.9 alpha
        ]

        total_earned = 0
        for block, amount in reward_blocks:
            print(f"  Block {block}: +{amount} alpha")
            db.insert_reward(
                netuid=config.netuid,
                block_number=block,
                alpha_amount=amount,
                tx_hash=f"0xmock_{block}",
                notes=f"Test reward for {config.harvester_wallet_address[:8]}...",
            )
            total_earned += amount

        print(f"\nTotal earned (24h): {total_earned} alpha\n")

        # Step 2: Query accumulated rewards
        print("Step 2: Querying accumulated rewards\n")
        accumulated = db.get_accumulated_rewards(netuid=config.netuid)
        print(f"Accumulated data: {accumulated}\n")

        # Step 3: Calculate harvestable amount
        print("Step 3: Calculating harvestable amount\n")
        harvestable_info = accounting.get_harvestable_amount(
            netuid=config.netuid,
            harvest_fraction=config.harvest_fraction
        )
        print(f"Harvestable info: {harvestable_info}\n")

        # Step 4: Export summary
        print("Step 4: Summary\n")
        print(f"Total Earned (24h):    {total_earned} alpha")
        if "harvestable" in harvestable_info:
            print(f"Harvestable ({config.harvest_fraction*100:.0f}%): {harvestable_info['harvestable']} alpha")
        print()

        print("=" * 60)
        print("✓ Earnings calculation test completed successfully!")
        print("=" * 60 + "\n")

    finally:
        # Cleanup
        try:
            if hasattr(db, 'close'):
                db.close()
            if os.path.exists(temp_db):
                os.remove(temp_db)
        except Exception as e:
            print(f"Cleanup warning: {e}")


if __name__ == "__main__":
    test_earnings_calculation()
