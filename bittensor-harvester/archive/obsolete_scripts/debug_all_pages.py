#!/usr/bin/env python3
"""Debug script to check ALL transaction pages from Taostats API"""

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
print("Fetching ALL transaction pages from API...\n")

# Manually fetch all pages since get_alpha_earnings_history only returns page 1
import requests

all_transactions = []
page = 1
max_pages = 10  # Safety limit

while page <= max_pages:
    url = f"https://api.taostats.io/api/transfer/v1?address={address}&limit=50&page={page}"
    headers = {}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching page {page}: {e}")
        break
    
    # Extract transactions from this page
    transactions = data.get('data', [])
    all_transactions.extend(transactions)
    
    # Check pagination info
    pagination = data.get('pagination', {})
    print(f"Page {page}: {len(transactions)} transactions | Total: {pagination.get('total_items', '?')} | Pages: {pagination.get('total_pages', '?')}")
    
    # Stop if no more pages
    if not pagination.get('next_page'):
        break
    
    page = pagination.get('next_page', page + 1)

print(f"\nTotal transactions fetched: {len(all_transactions)}\n")

# Get current time and 24h ago
now = datetime.now(timezone.utc)
yesterday = now - timedelta(hours=24)

# Analyze transactions
small_txs = []  # Emissions (< 5 TAO)
large_txs = []  # Manual trades (>= 5 TAO)

for tx in all_transactions:
    try:
        amount_str = tx.get('amount', '0')
        # Amount is in planck (1 TAO = 10^9 planck)
        amount_planck = int(amount_str)
        amount_tao = amount_planck / 1e9
        
        tstamp_str = tx.get('timestamp', '')
        tstamp = datetime.fromisoformat(tstamp_str.replace('Z', '+00:00'))
        
        is_recent = tstamp >= yesterday
        is_small = amount_tao < 5.0
        
        if is_recent:
            if is_small:
                small_txs.append({'amount': amount_tao, 'timestamp': tstamp, 'tx': tx})
            else:
                large_txs.append({'amount': amount_tao, 'timestamp': tstamp, 'tx': tx})
    except Exception as e:
        print(f"Error parsing tx: {e}")
        continue

print("="*80)
print(f"LAST 24H EMISSIONS (< 5 TAO per transaction)")
print("="*80)
if small_txs:
    total_small = 0
    for tx_info in sorted(small_txs, key=lambda x: -x['amount']):
        amount = tx_info['amount']
        tstamp = tx_info['timestamp']
        print(f"{tstamp.strftime('%Y-%m-%d %H:%M:%S UTC')} | {amount:10.6f} TAO")
        total_small += amount
    print(f"\nTotal Emissions (24h): {total_small:.6f} TAO")
else:
    print("No emissions found")

print("\n" + "="*80)
print(f"LAST 24H MANUAL TRADES (>= 5 TAO per transaction)")
print("="*80)
if large_txs:
    total_large = 0
    for tx_info in sorted(large_txs, key=lambda x: -x['amount']):
        amount = tx_info['amount']
        tstamp = tx_info['timestamp']
        print(f"{tstamp.strftime('%Y-%m-%d %H:%M:%S UTC')} | {amount:10.6f} TAO")
        total_large += amount
    print(f"\nTotal Trades (24h): {total_large:.6f} TAO")
else:
    print("No manual trades found")
