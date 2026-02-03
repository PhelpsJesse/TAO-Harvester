#!/usr/bin/env python3
"""
Fallback alpha provider using manual Taostats data entry.

Since Taostats page uses client-side rendering (Next.js) and their API 
requires authentication keys, we provide a manual way to input validated 
alpha holdings from the Taostats web page.

User can view their account at:
https://taostats.io/account/5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh

And manually create this config file with their alpha breakdown.
"""

import json
from typing import Dict
from datetime import datetime

# Alpha holdings as of 2026-02-01 from Taostats web page
# https://taostats.io/account/5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh
# Total: 123.26115 TAO across 29 subnets (showing top 10 visible, page has 29 entries)
ALPHA_HOLDINGS = {
    60: 20.3797,   # Bitsec.ai SN60
    124: 8.5404,   # Swarm SN124
    120: 8.1171,   # Affine SN120
    118: 7.7822,   # HODL ETF SN118
    44: 7.5978,    # Score SN44
    54: 6.0385,    # Yanez MIID SN54
    64: 5.9328,    # Chutes SN64
    75: 5.8844,    # Hippius SN75
    34: 5.5387,    # BitMind SN34
    29: 5.0695,    # Coldint SN29
    # Remaining subnets (from Taostats page showing "Showing 1 to 10 of 29 entries")
    # Page indicates more subnets exist but not all are visible. Total is 123.26115
    # Estimated distribution for remaining ~42.374 TAO across remaining 19 subnets
    # Until page can be fully scraped, using proportional allocation
}

# Target total: 123.26115 TAO
TOTAL_TARGET = 123.26115
_current_sum = sum(ALPHA_HOLDINGS.values())

# If needed, add remaining alpha to subnets or note that page needs manual update
# For now, this represents the visible holdings. 
# You can update this file manually by copying the full table from:
# https://taostats.io/account/5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh

def get_alpha_holdings() -> Dict[int, float]:
    """Get manually verified alpha holdings from Taostats."""
    return ALPHA_HOLDINGS.copy()

def get_total_alpha() -> float:
    """Get total alpha across all subnets."""
    return sum(ALPHA_HOLDINGS.values())

if __name__ == "__main__":
    holdings = get_alpha_holdings()
    total = get_total_alpha()
    
    print("Alpha Holdings by Subnet:")
    for netuid, amount in sorted(holdings.items()):
        print(f"  SN{netuid}: {amount:.4f} TAO")
    
    print(f"\nCurrent Total: {total:.6f} TAO")
    print(f"Target Total (from Taostats): 123.26115 TAO")
    print(f"Difference: {123.26115 - total:.6f} TAO (from remaining subnets)")
    print(f"\nNote: Page shows 29 subnets total. Only top 10 are shown above.")
    print(f"To update: View https://taostats.io/account/5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")
    print(f"and manually add remaining subnet entries to ALPHA_HOLDINGS dict.")
    print(f"\nLast Updated: 2026-02-01")
    print(f"Source: https://taostats.io/account/5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")
