#!/usr/bin/env python3
"""
Test the accounting endpoint to get daily earnings data
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.config import HarvesterConfig
from src.taostats import TaostatsClient

config = HarvesterConfig.from_env()
client = TaostatsClient(api_key=config.taostats_api_key)

print("\n" + "="*70)
print("Testing Taostats Accounting Data (Daily Earnings)")
print("="*70 + "\n")

address = config.harvester_wallet_address
netuid = 1

print(f"Address: {address}")
print(f"Subnet (netuid): {netuid}\n")

# Get accounting data
print("Fetching daily earnings data...")
accounting = client.get_accounting_by_date(address, netuid)

if "error" not in accounting:
    print(f"\n✓ Last 24h Earnings: {accounting['last_24h_emission']:.6f} TAO")
    print(f"\nDaily Breakdown (last {len(accounting['daily_data'])} days):")
    for day_data in accounting['daily_data']:
        emission_rao = day_data.get('emission', 0)
        emission_tao = emission_rao / 1e9 if emission_rao else 0
        date = day_data.get('date', 'unknown')
        print(f"  {date}: {emission_tao:.6f} TAO")
else:
    print(f"✗ Error: {accounting['error']}")

# Also try getting balance
print("\n" + "-"*70)
print("\nFetching account balance history...")
balance = client.get_account_balance(address)

if "error" not in balance:
    print(f"\n✓ Current Balance: {balance['current_balance']:.4f} TAO")
    print(f"\nBalance History (last {len(balance['balance_history'])} entries):")
    for entry in balance['balance_history']:
        balance_rao = entry.get('balance', 0)
        balance_tao = balance_rao / 1e9 if balance_rao else 0
        date = entry.get('date', 'unknown')
        print(f"  {date}: {balance_tao:.4f} TAO")
else:
    print(f"✗ Error: {balance['error']}")

print("\n" + "="*70)
