#!/usr/bin/env python3
"""Find the alpha-to-TAO conversion rate from recent earnings"""

import sys
sys.path.insert(0, 'src')
from config import get_config
from taostats import TaostatsClient
import os

config = get_config()
validator_hotkeys = config.validator_hotkeys if hasattr(config, 'validator_hotkeys') else ""
validators = [h.strip() for h in validator_hotkeys.split(',') if h.strip()]
address = validators[0] if validators else None

if not address:
    print("ERROR: No validator hotkey configured")
    sys.exit(1)

api_key = os.getenv('TAOSTATS_API_KEY', '')
client = TaostatsClient(api_key=api_key)

# Get earnings history with API (in TAO)
earnings_data = client.get_alpha_earnings_history(address, days=2)
daily_earnings = earnings_data.get('daily_earnings', {})

# Get all transactions that look like emissions (small amounts)
small_txs = []
large_txs = []

for day, day_data in daily_earnings.items():
    for t in day_data['transfers']:
        amount_tao = t['amount']
        if amount_tao <= 5.0:
            small_txs.append((day, amount_tao, t['from']))
        else:
            large_txs.append((day, amount_tao, t['from']))

print(f"Small transactions (likely emissions, <= 5 TAO):")
for day, amt, src in small_txs:
    print(f"  {day}: {amt:.4f} TAO from {src[:20]}")

print(f"\nLarge transactions (likely manual trades, > 5 TAO):")
for day, amt, src in large_txs:
    print(f"  {day}: {amt:.4f} TAO from {src[:20]}")

if small_txs:
    total_small = sum(t[1] for t in small_txs)
    print(f"\nTotal small transactions: {total_small:.4f} TAO")
    print(f"This should match approximately the 0.17 TAO you see in web UI")
    print(f"\nTo find alpha-to-TAO rate, we need to know:")
    print(f"  - How much alpha these {total_small:.4f} TAO represents")
    print(f"  - Or check what the web UI displays for these specific txs")
