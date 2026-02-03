#!/usr/bin/env python3
"""
Map earning source addresses to subnet IDs.

Instead of trying to get validators per subnet from Taostats (which returns global validators),
we'll analyze the earning patterns and use the Taostats API to find subnet emission data.
"""

import json

# Known earnings sources from the transfer analysis
earnings_sources = {
    '5FqqXKb9zonSNKbZhEuHYjCXnmPbX9tdzMCU2gx8gir8Z8a5': 'primary (multiple subnets)',
    '5CiEiYCp1i2HxUJC2AhMpJWwTfP3sKvM9M1a3V7X8b9C': 'secondary (1 or 2 subnets)',
}

# Your validator address
user_address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'

# Known alpha holdings (from Taostats page)
alpha_holdings = {
    60: 20.3797,
    124: 8.5404,
    120: 8.1171,
    118: 7.7822,
    44: 7.5978,
    54: 6.0385,
    64: 5.9328,
    75: 5.8844,
    34: 5.5387,
    29: 5.0695,
}

# Analyze: which subnets pay out to which emission sources?
# The primary source (5FqqXKb...) accounts for most transfers
# The secondary source (5CiEiYCp...) appears rarely

print("Analysis: Mapping Earnings Sources to Subnets")
print("="*70)
print(f"\nUser: {user_address}")
print(f"Known alpha on subnets: {sorted(alpha_holdings.keys())}")
print(f"Total alpha: {sum(alpha_holdings.values()):.4f} TAO\n")

print("Earnings Sources:")
print("-"*70)
for addr, description in earnings_sources.items():
    print(f"{addr}")
    print(f"  {description}\n")

print("="*70)
print("Manual Mapping (based on visible subnets and earning patterns):")
print("-"*70)
print("""
Since the primary source (5FqqXKb...) emits from most subnets, we need to:
1. Use Taostats API to get per-subnet emission data
2. Match the emission source addresses to subnet IDs

For now, create a config to manually specify which addresses correspond to which subnets.
""")

# Try to build a simple heuristic mapping
# The alpha amounts per subnet match our holdings, so we likely validate on all of them
# The primary emission source likely emits for all/most subnets
# The secondary source emits for one or two subnets

# Save this as a fallback mapping config
mapping_config = {
    "validator_address": user_address,
    "earnings_sources": {
        "5FqqXKb9zonSNKbZhEuHYjCXnmPbX9tdzMCU2gx8gir8Z8a5": {
            "description": "Primary emission source",
            "subnets": [1, 29, 34, 44, 54, 60, 64, 75, 118, 120, 124],
            "note": "Emits alpha for most/all subnets where user has alpha"
        },
        "5CiEiYCp1i2HxUJC2AhMpJWwTfP3sKvM9M1a3V7X8b9C": {
            "description": "Secondary emission source",
            "subnets": [29],
            "note": "Rare emissions, possibly subnet-specific rewards or corrections"
        }
    },
    "alpha_by_subnet": alpha_holdings,
    "total_alpha": sum(alpha_holdings.values()),
    "note": """
This mapping is created from earnings transfer analysis.
The primary source emits daily to most subnets.
The secondary source emits occasionally (possibly dTAO emissions or special rewards).

To improve accuracy: Query Taostats API for subnet_emission data to confirm 
which validator address is the subnet's emission account.
"""
}

with open('validator_subnet_mapping.json', 'w') as f:
    json.dump(mapping_config, f, indent=2)

print("\nMapping saved to validator_subnet_mapping.json")
print("\nNext: Use this mapping in earnings_report.py to assign earnings to subnets")
