#!/usr/bin/env python3
"""
Test earnings on specific subnets with rate limit handling
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.config import HarvesterConfig
from src.taostats import TaostatsClient

config = HarvesterConfig.from_env()
client = TaostatsClient(api_key=config.taostats_api_key)
address = config.harvester_wallet_address

print("\nTesting specific subnets with rate limit handling...\n")

# Test subnets one at a time with delays
test_subnets = [1, 5, 27, 30]

for netuid in test_subnets:
    print(f"Subnet {netuid}...", end=" ")
    earnings = client.get_validator_earnings(address, netuid)
    emissions = earnings.get('total_emissions', 0)
    
    if emissions > 0:
        print(f"✓ {emissions:.4f} alpha")
    else:
        print("- No emissions")
    
    time.sleep(0.5)  # Rate limit delay

print("\nDone!")
