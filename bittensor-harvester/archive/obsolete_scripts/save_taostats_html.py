#!/usr/bin/env python3
"""Save Taostats HTML for analysis."""

import requests

address = "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh"
page_url = f"https://taostats.io/account/{address}"

print(f"Fetching: {page_url}\n")
response = requests.get(page_url, timeout=10)
response.raise_for_status()
html = response.text

# Save to file
with open('taostats_page.html', 'w', encoding='utf-8') as f:
    f.write(html)
    
print(f"Saved HTML to taostats_page.html ({len(html)} bytes)")

# Show snippet around first SN mention
import re
sn_match = re.search(r'SN(\d+)', html)
if sn_match:
    pos = sn_match.start()
    snippet = html[max(0, pos-200):min(len(html), pos+400)]
    print("\nSnippet around first SN mention:")
    print(snippet)
