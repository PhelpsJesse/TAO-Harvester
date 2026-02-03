#!/usr/bin/env python3
"""Build mapping of validator addresses to subnet IDs from Taostats API."""

import requests
import json
from collections import defaultdict

api_key = 'tao-40546b90-9bb7-44a8-bad9-4110f9f809fd:0700a759'
headers = {'Authorization': api_key}

# List of subnets to query
subnets = [1, 29, 34, 44, 54, 60, 64, 75, 118, 120, 124]

# Mapping: validator_address -> subnet_id
validator_to_subnet = {}

# Mapping: subnet_id -> list of validators
subnet_validators = defaultdict(list)

print("Querying Taostats for subnet validators...\n")

for netuid in subnets:
    try:
        print(f"SN{netuid}...", end=" ", flush=True)
        
        # Try different endpoint patterns
        endpoints = [
            f"https://api.taostats.io/api/validator/latest/v1?subnet_uid={netuid}&limit=100",
            f"https://api.taostats.io/api/validators/subnet/v1?subnet_uid={netuid}&limit=100",
            f"https://api.taostats.io/api/subnet/validators/v1?subnet_uid={netuid}&limit=100",
        ]
        
        found = False
        for endpoint in endpoints:
            resp = requests.get(endpoint, headers=headers, timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                validators_list = data.get('data', [])
                
                if isinstance(validators_list, list) and len(validators_list) > 0:
                    print(f"({len(validators_list)} validators)")
                    found = True
                    
                    for v in validators_list:
                        if isinstance(v, dict):
                            # Extract validator address
                            hotkey = None
                            if isinstance(v.get('hotkey'), dict):
                                hotkey = v['hotkey'].get('ss58') or v['hotkey'].get('hex')
                            else:
                                hotkey = v.get('hotkey') or v.get('address') or v.get('ss58')
                            
                            if hotkey:
                                validator_to_subnet[hotkey] = netuid
                                subnet_validators[netuid].append(hotkey)
                    break
        
        if not found:
            print("(no validators found)")
            
    except Exception as e:
        print(f"(Error: {str(e)[:30]})")

print(f"\n{'='*70}")
print(f"Total unique validators found: {len(validator_to_subnet)}")
print(f"Subnets with validators: {len(subnet_validators)}")

# Display mapping
print(f"\n{'='*70}")
print("Validator → Subnet Mapping:")
print(f"{'='*70}\n")

for netuid in sorted(subnet_validators.keys()):
    validators = subnet_validators[netuid]
    print(f"SN{netuid}: {len(validators)} validators")
    for v in validators[:3]:  # Show first 3
        print(f"  {v}")
    if len(validators) > 3:
        print(f"  ... and {len(validators)-3} more")
    print()

# Save to JSON for use in earnings_report
mapping_file = 'validator_subnet_mapping.json'
with open(mapping_file, 'w') as f:
    json.dump({
        'validator_to_subnet': validator_to_subnet,
        'subnet_validators': {str(k): v for k, v in subnet_validators.items()}
    }, f, indent=2)

print(f"Mapping saved to {mapping_file}")

# Print the primary earnings source addresses for debugging
print(f"\n{'='*70}")
print("Key validators (potential earning sources):")
print("  5FqqXKb9zonSNKbZhEuHYjCXnmPbX9tdzMCU2gx8gir8Z8a5 (primary source)")
print("  5CiEiYCp1i2HxUJC2AhMpJWwTfP3sKvM9M1a3V7X8b9C (secondary source)")
if '5FqqXKb9zonSNKbZhEuHYjCXnmPbX9tdzMCU2gx8gir8Z8a5' in validator_to_subnet:
    print(f"    → SN{validator_to_subnet['5FqqXKb9zonSNKbZhEuHYjCXnmPbX9tdzMCU2gx8gir8Z8a5']}")
if '5CiEiYCp1i2HxUJC2AhMpJWwTfP3sKvM9M1a3V7X8b9C' in validator_to_subnet:
    print(f"    → SN{validator_to_subnet['5CiEiYCp1i2HxUJC2AhMpJWwTfP3sKvM9M1a3V7X8b9C']}")
