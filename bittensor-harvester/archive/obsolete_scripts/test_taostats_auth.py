#!/usr/bin/env python3
"""Test Taostats API endpoints with authentication."""

import requests
import json

address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'
api_key = 'tao-40546b90-9bb7-44a8-bad9-4110f9f809fd:0700a759'

headers = {'Authorization': api_key}

# Test with API key
endpoints = [
    ('account/history', f'https://api.taostats.io/api/account/history/v1?validator_hotkey={address}&limit=30'),
    ('validator/latest', f'https://api.taostats.io/api/validator/latest/v1?hotkey={address}&limit=50'),
    ('transactions', f'https://api.taostats.io/api/extrinsic/v1?address={address}&limit=30'),
    ('transfers', f'https://api.taostats.io/api/transfer/v1?address={address}&limit=30'),
    ('portfolio', f'https://api.taostats.io/api/portfolio/v1?address={address}'),
]

print("Testing with API key authentication...\n")

for name, endpoint in endpoints:
    try:
        print(f'=== {name} ===')
        print(f'Endpoint: {endpoint.split("?")[0]}')
        resp = requests.get(endpoint, headers=headers, timeout=5)
        print(f'Status: {resp.status_code}')
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                print(f'Response keys: {list(data.keys())}')
                if 'data' in data:
                    if isinstance(data['data'], list):
                        print(f'Record count: {len(data["data"])}')
                        if len(data['data']) > 0:
                            print(f'First record:\n{json.dumps(data["data"][0], indent=2)[:500]}')
                    elif isinstance(data['data'], dict):
                        print(f'Data keys: {list(data["data"].keys())}')
                        print(f'Data:\n{json.dumps(data["data"], indent=2)[:500]}')
            elif isinstance(data, list):
                print(f'Array length: {len(data)}')
                if len(data) > 0:
                    print(f'First record:\n{json.dumps(data[0], indent=2)[:500]}')
            else:
                print(f'Type: {type(data).__name__}')
                print(f'Content:\n{str(data)[:300]}')
        elif resp.status_code == 400:
            print(f'400 Bad Request')
            try:
                print(f'Error details: {resp.json()}')
            except:
                pass
        
        print()
    except Exception as e:
        print(f'Exception: {e}\n')
