#!/usr/bin/env python3
"""Fetch ALL transaction pages from Taostats API and analyze by subnet."""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, 'src')
from taostats import TaostatsClient
from config import get_config

config = get_config()
validator_hotkeys = config.validator_hotkeys if hasattr(config, 'validator_hotkeys') else ""
validators = [h.strip() for h in validator_hotkeys.split(',') if h.strip()]
address = validators[0] if validators else None

if not address:
    print("ERROR: No validator hotkey configured. Set VALIDATOR_HOTKEYS in .env")
    sys.exit(1)

api_key = os.getenv('TAOSTATS_API_KEY', '')
client = TaostatsClient(api_key=api_key)

print(f"Address: {address}\n")
print("Fetching ALL transaction pages from Taostats API...")

# We need to manually fetch paginated data
import requests
api_key = os.getenv('TAOSTATS_API_KEY', '')
headers = {"Authorization": api_key} if api_key else {}

all_transactions = []
page = 1
total_pages = None

while True:
    url = f"https://api.taostats.io/api/transfer/v1?address={address}&page={page}&limit=50"
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        pagination = data.get('pagination', {})
        total_pages = pagination.get('total_pages', 1)
        current_data = data.get('data', [])
        
        all_transactions.extend(current_data)
        print(f"Page {page}/{total_pages}: {len(current_data)} transactions")
        
        if page >= total_pages:
            break
        page += 1
    except Exception as e:
        print(f"Error fetching page {page}: {e}")
        break

print(f"\nTotal transactions fetched: {len(all_transactions)}\n")

# Now let's analyze by date and filter by threshold
# Get current time and 24h ago
now = datetime.now(timezone.utc)
yesterday = now - timedelta(hours=24)

# Convert planck to TAO: 1 TAO = 1e9 planck
PLANCK_PER_TAO = 1e9

# Analyze transactions
print("="*100)
print("TRANSACTIONS IN LAST 24 HOURS (with 5 ALPHA threshold = ~0.05 TAO max)")
print("="*100)

threshold_tao = 0.05  # Approximate: 5 alpha at worst case 0.01 TAO/alpha

transactions_24h = []
large_transactions = []

for tx in all_transactions:
    try:
        ts_str = tx.get('timestamp', '')
        amount_planck = int(tx.get('amount', 0))
        amount_tao = amount_planck / PLANCK_PER_TAO
        
        # Parse timestamp
        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        
        # Only last 24h
        if ts < yesterday:
            continue
        
        from_addr = tx.get('from', {}).get('ss58', 'unknown')
        to_addr = tx.get('to', {}).get('ss58', 'unknown')
        block = tx.get('block_number', '')
        
        tx_info = {
            'timestamp': ts,
            'from': from_addr,
            'to': to_addr,
            'amount_tao': amount_tao,
            'block': block,
            'tx_hash': tx.get('transaction_hash', '')[:16]
        }
        
        if amount_tao <= threshold_tao:
            transactions_24h.append(tx_info)
        else:
            large_transactions.append(tx_info)
    except Exception as e:
        print(f"Error parsing transaction: {e}")
        continue

print(f"\nSmall transactions (emissions, <= {threshold_tao} TAO): {len(transactions_24h)}")
print(f"Large transactions (manual trades, > {threshold_tao} TAO): {len(large_transactions)}\n")

if transactions_24h:
    print("EMISSIONS (small transactions <= 0.05 TAO):")
    print("-" * 100)
    total_emissions = 0
    for tx in sorted(transactions_24h, key=lambda x: x['timestamp']):
        print(f"{tx['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | {tx['amount_tao']:10.8f} TAO | Block {tx['block']}")
        total_emissions += tx['amount_tao']
    print("-" * 100)
    print(f"TOTAL EMISSIONS (last 24h): {total_emissions:.8f} TAO")
else:
    print("No emission transactions found in last 24h")

if large_transactions:
    print(f"\n\nMANUAL TRADES (large transactions > {threshold_tao} TAO):")
    print("-" * 100)
    for tx in sorted(large_transactions, key=lambda x: x['timestamp']):
        print(f"{tx['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | {tx['amount_tao']:10.8f} TAO | {tx['from'][:20]}... | Block {tx['block']}")
    print("-" * 100)
