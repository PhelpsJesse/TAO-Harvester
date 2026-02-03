#!/usr/bin/env python3
"""Extract alpha earnings from transfer history."""

import requests
import json
from datetime import datetime, date

address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'
api_key = 'tao-40546b90-9bb7-44a8-bad9-4110f9f809fd:0700a759'

headers = {'Authorization': api_key}

# Get transfer history with larger limit
endpoint = f'https://api.taostats.io/api/transfer/v1?address={address}&limit=100'
resp = requests.get(endpoint, headers=headers, timeout=5)
data = resp.json()

transfers = data.get('data', [])
print(f"Total transfers found: {len(transfers)}\n")

# Group by date and identify alpha emissions (transfers TO the address)
daily_earnings = {}

for transfer in transfers:
    to_addr = transfer.get('to', {})
    from_addr = transfer.get('from', {})
    to_ss58 = to_addr.get('ss58', '') if isinstance(to_addr, dict) else to_addr
    
    # Only count transfers TO the address (these are earnings/emissions)
    if to_ss58 == address:
        amount_rao = int(transfer.get('amount', '0'))
        amount_tao = amount_rao / 1e9
        timestamp = transfer.get('timestamp', '')
        block = transfer.get('block_number', '')
        
        # Parse date from timestamp
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                day = dt.strftime('%Y-%m-%d')
            except:
                day = 'unknown'
        else:
            day = 'unknown'
        
        # Group by day
        if day not in daily_earnings:
            daily_earnings[day] = []
        
        daily_earnings[day].append({
            'amount': amount_tao,
            'block': block,
            'from': from_addr.get('ss58', 'unknown') if isinstance(from_addr, dict) else 'unknown',
            'timestamp': timestamp
        })

# Display summary
print("Daily Alpha Earnings (Inbound Transfers):")
print("-" * 70)

for day in sorted(daily_earnings.keys(), reverse=True):
    transfers_list = daily_earnings[day]
    total = sum(t['amount'] for t in transfers_list)
    
    print(f"\n{day}: {total:.9f} TAO ({len(transfers_list)} transfers)")
    for t in transfers_list:
        print(f"  {t['timestamp']:30} Block {t['block']:7}  {t['amount']:12.9f} TAO  from {t['from'][:20]}...")

print(f"\n{'='*70}")
total_all = sum(sum(t['amount'] for t in transfers) for transfers in daily_earnings.values())
print(f"Total from all transfers: {total_all:.9f} TAO")
print(f"Date range: {min(daily_earnings.keys())} to {max(daily_earnings.keys())}")
