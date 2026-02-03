#!/usr/bin/env python3
"""Debug script to check all transactions from Taostats API"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, 'src')
from taostats import TaostatsClient
from config import get_config

config = get_config()
# Get the address from validator_hotkeys
validator_hotkeys = config.validator_hotkeys if hasattr(config, 'validator_hotkeys') else ""
validators = [h.strip() for h in validator_hotkeys.split(',') if h.strip()]
address = validators[0] if validators else None

if not address:
    print("ERROR: No validator hotkey configured. Set VALIDATOR_HOTKEYS in .env")
    sys.exit(1)

print(f"Address: {address}\n")
api_key = os.getenv('TAOSTATS_API_KEY', '')
client = TaostatsClient(api_key=api_key)

print("Fetching earnings history from API...")
earnings_data = client.get_alpha_earnings_history(address, days=2)
print(f"Response: {earnings_data}\n")

# Extract all transfers from the response
all_transfers = []
daily_earnings = earnings_data.get('daily_earnings', {})
for day, day_data in daily_earnings.items():
    for transfer in day_data.get('transfers', []):
        all_transfers.append(transfer)

print(f"Total transactions returned: {len(all_transfers)}\n")

# Get current time and 24h ago
now = datetime.now(timezone.utc)
yesterday = now - timedelta(hours=24)

# Group by source and date
sources = {}
daily_sources = {}

for t in all_transfers:
    source = t.get('from', 'unknown')
    amount = float(t.get('amount', 0))
    created = t.get('timestamp', '')
    
    try:
        tstamp = datetime.fromisoformat(created.replace('Z', '+00:00'))
    except:
        tstamp = None
    
    # Track all sources
    if source not in sources:
        sources[source] = {'count': 0, 'total_alpha': 0, 'amounts': []}
    sources[source]['count'] += 1
    sources[source]['total_alpha'] += amount
    sources[source]['amounts'].append(amount)
    
    # Track only last 24h
    if tstamp and tstamp >= yesterday:
        if source not in daily_sources:
            daily_sources[source] = {'count': 0, 'total_alpha': 0}
        daily_sources[source]['count'] += 1
        daily_sources[source]['total_alpha'] += amount

print("="*80)
print("ALL SOURCES (full history)")
print("="*80)
for source, data in sorted(sources.items(), key=lambda x: -x[1]['total_alpha']):
    min_amt = min(data['amounts']) if data['amounts'] else 0
    max_amt = max(data['amounts']) if data['amounts'] else 0
    print(f"{source[:50]:50} | {data['count']:4d} tx | {data['total_alpha']:10.4f} TAO | range: {min_amt:.4f}-{max_amt:.4f}")

print(f"\nTotal across all sources: {sum(d['total_alpha'] for d in sources.values()):.4f} TAO\n")

print("="*80)
print(f"SOURCES IN LAST 24H (since {yesterday.strftime('%Y-%m-%d %H:%M UTC')})")
print("="*80)
if daily_sources:
    for source, data in sorted(daily_sources.items(), key=lambda x: -x[1]['total_alpha']):
        print(f"{source[:50]:50} | {data['count']:4d} tx | {data['total_alpha']:10.4f} TAO")
    print(f"\nTotal in last 24h: {sum(d['total_alpha'] for d in daily_sources.values()):.4f} TAO")
else:
    print("No transactions in last 24h")
