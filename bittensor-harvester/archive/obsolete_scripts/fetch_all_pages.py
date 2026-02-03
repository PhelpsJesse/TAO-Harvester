#!/usr/bin/env python3
"""Fetch ALL pages of transaction history to find small emission transactions"""

import sys
import os
sys.path.insert(0, 'src')
from config import get_config
from taostats import TaostatsClient

config = get_config()
validator_hotkeys = config.validator_hotkeys if hasattr(config, 'validator_hotkeys') else ""
validators = [h.strip() for h in validator_hotkeys.split(',') if h.strip()]
address = validators[0] if validators else None

if not address:
    print("ERROR: No validator hotkey configured")
    sys.exit(1)

api_key = os.getenv('TAOSTATS_API_KEY', '')
client = TaostatsClient(api_key=api_key)

# Get earnings history (which uses get_alpha_earnings_history internally)
# But we need to fetch all pages manually
print("Fetching ALL pages of transaction history...")

# Make direct API call to get all pages
import requests
session = requests.Session()
if api_key:
    session.headers.update({"Authorization": api_key})

all_transactions = []
page = 1
while True:
    url = f"https://api.taostats.io/api/transfer/v1"
    params = {"address": address, "limit": 50, "page": page}
    
    try:
        resp = session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching page {page}: {e}")
        break
    
    items = data.get("data", [])
    if not items:
        print(f"No more items at page {page}")
        break
    
    all_transactions.extend(items)
    pagination = data.get("pagination", {})
    
    print(f"Page {page}: {len(items)} items | Total so far: {len(all_transactions)}")
    
    if pagination.get("next_page") and pagination["next_page"] != page:
        page = pagination["next_page"]
    else:
        break

print(f"\n{'='*80}")
print(f"Total transactions fetched: {len(all_transactions)}")
print(f"{'='*80}\n")

# Analyze transactions by amount
from collections import defaultdict
by_amount = defaultdict(list)

for tx in all_transactions:
    # Amount is in planck, need to convert to TAO
    amount_planck = int(tx.get('amount', 0))
    amount_tao = amount_planck / 1e9
    
    from_addr = tx.get('from', {}).get('ss58', 'unknown')
    timestamp = tx.get('timestamp', '')
    
    by_amount[round(amount_tao, 2)].append({
        'amount': amount_tao,
        'from': from_addr,
        'timestamp': timestamp
    })

print("Transactions grouped by amount:")
for amount in sorted(by_amount.keys()):
    count = len(by_amount[amount])
    from_addrs = set(t['from'] for t in by_amount[amount])
    print(f"  {amount:7.4f} TAO: {count:2d} transactions from {len(from_addrs)} source(s)")
    if amount <= 0.1:  # Show details for small transactions
        for t in by_amount[amount][:2]:  # First 2 examples
            print(f"           {t['timestamp']} from {t['from'][:20]}")
