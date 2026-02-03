#!/usr/bin/env python3
"""Test RPC endpoints to find which ones work."""

import requests
import json
from datetime import datetime

endpoints = [
    ("Archive API (Mainnet)", "https://archive-api.bittensor.com/rpc"),
    ("Archive API (Testnet)", "https://archive-api.testnet.bittensor.com/rpc"),
    ("Lite (Mainnet)", "https://lite.chain.opentensor.ai"),
    ("Local Node", "http://localhost:9933"),
    ("OpenTensor RPC", "https://rpc.finney.opentensor.ai"),
]

print("Testing RPC endpoints...\n")
print("=" * 80)

for name, url in endpoints:
    print(f"\n{name}")
    print(f"  URL: {url}")
    
    try:
        # Simple JSON-RPC query: get chain name
        payload = {
            "jsonrpc": "2.0",
            "method": "system_chain",
            "params": [],
            "id": 1
        }
        
        resp = requests.post(url, json=payload, timeout=5)
        status = resp.status_code
        
        if status == 200:
            data = resp.json()
            if 'result' in data:
                print(f"  ✓ Status: {status} OK")
                print(f"    Chain: {data['result']}")
            else:
                print(f"  ✓ Status: {status} OK (but unexpected response format)")
                print(f"    Response: {str(data)[:100]}...")
        else:
            print(f"  ✗ Status: {status}")
            print(f"    Error: {resp.text[:100]}")
            
    except requests.exceptions.Timeout:
        print(f"  ✗ Timeout (5s)")
    except requests.exceptions.ConnectionError as e:
        print(f"  ✗ Connection error: {str(e)[:50]}")
    except Exception as e:
        print(f"  ✗ Error: {str(e)[:50]}")

print("\n" + "=" * 80)
print("\nRecommendation:")
print("  - archive-api.bittensor.com is best for historical queries")
print("  - lite.chain.opentensor.ai may be rate-limited")
print("  - localhost:9933 requires running a local Bittensor node")
