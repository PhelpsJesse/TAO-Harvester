#!/usr/bin/env python3
"""Find a working public RPC endpoint for Bittensor."""

import requests
import time

# More RPC endpoints to try
endpoints = [
    "https://lite.chain.opentensor.ai",
    "https://ws.finney.opentensor.ai",  
    "https://finney.node.opentensor.ai/rpc",
    "https://bittensor-rpc.allthatnode.com:8545",
    "https://testnet-rpc.allthatnode.com:8545",
]

print("Finding best public RPC endpoint for Bittensor...\n")

working = []

for url in endpoints:
    try:
        payload = {"jsonrpc": "2.0", "method": "system_chain", "params": [], "id": 1}
        resp = requests.post(url, json=payload, timeout=5)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                if 'result' in data:
                    working.append((url, data['result']))
                    print(f"✓ {url}")
                    print(f"  Chain: {data['result']}\n")
            except:
                pass
        else:
            print(f"✗ {url} (Status: {resp.status_code})\n")
    except Exception as e:
        print(f"✗ {url} ({str(e)[:40]}...)\n")

if working:
    print("\n" + "=" * 80)
    print("WORKING ENDPOINTS:")
    for url, chain in working:
        print(f"  {url}")
        print(f"    Chain: {chain}")
else:
    print("\nNo public endpoints working. You'll need to:")
    print("  1. Run a local Bittensor node: bittensor-cli node start")
    print("  2. Or contact OpenTensor for a public RPC access")
