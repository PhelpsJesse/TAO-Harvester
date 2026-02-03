#!/usr/bin/env python3
"""Debug script to check what transfers are being fetched."""

from src.taostats import TaostatsClient
import os
import json

taostats = TaostatsClient(api_key=os.getenv('TAOSTATS_API_KEY', ''))
earnings = taostats.get_alpha_earnings_history('5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh', days=1)

print('Total earnings (1d):', earnings.get('total_earnings', 0))
daily = earnings.get('daily_earnings', {})

for day in sorted(daily.keys(), reverse=True):
    day_data = daily[day]
    transfers = day_data['transfers']
    print(f'\n{day}: {len(transfers)} transfers')
    
    # Group by source
    from collections import defaultdict
    by_source = defaultdict(list)
    for t in transfers:
        by_source[t['from']].append(t)
    
    total_day = 0
    for source, source_transfers in sorted(by_source.items()):
        source_total = sum(t['amount'] for t in source_transfers)
        print(f'  {source[:16]}... ({len(source_transfers)} transfers) = {source_total:.9f} alpha')
        total_day += source_total
    
    print(f'  TOTAL: {total_day:.9f} alpha')
