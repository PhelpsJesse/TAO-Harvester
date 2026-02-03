#!/usr/bin/env python3
"""Debug Taostats page scraping."""

import requests
import re

address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'
page_url = f"https://taostats.io/account/{address}"

print(f"Fetching {page_url}...")
response = requests.get(page_url, timeout=10)
response.raise_for_status()
html = response.text

print(f"HTML length: {len(html)} characters")

# Look for SN patterns
sn_matches = re.findall(r'SN\d+', html)
print(f"\nFound {len(sn_matches)} SN mentions: {set(sn_matches)}")

# Look for the alpha breakdown section
alpha_section = re.search(r'Alpha.*?Bittensor.*?[\d,\.]+', html, re.IGNORECASE)
if alpha_section:
    print(f"\nAlpha breakdown section:\n{alpha_section.group(0)[:200]}")

# Look for all numeric amounts
amounts = re.findall(r'Bittensor\s+([\d,\.]+)', html)
print(f"\nFound {len(amounts)} Bittensor amounts: {amounts[:20]}")

# Extract table rows - look for SN patterns and nearby amounts
print("\n\nLooking for SN<num> with nearby amounts:")
lines = html.split('\n')
for i, line in enumerate(lines):
    if 'SN' in line and any(c.isdigit() for c in line):
        # Look for SN followed by digits
        match = re.search(r'SN(\d+)', line)
        if match:
            netuid = match.group(1)
            # Look in this line and next few lines for amount
            context = ' '.join(lines[max(0, i-1):min(len(lines), i+3)])
            print(f"Line {i}: SN{netuid}")
            print(f"  Context: {context[:150]}")
            
            # Extract amount from context
            amount_match = re.search(r'([\d,\.]+)\s+Bittensor', context)
            if amount_match:
                print(f"  Amount: {amount_match.group(1)}")
            print()
