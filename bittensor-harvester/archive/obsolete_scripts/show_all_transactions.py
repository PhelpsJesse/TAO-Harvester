#!/usr/bin/env python3
"""Show all transactions in full detail."""

import os
import sys
import requests
from datetime import datetime, timedelta, timezone

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

print(f"Address: {address}\n")
print("Fetching ALL transactions...\n")

# Fetch all pages
all_transactions = []
page = 1
total_pages = None

while True:
    url = f"https://api.taostats.io/api/transfer/v1?address={address}&page={page}&limit=50"
    resp = requests.get(url, headers=headers, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    
    pagination = data.get('pagination', {})
    total_pages = pagination.get('total_pages', 1)
    current_data = data.get('data', [])
    
    all_transactions.extend(current_data)
    
    if page >= total_pages:
        break
    page += 1

print(f"Total transactions: {len(all_transactions)}\n")
print("="*120)
print("ALL TRANSACTIONS (most recent first)")
print("="*120)

# Convert planck to TAO
PLANCK_PER_TAO = 1e9

for i, tx in enumerate(all_transactions, 1):
    ts_str = tx.get('timestamp', '')
    amount_planck = int(tx.get('amount', 0))
    amount_tao = amount_planck / PLANCK_PER_TAO
    from_addr = tx.get('from', {}).get('ss58', 'unknown')[:20]
    to_addr = tx.get('to', {}).get('ss58', 'unknown')[:20]
    tx_hash = tx.get('transaction_hash', '')[:16]
    block = tx.get('block_number', '')
    
    print(f"\n{i}. {ts_str}")
    print(f"   Amount: {amount_tao:12.8f} TAO (from planck: {amount_planck})")
    print(f"   From: {from_addr}...")
    print(f"   To:   {to_addr}...")
    print(f"   Block: {block}, Hash: {tx_hash}...")

print("\n" + "="*120)
print(f"SUMMARY:")
print(f"Total transactions: {len(all_transactions)}")

# Get current time and check how many are in last 24h
now = datetime.now(timezone.utc)
yesterday = now - timedelta(hours=24)

count_24h = 0
for tx in all_transactions:
    ts_str = tx.get('timestamp', '')
    try:
        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        if ts >= yesterday:
            count_24h += 1
    except:
        pass

print(f"Transactions in last 24 hours: {count_24h}")

# Show totals
total_in = 0
total_out = 0
for tx in all_transactions:
    amount_planck = int(tx.get('amount', 0))
    amount_tao = amount_planck / PLANCK_PER_TAO
    to_addr = tx.get('to', {}).get('ss58', '')
    
    if to_addr == address:
        total_in += amount_tao
    else:
        total_out += amount_tao

print(f"Total inbound: {total_in:.8f} TAO")
print(f"Total outbound: {total_out:.8f} TAO")
print(f"Net: {total_in - total_out:.8f} TAO")
