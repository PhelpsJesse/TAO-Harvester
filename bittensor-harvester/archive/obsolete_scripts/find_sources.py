#!/usr/bin/env python3
"""Find all emission sources in the transfer history."""

import json
import os
from collections import defaultdict
from src.taostats import TaostatsClient
from src.config import HarvesterConfig

config = HarvesterConfig.from_env()
taostats = TaostatsClient(api_key=config.taostats_api_key)

address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'
print(f"Fetching transfers for {address}...")

earnings = taostats.get_alpha_earnings_history(address, days=30)

if 'error' in earnings:
    print(f"Error: {earnings['error']}")
else:
    # Group by source
    by_source = defaultdict(float)
    daily_by_source = defaultdict(list)
    
    daily_earnings = earnings.get('daily_earnings', {})
    for day, day_data in sorted(daily_earnings.items()):
        transfers = day_data.get('transfers', [])
        for t in transfers:
            source = t['from']
            amount = t['amount']
            by_source[source] += amount
            daily_by_source[source].append((day, amount))
    
    print(f"\nTotal unique sources: {len(by_source)}")
    print(f"\nTop sources by total amount:")
    for source, total in sorted(by_source.items(), key=lambda x: -x[1])[:10]:
        daily_count = len(daily_by_source[source])
        avg_daily = total / daily_count if daily_count > 0 else 0
        print(f"\n  {source[:20]}...")
        print(f"    Total:     {total:.9f} TAO")
        print(f"    Days with transfers: {daily_count}")
        print(f"    Avg daily: {avg_daily:.9f} TAO")
        
        # Check if this source is mapped
        mapped_config = json.load(open('config.json'))
        sources_config = mapped_config.get('emissions_mapping', {}).get('sources', {})
        if source in sources_config:
            mapped_subnets = sources_config[source].get('subnets', [])
            print(f"    Mapped to subnets: {mapped_subnets}")
        else:
            print(f"    ⚠️  NOT MAPPED in config.json!")
