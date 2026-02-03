#!/usr/bin/env python3
"""Test Taostats API endpoints for historical alpha data."""

import requests
import json

address = '5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh'

endpoints = [
    ('account/history (validator_hotkey)', f'https://api.taostats.io/api/account/history/v1?validator_hotkey={address}&limit=30'),
    ('account/history (all params)', f'https://api.taostats.io/api/account/history/v1?address={address}&limit=30'),
    ('validator/latest (multi)', f'https://api.taostats.io/api/validator/latest/v1?hotkey={address}&limit=50'),
    ('subnet validators', f'https://api.taostats.io/api/validators/v1?hotkey={address}'),
    ('transaction history', f'https://api.taostats.io/api/extrinsic/v1?address={address}&limit=30'),
    ('transfer history', f'https://api.taostats.io/api/transfer/v1?address={address}&limit=30'),
]

for name, endpoint in endpoints:
    try:
        print(f'\n=== {name} ===')
        resp = requests.get(endpoint, timeout=5)
        print(f'Status: {resp.status_code}')
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                print(f'Keys: {list(data.keys())}')
                if 'data' in data and isinstance(data['data'], list):
                    print(f'Record count: {len(data["data"])}')
                    if len(data['data']) > 0:
                        print(f'Sample:\n{json.dumps(data["data"][0], indent=2)[:600]}')
            elif isinstance(data, list):
                print(f'List length: {len(data)}')
                if len(data) > 0:
                    print(f'Sample:\n{json.dumps(data[0], indent=2)[:600]}')
        elif resp.status_code == 400:
            print(f'400 Bad Request - likely parameter issue')
            try:
                print(f'Error: {resp.json()}')
            except:
                print(f'Response: {resp.text[:200]}')
    except Exception as e:
        print(f'Error: {e}')
