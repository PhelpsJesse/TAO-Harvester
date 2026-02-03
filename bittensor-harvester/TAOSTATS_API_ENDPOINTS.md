# Taostats API Endpoints Documentation

## Base Information

**API Base URL:** `https://api.taostats.io`

**API Key:** Required for all requests (get one at https://dash.taostats.io)

**Get API Key:** Visit https://dash.taostats.io to obtain your API key

## Authentication

All API requests require an Authorization header with your API key:

```python
headers = {
    "accept": "application/json",
    "Authorization": api_key
}
```

Or with environment variables:

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('taostats_api')

headers = {
    "accept": "application/json",
    "Authorization": api_key
}
```

## Core Endpoint Patterns

All endpoints follow this URL structure:
```
https://api.taostats.io/api/{endpoint}/v1?{query_parameters}
```

### Common Query Parameters

- `page` - Page number for pagination (starts at 1)
- `limit` - Number of items per page (max typically 200)
- `order` - Sort order (e.g., `timestamp_asc`, `timestamp_desc`, `stake_desc`)

### Pagination Response Structure

```json
{
  "data": [...],
  "pagination": {
    "total_items": 1000,
    "total_pages": 5,
    "next_page": 2
  }
}
```

## Validator Endpoints

### Get Latest Validators

**Endpoint:** `/api/validator/latest/v1`

```python
# Get top 25 validators by stake
url = "https://api.taostats.io/api/validator/latest/v1?limit=25&order=stake_desc"
response = requests.get(url, headers=headers)
data = response.json()

for validator in data['data']:
    hotkey = validator['hotkey']['ss58']
    stake = float(validator['stake']) / 1e9  # Convert from rao to TAO
    name = validator['name'] or hotkey[:5]
    print(f"{name}: {stake} TAO")
```

**Query Parameters:**
- `hotkey` - Filter by specific validator hotkey
- `limit` - Number of results (default varies)
- `order` - Sort by: `stake_desc`, `stake_asc`, etc.

**Response Fields:**
- `hotkey` - Object with `ss58` address
- `stake` - Stake amount in rao (divide by 1e9 for TAO)
- `name` - Validator name
- `stake_24h_change` - 24h stake change

### Get Validator by Hotkey

```python
url = f"https://api.taostats.io/api/validator/latest/v1?hotkey={hotkey}"
response = requests.get(url, headers=headers)
validator = response.json()['data'][0]
```

## Earnings and Accounting Endpoints

### Account History (Balance History)

**Endpoint:** `/api/account/history/v1`

```python
url = f"https://api.taostats.io/api/account/history/v1?address={coldkey}&timestamp_start={start_date}&timestamp_end={end_date}&limit=200&page={page}&order=timestamp_asc"

response = requests.get(url, headers=headers)
data = response.json()

for entry in data['data']:
    timestamp = entry['timestamp']
    balance_total = float(entry['balance_total']) / 1e9  # TAO
    balance_staked = float(entry['balance_staked']) / 1e9  # TAO
    balance_free = float(entry['balance_free']) / 1e9  # TAO
```

**Query Parameters:**
- `address` - Coldkey address (required)
- `timestamp_start` - Start timestamp (Unix seconds)
- `timestamp_end` - End timestamp (Unix seconds)
- `page` - Page number
- `limit` - Items per page
- `order` - `timestamp_asc` or `timestamp_desc`

**Response Fields:**
- `timestamp` - ISO format: "YYYY-MM-DDTHH:MM:SS" or "YYYY-MM-DDTHH:MM:SS.SSSZ"
- `balance_total` - Total balance in rao
- `balance_staked` - Staked amount in rao
- `balance_free` - Free (unstaked) amount in rao

### Accounting Data (Emissions and Income)

**Endpoint:** `/api/accounting/v1`

```python
url = f"https://api.taostats.io/api/accounting/v1?network={network}&date_start={start_date}&date_end={end_date}&coldkey={coldkey}&page={page}"

response = requests.get(url, headers=headers)
data = response.json()

for record in data['data']:
    date = record['date']
    hotkey = record['hotkey']
    emission = float(record['emission']) / 1e9  # TAO earned
```

**Query Parameters:**
- `network` - Network name: "finney", "nakamoto", "kusanagi"
- `date_start` - Start date: "YYYY-MM-DD"
- `date_end` - End date: "YYYY-MM-DD"
- `coldkey` - Coldkey address
- `page` - Page number

**Response Fields:**
- `date` - Date of emission
- `hotkey` - Associated hotkey
- `emission` - Emission amount in rao
- `network` - Network name

### Tax/Token Accounting

**Endpoint:** `/api/accounting/tax_token/v1`

```python
url = f"https://api.taostats.io/api/accounting/tax_token/v1?date_start={start_date}&date_end={end_date}&coldkey={coldkey}"

response = requests.get(url, headers=headers)
```

## Subnet Endpoints

### Get Latest Subnets

**Endpoint:** `/api/subnet/latest/v1`

```python
url = "https://api.taostats.io/api/subnet/latest/v1"
response = requests.get(url, headers=headers)
data = response.json()

number_of_subnets = data['pagination']['total_items']

for subnet in data['data']:
    netuid = subnet['netuid']
    emission = float(subnet['emission']) / 1e9
    name = subnet['name']
    commit_reveal_enabled = subnet['commit_reveal_weights_enabled']
```

**Response Fields:**
- `netuid` - Subnet network unique ID
- `emission` - Current emission in rao
- `name` - Subnet name
- `commit_reveal_weights_enabled` - Boolean flag

### Subnet History

**Endpoint:** `/api/subnet/history/v1`

```python
url = f"https://api.taostats.io/api/subnet/history/v1?netuid={netuid}&limit={num_days}&order=timestamp_desc"

response = requests.get(url, headers=headers)
data = response.json()
```

**Query Parameters:**
- `netuid` - Subnet ID (required)
- `limit` - Number of history records
- `order` - `timestamp_desc`, `timestamp_asc`

## Delegation Endpoints

### Get Delegation Events

**Endpoint:** `/api/delegation/v1`

```python
# Last 24 hours (7200 blocks)
url = f"https://api.taostats.io/api/delegation/v1?page={page}&limit=200&block_start={block_start}&block_end={block_end}"

response = requests.get(url, headers=headers)
data = response.json()

for delegation in data['data']:
    hotkey = delegation['delegate']['ss58']
    amount = float(delegation['amount']) / 1e9  # TAO
    action = delegation['action']  # "DELEGATE" or "UNDELEGATE"
    timestamp = delegation['timestamp']
```

**Query Parameters:**
- `nominator` - Filter by nominator address
- `delegate` - Filter by delegate address
- `block_start` - Start block number
- `block_end` - End block number
- `timestamp_start` - Start timestamp
- `timestamp_end` - End timestamp
- `page` - Page number
- `limit` - Items per page

**Response Fields:**
- `delegate` - Object with `ss58` hotkey
- `amount` - Delegation amount in rao
- `action` - "DELEGATE" or "UNDELEGATE"
- `timestamp` - ISO timestamp
- `block_number` - Block number

### Get Delegation for Specific Nominator

```python
url = f"https://api.taostats.io/api/delegation/v1?nominator={coldkey}&timestamp_start={start_date}&timestamp_end={end_date}&limit=200&page={page}&order=block_number_asc"
```

## Block Endpoints

### Get Current Block

**Endpoint:** `/api/block/v1`

```python
url = "https://api.taostats.io/api/block/v1?limit=1"
response = requests.get(url, headers=headers)
data = response.json()

current_block = data['data'][0]['block_number']
block_24h_ago = current_block - 7200  # 7200 blocks ≈ 24 hours
```

**Response Fields:**
- `block_number` - Current block number
- `timestamp` - Block timestamp

## dTAO (Dynamic TAO) Endpoints

### Subnet Emission (Alpha/dTAO)

**Endpoint:** `/api/dtao/subnet_emission/v1`

```python
url = f"https://api.taostats.io/api/dtao/subnet_emission/v1?netuid={netuid}&block_start={block_start}&block_end={block_end}&page={page}&limit=200"

response = requests.get(url, headers=headers)
data = response.json()

for emission in data['data']:
    tao_in_pool = float(emission['tao_in_pool']) / 1e9
    timestamp = emission['timestamp']
    block_number = emission['block_number']
```

### Hotkey Emission (Alpha Emissions by Validator)

**Endpoint:** `/api/dtao/hotkey_emission/v1`

```python
url = f"https://api.taostats.io/api/dtao/hotkey_emission/v1?block_number={block_number}&netuid={netuid}&limit=200&order=emission_desc"

response = requests.get(url, headers=headers)
data = response.json()

for validator in data['data']:
    hotkey = validator['hotkey']['ss58']
    emission = float(validator['emission']) / 1e9  # TAO equivalent
```

### Pool Info (Alpha Pool Data)

**Endpoint:** `/api/dtao/pool/latest/v1`

```python
url = f"https://api.taostats.io/api/dtao/pool/latest/v1?netuid={netuid}&page=1"

response = requests.get(url, headers=headers)
data = response.json()

pool = data['data'][0]
total_alpha = float(pool['total_alpha']) / 1e9
alpha_in_pool = float(pool['alpha_in_pool']) / 1e9
alpha_staked = float(pool['alpha_staked']) / 1e9
alpha_price = float(pool['price'])
```

### Stake Balance History

**Endpoint:** `/api/dtao/stake_balance/latest/v1`

```python
url = f"https://api.taostats.io/api/dtao/stake_balance/latest/v1?coldkey={coldkey}"

response = requests.get(url, headers=headers)
data = response.json()

for stake_entry in data['data']:
    netuid = stake_entry['netuid']
    amount = float(stake_entry['amount']) / 1e9
    token_type = stake_entry['token_type']  # "alpha", "tao"
```

### Burned Alpha

**Endpoint:** `/api/dtao/burned_alpha/v1`

```python
url = f"https://api.taostats.io/api/dtao/burned_alpha/v1?netuid={netuid}&block_start={block_start}&block_end={block_end}"

response = requests.get(url, headers=headers)
data = response.json()

for burn in data['data']:
    amount = float(burn['amount']) / 1e9
    timestamp = burn['timestamp']
```

## Metagraph Endpoints

### Root Metagraph History (Validator Weights)

**Endpoint:** `/api/metagraph/root/history/v1`

```python
url = f"https://api.taostats.io/api/metagraph/root/history/v1?block_start={block_start}&block_end={block_end}&page={page}&limit=200"

response = requests.get(url, headers=headers)
data = response.json()

for validator_data in data['data']:
    hotkey = validator_data['hotkey']['ss58']
    stake = float(validator_data['stake']) / 1e9
    subnet_weights = validator_data['subnet_weights']  # Dict of netuid: weight
    
    for netuid, weight in subnet_weights.items():
        print(f"Validator {hotkey} weight on subnet {netuid}: {weight}")
```

## Extrinsic Endpoints

### Get Extrinsics

**Endpoint:** `/api/extrinsic/v1`

```python
url = f"https://api.taostats.io/api/extrinsic/v1?signer_address={coldkey}&page={page}&limit={count}"

response = requests.get(url, headers=headers)
data = response.json()

for extrinsic in data['data']:
    call_name = extrinsic['call_args']
    block_number = extrinsic['block_number']
    timestamp = extrinsic['timestamp']
```

**Query Parameters:**
- `signer_address` - Address that signed the extrinsic
- `full_name` - Filter by extrinsic name (e.g., "SubtensorModule.set_weights")
- `page` - Page number
- `limit` - Items per page

### Get Call Events

**Endpoint:** `/api/call/v1`

```python
url = f"https://api.taostats.io/api/call/v1?full_name=SubtensorModule.vote&block_start={block_start}"

response = requests.get(url, headers=headers)
data = response.json()
```

## Complete Python Example with APIClient

```python
import requests
import json
import time
from typing import Optional, Dict, Any

class APIClient:
    """Client for Taostats API with retry logic"""
    
    def __init__(self, base_url: str, api_key: str = None, max_retries: int = 3, retry_delay: int = 60):
        self.base_url = base_url
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.headers = {
            "accept": "application/json"
        }
    
    def get_json(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Dict]:
        """Make API request with retry logic for rate limiting"""
        
        if self.api_key:
            self.headers['Authorization'] = self.api_key
        
        url = f"{self.base_url}{endpoint}"
        retries = 0
        
        while retries <= self.max_retries:
            try:
                response = requests.get(url, params=params, headers=self.headers)
                
                if response.status_code == 429:
                    # Rate limit exceeded
                    retry_after = int(response.headers.get('Retry-After', self.retry_delay))
                    print(f'Rate limit exceeded, retrying in {retry_after} seconds...')
                    time.sleep(retry_after)
                    retries += 1
                    
                elif response.status_code == 200:
                    return response.json()
                    
                else:
                    print(f'Error {response.status_code}: {response.text}')
                    return None
                    
            except requests.RequestException as e:
                print(f'Error: {e}')
                return None
        
        print('Too many retries, returning None')
        return None

# Usage
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('taostats_api')
    
    # Initialize client
    client = APIClient(base_url='https://api.taostats.io', api_key=api_key)
    
    # Get top validators
    response = client.get_json('/api/validator/latest/v1', params={'limit': 25, 'order': 'stake_desc'})
    
    if response:
        for validator in response['data']:
            print(f"{validator['name']}: {float(validator['stake'])/1e9:.2f} TAO")
```

## Rate Limiting

- API respects `Retry-After` header
- Recommended delays: 1 second between requests
- Maximum retry delay: 60 seconds
- Always check pagination to avoid unnecessary requests

## Common Patterns

### Pagination Loop

```python
page = 1
total_pages = 1
all_data = []

while page <= total_pages:
    params = {'page': page, 'limit': 200}
    response = client.get_json(endpoint, params=params)
    
    if response:
        all_data.extend(response['data'])
        total_pages = response['pagination']['total_pages']
        page += 1
    else:
        break
```

### Timestamp Handling

```python
# Sometimes returns milliseconds, sometimes doesn't
def parse_timestamp(timestamp_str):
    if len(timestamp_str) > 20:
        # Has milliseconds
        return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        # No milliseconds
        return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
```

### Convert Rao to TAO

```python
# All amounts are in rao (smallest unit)
# 1 TAO = 1e9 rao
amount_in_tao = float(amount_in_rao) / 1e9
```

## Getting Your API Key

1. Visit https://dash.taostats.io
2. Sign up or log in
3. Generate API key
4. Store in `.env` file as `taostats_api=<your_key>`
