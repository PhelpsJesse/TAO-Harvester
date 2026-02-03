#!/usr/bin/env python3
"""Show which days the unmapped source transfers occurred."""

from collections import defaultdict
from src.taostats import TaostatsClient
from src.config import HarvesterConfig

config = HarvesterConfig.from_env()
taostats = TaostatsClient(api_key=config.taostats_api_key)

address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'
earnings = taostats.get_alpha_earnings_history(address, days=30)

unmapped_source = '5CiEiYCp1i2HxUJC2AhMpJWwTfP3sKvM9M1a3V7X8b9C'

daily_earnings = earnings.get('daily_earnings', {})
print(f"Days with transfers from {unmapped_source[:20]}...:\n")

for day in sorted(daily_earnings.keys()):
    transfers = daily_earnings[day].get('transfers', [])
    for t in transfers:
        if t['from'] == unmapped_source:
            print(f"  {day}: {t['amount']:.9f} TAO")
