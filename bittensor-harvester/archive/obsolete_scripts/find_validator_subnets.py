#!/usr/bin/env python3
"""
Diagnostic: Find which subnets have earnings for your validator address
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from src.config import HarvesterConfig
from src.taostats import TaostatsClient

config = HarvesterConfig.from_env()
client = TaostatsClient(api_key=config.taostats_api_key)
address = config.harvester_wallet_address

print("\n" + "="*70)
print("Testing All Subnets for Your Address")
print("="*70 + "\n")
print(f"Address: {address}\n")

# Test subnets 1-20
results = {}
for netuid in range(1, 21):
    earnings = client.get_validator_earnings(address, netuid)
    emissions = earnings.get('total_emissions', 0)
    
    if emissions > 0:
        print(f"✓ Subnet {netuid}: {emissions:.4f} alpha")
        results[netuid] = emissions
    elif earnings.get('raw_data', {}).get('data'):
        print(f"  Subnet {netuid}: Has data but no emissions")
        results[netuid] = 0

if not results:
    print("No emissions found on subnets 1-20")
else:
    print(f"\n{'='*70}")
    print(f"Total: {sum(results.values()):.4f} alpha across {len(results)} subnet(s)")
    print(f"{'='*70}")
