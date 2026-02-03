#!/usr/bin/env python3
"""Check available Taostats endpoints for emissions data."""

import os
import sys
import requests

sys.path.insert(0, 'src')
from config import get_config

config = get_config()
validator_hotkeys = config.validator_hotkeys if hasattr(config, 'validator_hotkeys') else ""
validators = [h.strip() for h in validator_hotkeys.split(',') if h.strip()]
address = validators[0] if validators else None

if not address:
    print("ERROR: No validator hotkey configured")
    sys.exit(1)

api_key = os.getenv('TAOSTATS_API_KEY', '')
headers = {"Authorization": api_key} if api_key else {}

BASE_URL = "https://api.taostats.io"

# Try different endpoints that might have emissions data
endpoints_to_try = [
    f"/api/account/latest/v1?address={address}&network=finney",
    f"/api/accounting/v1?address={address}&days=1",
    f"/api/account/history/v1?address={address}",
    f"/api/account/earnings/v1?address={address}",
    f"/api/hotkey_emissions/v1?address={address}",
    f"/api/dtao/hotkey_emission/v1?address={address}",
]

print(f"Testing endpoints for address: {address}\n")

for endpoint in endpoints_to_try:
    url = BASE_URL + endpoint
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        status = resp.status_code
        try:
            data = resp.json()
            data_keys = list(data.keys())[:5]  # First 5 keys
            print(f"✓ {endpoint}")
            print(f"  Status: {status}, Keys: {data_keys}\n")
        except:
            print(f"✓ {endpoint}")
            print(f"  Status: {status}, Response length: {len(resp.text)} chars\n")
    except Exception as e:
        print(f"✗ {endpoint}")
        print(f"  Error: {str(e)[:50]}...\n")
