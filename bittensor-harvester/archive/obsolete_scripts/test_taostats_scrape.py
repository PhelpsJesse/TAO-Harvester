#!/usr/bin/env python3
"""Test Taostats web scraping to see all subnet patterns."""

import requests
import re

address = "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh"
page_url = f"https://taostats.io/account/{address}"

print(f"Fetching: {page_url}\n")
response = requests.get(page_url, timeout=10)
response.raise_for_status()
html = response.text

# Find all SN patterns
sn_matches = re.findall(r'SN(\d+)', html)
unique_subnets = sorted(set(int(sn) for sn in sn_matches))

print(f"Found {len(unique_subnets)} unique subnets mentioned on page:")
print(unique_subnets)
print()

# Try to find all subnet balances
lines = html.split('\n')
subnet_balances = {}

for i, line in enumerate(lines):
    sn_match = re.search(r'SN(\d+)', line)
    if sn_match:
        netuid = int(sn_match.group(1))
        # Look forward in the next few lines for a Bittensor amount
        context = '\n'.join(lines[i:min(i+10, len(lines))])
        amount_match = re.search(r'Bittensor\s+([\d,\.]+)', context)
        if amount_match:
            alpha_str = amount_match.group(1).replace(',', '').strip()
            alpha_float = float(alpha_str)
            if alpha_float > 0:
                subnet_balances[netuid] = alpha_float

print(f"\nExtracted {len(subnet_balances)} subnet balances:")
for netuid in sorted(subnet_balances.keys()):
    print(f"  SN{netuid}: {subnet_balances[netuid]:.8f}")
print(f"\nTotal: {sum(subnet_balances.values()):.8f}")
