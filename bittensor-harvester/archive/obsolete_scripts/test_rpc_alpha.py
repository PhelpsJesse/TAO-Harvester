#!/usr/bin/env python3
"""Test RPC alpha balance queries directly."""

import sys
sys.path.insert(0, 'src')

from chain import ChainClient

# Test address and subnets
address = "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh"
subnets = [29, 34, 44]

client = ChainClient(rpc_url="https://lite.chain.opentensor.ai", db=None)

print("Testing RPC alpha balance queries...\n")

for netuid in subnets:
    try:
        balance = client.get_alpha_balance(address, netuid)
        print(f"SN{netuid}: {balance} ALPHA")
    except Exception as e:
        print(f"SN{netuid}: ERROR - {e}")

