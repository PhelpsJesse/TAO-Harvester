# Taostats API Research: Alpha Earnings & Historical Balance Data

**Research Date:** February 1, 2026  
**Purpose:** Identify best Taostats API endpoints for tracking daily alpha earnings by subnet

---

## Executive Summary

Based on Taostats API documentation and endpoint analysis, there are **NO dedicated "daily alpha dividend" tracking endpoints**. However, there are **5 highly promising endpoints** that can reconstruct daily alpha earnings:

1. **Hotkey Emissions** (Primary) - Get daily emission data per validator per subnet
2. **Validator Alpha Shares** (Primary) - Track alpha holdings and share distribution
3. **Validator History** (Secondary) - Track stake/alpha balance changes over time
4. **Subnet Emission** (Secondary) - Track subnet-level emission pools
5. **Validator Yield** (Supplementary) - APY calculations for estimating daily earnings

---

## Top 5 Recommended Endpoints

### 1. **Get Hotkey Emissions** ⭐⭐⭐ (PRIMARY)

**Use Case:** Calculate daily alpha earnings per validator per subnet

**Endpoint:** `GET https://api.taostats.io/api/dtao/hotkey_emission/v1`

**Query Parameters:**
```python
{
    "hotkey": "5YOUR_HOTKEY_ADDRESS",      # Validator hotkey
    "netuid": 1,                             # Subnet ID
    "block_start": 5000000,                  # Optional: starting block
    "block_end": 5100000,                    # Optional: ending block
    "timestamp_start": 1706745600,           # Optional: Unix timestamp (seconds)
    "timestamp_end": 1706832000,             # Optional: Unix timestamp (seconds)
    "limit": 200,                            # Items per page (max 200)
    "page": 1,                               # Pagination
    "order": "timestamp_asc"                 # Options: block_number_asc/desc, timestamp_asc/desc, 
                                             #          netuid_asc/desc, emission_asc/desc
}
```

**Response Structure:**
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 50,
    "total_items": 1000,
    "total_pages": 20,
    "next_page": 2,
    "prev_page": null
  },
  "data": [
    {
      "block_number": 5373806,
      "timestamp": "2025-04-17T21:14:48Z",
      "netuid": 1,
      "hotkey": {
        "ss58": "5GKH9FPPnWSUoeeTJp19wVtd84XqFW4pyK2ijV2GsFbhTrP1",
        "hex": "0xbc0e6b701243978c1fe73d721c7b157943a713fca9f3c88cad7a9f7799bc6b26"
      },
      "emission": "150000000000",           # In rao (divide by 1e9 for TAO/Alpha)
      "root_emission": "50000000000"        # Root network emission in rao
    }
  ]
}
```

**Implementation Example:**
```python
import requests
from datetime import datetime, timedelta

def get_daily_alpha_emissions(hotkey: str, netuid: int, date: str, api_key: str):
    """Get alpha emissions for a specific day (YYYY-MM-DD)"""
    
    # Parse date and get Unix timestamps
    day_start = datetime.strptime(date, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    
    timestamp_start = int(day_start.timestamp())
    timestamp_end = int(day_end.timestamp())
    
    url = "https://api.taostats.io/api/dtao/hotkey_emission/v1"
    headers = {"Authorization": api_key}
    
    params = {
        "hotkey": hotkey,
        "netuid": netuid,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "limit": 200,
        "order": "timestamp_asc"
    }
    
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    
    # Sum all emissions for the day
    total_alpha = 0
    for entry in data['data']:
        alpha_rao = entry.get('emission', 0)
        total_alpha += alpha_rao / 1e9  # Convert to TAO
    
    return {
        "date": date,
        "hotkey": hotkey,
        "netuid": netuid,
        "total_alpha_tao": total_alpha,
        "raw_entries": len(data['data'])
    }
```

**Rate Limit:** 5 requests/minute (12 second delay between requests)

**Notes:**
- Returns timestamped emission entries
- Can filter by block range OR timestamp range
- Perfect for day-to-day delta calculations
- Supports historical data lookback

---

### 2. **Get Validator Alpha Shares** ⭐⭐⭐ (PRIMARY)

**Use Case:** Track alpha balance changes and share distribution per subnet

**Endpoint:** `GET https://api.taostats.io/api/dtao/hotkey_alpha_shares/latest/v1`

**Query Parameters:**
```python
{
    "hotkey": "5YOUR_HOTKEY_ADDRESS",      # Validator hotkey
    "netuid": 1,                             # Subnet ID
    "alpha_min": "0",                        # Filter by alpha range (in nanoAlpha)
    "alpha_max": "999999999999999999999",    # Upper bound
    "page": 1,
    "limit": 200,
    "order": "netuid_desc"                   # Options: netuid_asc/desc, shares_asc/desc, alpha_asc/desc
}
```

**Response Structure:**
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 50,
    "total_items": 88,
    "total_pages": 2
  },
  "data": [
    {
      "block_number": 5373806,
      "timestamp": "2025-04-17T21:14:48Z",
      "netuid": 1,
      "hotkey": {
        "ss58": "5GKH9FPPnWSUoeeTJp19wVtd84XqFW4pyK2ijV2GsFbhTrP1",
        "hex": "0xbc0e6b701243978c1fe73d721c7b157943a713fca9f3c88cad7a9f7799bc6b26"
      },
      "shares": "13890034603543431171280295544634012",  # Share count
      "alpha": "1523876432100500000000"                 # Alpha balance (in nanoAlpha, divide by 1e9 for actual alpha)
    }
  ]
}
```

**Implementation Example:**
```python
def get_alpha_balance_snapshot(hotkey: str, netuid: int, api_key: str):
    """Get current alpha balance and shares for validator"""
    
    url = "https://api.taostats.io/api/dtao/hotkey_alpha_shares/latest/v1"
    headers = {"Authorization": api_key}
    
    params = {
        "hotkey": hotkey,
        "netuid": netuid
    }
    
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    
    if not data['data']:
        return None
    
    entry = data['data'][0]
    
    return {
        "timestamp": entry['timestamp'],
        "netuid": entry['netuid'],
        "alpha_balance": int(entry['alpha']) / 1e9,  # Convert nanoAlpha to alpha
        "shares": int(entry['shares']),
        "block_number": entry['block_number']
    }


def calculate_daily_alpha_delta(hotkey: str, netuid: int, prev_snapshot, api_key: str):
    """Calculate alpha earned today by comparing snapshots"""
    
    current = get_alpha_balance_snapshot(hotkey, netuid, api_key)
    if not current or not prev_snapshot:
        return None
    
    alpha_earned = current['alpha_balance'] - prev_snapshot['alpha_balance']
    
    return {
        "date": datetime.utcnow().date(),
        "netuid": netuid,
        "alpha_earned": alpha_earned,
        "previous_balance": prev_snapshot['alpha_balance'],
        "current_balance": current['alpha_balance']
    }
```

**Rate Limit:** 5 requests/minute

**Notes:**
- Provides current snapshot (not historical)
- For historical snapshots, must track `/historical` endpoint
- Better for tracking balance deltas than absolute emissions
- Accounts for stake delegations affecting shares

---

### 3. **Get Validator History** ⭐⭐ (SECONDARY - BEST FOR BALANCE TRACKING)

**Use Case:** Historical balance snapshots to calculate daily alpha accrual

**Endpoint:** `GET https://api.taostats.io/api/dtao/validator/history/v1`

**Query Parameters:**
```python
{
    "hotkey": "5YOUR_HOTKEY_ADDRESS",      # Validator hotkey (required for filtering)
    "netuid": 1,                             # Optional: Subnet ID
    "block_start": 5000000,                  # Optional: Starting block
    "block_end": 5100000,                    # Optional: Ending block
    "timestamp_start": 1706745600,           # Optional: Unix timestamp
    "timestamp_end": 1706832000,             # Optional: Unix timestamp
    "page": 1,
    "limit": 200,
    "order": "timestamp_asc"                 # Options: timestamp_asc/desc, block_number_asc/desc
}
```

**Response Structure:**
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 50,
    "total_items": 365,
    "total_pages": 8
  },
  "data": [
    {
      "hotkey": {
        "ss58": "5GKH9FPPnWSUoeeTJp19wVtd84XqFW4pyK2ijV2GsFbhTrP1",
        "hex": "0xbc0e6b701243978c1fe73d721c7b157943a713fca9f3c88cad7a9f7799bc6b26"
      },
      "name": "Validator Name",
      "block_number": 5373806,
      "timestamp": "2025-04-17T21:14:48Z",
      "netuid": 1,
      "stake": "797764970178086",              # In rao (divide by 1e9)
      "stake_24h_change": "-12345678901",     # In rao
      "emission": "790856951071",              # Nominator return in rao
      "validator_return": "78214435626",       # Per day return in rao
      "alpha_stake": "152287191316855",        # Alpha staked in rao
      "alpha_stake_as_tao": "152287191316855", # Already converted?
      "dominance": "14.10",                    # As percentage string
      "dominance_24h_change": "0.04"
    }
  ]
}
```

**Implementation Example:**
```python
def get_validator_balance_history(hotkey: str, netuid: int, days: int = 30, api_key: str = ""):
    """Get daily validator history for last N days"""
    
    url = "https://api.taostats.io/api/dtao/validator/history/v1"
    headers = {"Authorization": api_key}
    
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    timestamp_start = int(start_date.timestamp())
    timestamp_end = int(now.timestamp())
    
    all_entries = []
    page = 1
    
    while True:
        params = {
            "hotkey": hotkey,
            "netuid": netuid,
            "timestamp_start": timestamp_start,
            "timestamp_end": timestamp_end,
            "page": page,
            "limit": 200,
            "order": "timestamp_asc"
        }
        
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        all_entries.extend(data['data'])
        
        if data['pagination']['next_page'] is None:
            break
        
        page += 1
    
    # Convert to daily snapshots
    daily_snapshots = {}
    for entry in all_entries:
        date_key = entry['timestamp'].split('T')[0]
        
        # Keep last entry of the day (most recent)
        daily_snapshots[date_key] = {
            "timestamp": entry['timestamp'],
            "alpha_stake_tao": float(entry.get('alpha_stake_as_tao', 0)) / 1e9,
            "total_stake_tao": float(entry.get('stake', 0)) / 1e9,
            "validator_return_tao": float(entry.get('validator_return', 0)) / 1e9
        }
    
    return daily_snapshots


def calculate_daily_alpha_from_history(hotkey: str, netuid: int, api_key: str):
    """Calculate daily alpha changes from history"""
    
    history = get_validator_balance_history(hotkey, netuid, days=90, api_key=api_key)
    
    daily_deltas = {}
    prev_date = None
    prev_balance = 0
    
    for date in sorted(history.keys()):
        current_balance = history[date]['alpha_stake_tao']
        
        if prev_date:
            daily_deltas[date] = {
                "alpha_earned": current_balance - prev_balance,
                "validator_return": history[date]['validator_return_tao']
            }
        
        prev_balance = current_balance
        prev_date = date
    
    return daily_deltas
```

**Rate Limit:** 5 requests/minute

**Notes:**
- Provides daily snapshots (but infrequent)
- Best for week-over-week or month-over-month analysis
- Does NOT provide emission-level granularity
- Includes both alpha and TAO stake data

---

### 4. **Get Subnet Emission** ⭐⭐ (SECONDARY - SUBNET LEVEL)

**Use Case:** Total daily alpha emissions per subnet (pool-level data)

**Endpoint:** `GET https://api.taostats.io/api/dtao/subnet_emission/v1`

**Query Parameters:**
```python
{
    "netuid": 1,                             # Subnet ID (required)
    "block_start": 5000000,                  # Optional
    "block_end": 5100000,                    # Optional
    "page": 1,
    "limit": 200,
    "order": "timestamp_asc"                 # Options: block_number_asc/desc, timestamp_asc/desc
}
```

**Response Structure:**
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 50,
    "total_items": 1000
  },
  "data": [
    {
      "block_number": 5373806,
      "timestamp": "2025-04-17T21:14:48Z",
      "netuid": 1,
      "alpha_in_pool": "500000000000",           # Total alpha in subnet pool (in rao)
      "tao_in_pool": "1000000000000",            # Total TAO in pool (in rao)
      "emission": "100000000000",                # Daily emission in rao
      "total_alpha_staked": "250000000000",      # Total staked alpha (in rao)
      "total_tao_staked": "750000000000"         # Total staked TAO (in rao)
    }
  ]
}
```

**Implementation Example:**
```python
def get_subnet_daily_emissions(netuid: int, date: str, api_key: str):
    """Get total subnet alpha emissions for a specific day"""
    
    url = "https://api.taostats.io/api/dtao/subnet_emission/v1"
    headers = {"Authorization": api_key}
    
    day_start = datetime.strptime(date, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    
    timestamp_start = int(day_start.timestamp())
    timestamp_end = int(day_end.timestamp())
    
    params = {
        "netuid": netuid,
        "timestamp_start": timestamp_start,
        "timestamp_end": timestamp_end,
        "limit": 200,
        "order": "timestamp_asc"
    }
    
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    
    total_emission_tao = 0
    pool_snapshots = []
    
    for entry in data['data']:
        emission_tao = float(entry['emission']) / 1e9
        total_emission_tao += emission_tao
        
        pool_snapshots.append({
            "timestamp": entry['timestamp'],
            "alpha_in_pool_tao": float(entry['alpha_in_pool']) / 1e9,
            "emission_tao": emission_tao
        })
    
    return {
        "date": date,
        "netuid": netuid,
        "total_daily_emission_tao": total_emission_tao,
        "pool_snapshots": pool_snapshots,
        "num_samples": len(pool_snapshots)
    }
```

**Rate Limit:** 5 requests/minute

**Notes:**
- Shows total subnet emission pool (all validators combined)
- Useful for calculating validator share of total emissions
- Can combine with hotkey_emission to get % of subnet

---

### 5. **Get Validator Yield** ⭐ (SUPPLEMENTARY)

**Use Case:** Calculate estimated daily alpha from APY metrics

**Endpoint:** `GET https://api.taostats.io/api/dtao/validator/yield/latest/v1`

**Query Parameters:**
```python
{
    "hotkey": "5YOUR_HOTKEY_ADDRESS",      # Optional: filter by hotkey
    "netuid": 1,                             # Optional: subnet ID
    "min_stake": "1000000000",               # Optional: minimum stake in rao
    "page": 1,
    "limit": 200,
    "order": "one_day_apy_desc"             # Options: one_day_apy_asc/desc, seven_day_apy_asc/desc, etc.
}
```

**Response Structure:**
```json
{
  "pagination": {
    "current_page": 1,
    "per_page": 50,
    "total_items": 2605
  },
  "data": [
    {
      "hotkey": {
        "ss58": "5GKH9FPPnWSUoeeTJp19wVtd84XqFW4pyK2ijV2GsFbhTrP1"
      },
      "name": "Validator Name",
      "netuid": 1,
      "block_number": 5373830,
      "timestamp": "2025-04-17T21:19:36Z",
      "stake": "797764970178086",           # In rao
      "one_hour_apy": "0.1957403658346058508731763447",
      "one_day_apy": "0.1958641988377613847261875705",
      "seven_day_apy": "0.20796523177254449036165",
      "thirty_day_apy": "0.21373806029020066287845",
      "one_day_epoch_participation": "1",
      "seven_day_epoch_participation": "1",
      "thirty_day_epoch_participation": "1"
    }
  ]
}
```

**Implementation Example:**
```python
def estimate_daily_alpha_from_apy(hotkey: str, netuid: int, alpha_stake_tao: float, api_key: str):
    """Estimate daily alpha earnings using APY metrics"""
    
    url = "https://api.taostats.io/api/dtao/validator/yield/latest/v1"
    headers = {"Authorization": api_key}
    
    params = {
        "hotkey": hotkey,
        "netuid": netuid
    }
    
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    
    if not data['data']:
        return None
    
    entry = data['data'][0]
    
    one_day_apy = float(entry['one_day_apy'])
    
    # Calculate estimated daily earnings
    estimated_daily_alpha = alpha_stake_tao * one_day_apy
    
    return {
        "hotkey": hotkey,
        "netuid": netuid,
        "alpha_staked": alpha_stake_tao,
        "one_day_apy": one_day_apy,
        "estimated_daily_alpha": estimated_daily_alpha,
        "seven_day_apy": float(entry['seven_day_apy']),
        "thirty_day_apy": float(entry['thirty_day_apy']),
        "timestamp": entry['timestamp']
    }
```

**Rate Limit:** 5 requests/minute

**Notes:**
- APY-based estimates (not actual earnings)
- Use for forecasting, not accounting
- Should cross-check against hotkey_emission for accuracy

---

## Alternative Approaches (No Dedicated Endpoints)

### Approach A: Manual Daily Snapshots
Since no "dividend tracking" endpoint exists, implement daily snapshots:

```python
def create_daily_alpha_tracking(hotkey: str, netuid: int, api_key: str):
    """
    Strategy: Take daily snapshots and calculate deltas
    Run once per day (e.g., at 00:00 UTC)
    """
    
    snapshot = {
        "date": datetime.utcnow().date().isoformat(),
        "alpha_balance": get_alpha_balance_snapshot(hotkey, netuid, api_key),
        "emissions": get_daily_alpha_emissions(hotkey, netuid, 
                                                datetime.utcnow().date().isoformat(), 
                                                api_key),
        "yield_metrics": estimate_daily_alpha_from_apy(hotkey, netuid, 
                                                        get_alpha_balance_snapshot(hotkey, netuid, api_key)['alpha_balance'],
                                                        api_key)
    }
    
    # Store snapshot in database or CSV
    # Compare with previous day for delta calculation
    return snapshot
```

### Approach B: Block-Level Analysis
Query by block range to get granular emission data:

```python
def get_emissions_by_blocks(hotkey: str, netuid: int, block_start: int, block_end: int, api_key: str):
    """
    Query emissions across specific block range
    ~6 blocks per minute on Bittensor = 8640 blocks per day
    """
    
    url = "https://api.taostats.io/api/dtao/hotkey_emission/v1"
    headers = {"Authorization": api_key}
    
    params = {
        "hotkey": hotkey,
        "netuid": netuid,
        "block_start": block_start,
        "block_end": block_end,
        "limit": 200,
        "order": "block_number_asc"
    }
    
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    
    total_alpha = sum(float(e['emission']) / 1e9 for e in data['data'])
    
    return {
        "block_range": f"{block_start}-{block_end}",
        "total_alpha_earned": total_alpha,
        "num_emissions": len(data['data'])
    }
```

---

## Key Limitations & Workarounds

| Issue | Impact | Workaround |
|-------|--------|-----------|
| No dedicated "daily dividend" endpoint | Can't directly query alpha accrued per day | Use hotkey_emission + time filtering |
| Accounting endpoints behind paywall | Can't access tax/detailed accounting | Use free dTAO endpoints instead |
| Historical alpha shares limited | Difficult to track alpha balance history | Use validator/history + snapshots |
| Rate limit: 5 req/min | Slow for multi-validator tracking | Cache results, implement request queue |
| Multi-validator setups incomplete | Some validators missing from data | Cross-reference with RPC for accuracy |

---

## Recommended Implementation Strategy

### For Daily Alpha Earnings Tracking:

```
Priority 1: /api/dtao/hotkey_emission/v1
  - Query with timestamp_start/timestamp_end for each day
  - Sum all emission entries
  - Run daily at 00:00 UTC

Priority 2: /api/dtao/hotkey_alpha_shares/latest/v1
  - Take snapshot daily
  - Compare snapshots for delta calculation
  - Validate against Priority 1 data

Priority 3: /api/dtao/validator/history/v1
  - Weekly snapshots for aggregated view
  - Useful for reconciliation

Fallback: /api/dtao/validator/yield/latest/v1
  - Estimate APY-based earnings for forecasting only
  - Do not use for accounting
```

### For Multi-Subnet Breakdown:

```
For each subnet in validator's registrations:
  - Call hotkey_emission with netuid parameter
  - Aggregate results by date
  - Store in daily_earnings table:
    date | netuid | alpha_earned | validator_hotkey | emissions_count
```

---

## Code Template: Complete Daily Alpha Tracking

```python
"""
Complete implementation for daily alpha earnings tracking
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List

class AlphaEarningsTracker:
    BASE_URL = "https://api.taostats.io"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": api_key}
    
    def get_daily_emissions(self, hotkey: str, netuid: int, date: str) -> Dict:
        """Primary method: Get alpha emissions for specific day"""
        
        day_start = datetime.strptime(date, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        
        url = f"{self.BASE_URL}/api/dtao/hotkey_emission/v1"
        params = {
            "hotkey": hotkey,
            "netuid": netuid,
            "timestamp_start": int(day_start.timestamp()),
            "timestamp_end": int(day_end.timestamp()),
            "limit": 200,
            "order": "timestamp_asc"
        }
        
        response = requests.get(url, params=params, headers=self.headers)
        data = response.json()
        
        total_alpha = sum(float(e['emission']) / 1e9 for e in data['data'])
        
        return {
            "date": date,
            "hotkey": hotkey,
            "netuid": netuid,
            "alpha_earned_tao": total_alpha,
            "num_emissions": len(data['data']),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_subnet_breakdown(self, hotkey: str, subnets: List[int], date: str) -> List[Dict]:
        """Get alpha earnings broken down by subnet"""
        
        results = []
        for netuid in subnets:
            earnings = self.get_daily_emissions(hotkey, netuid, date)
            results.append(earnings)
        
        return results

# Usage:
# tracker = AlphaEarningsTracker(api_key="your_api_key")
# today = datetime.utcnow().date().isoformat()
# daily_earnings = tracker.get_daily_emissions("5YOUR_HOTKEY", 1, today)
# print(f"Alpha earned today: {daily_earnings['alpha_earned_tao']} TAO")
```

---

## Summary Table

| Endpoint | Purpose | Data Freshness | Granularity | Use Case |
|----------|---------|-----------------|-------------|----------|
| `hotkey_emission/v1` | Daily alpha per validator | Real-time | Per block | ⭐ Primary earnings tracking |
| `hotkey_alpha_shares/latest/v1` | Alpha balance snapshot | Real-time | Current only | ⭐ Balance delta calculation |
| `validator/history/v1` | Historical validator data | Real-time | Daily snapshots | Historical analysis & reconciliation |
| `subnet_emission/v1` | Pool-level emissions | Real-time | Per block | Subnet benchmarking |
| `validator/yield/latest/v1` | APY metrics | Real-time | Current only | Forecasting only |

---

## Next Steps

1. **Implement Daily Snapshots:** Add daily task to capture hotkey_emission data
2. **Create Alpha Earnings Table:** Store daily_alpha with date/netuid/amount
3. **Add Multi-Subnet Support:** Loop through all registered subnets
4. **Cross-Validate:** Compare hotkey_emission with alpha_shares deltas
5. **Monitor Accuracy:** Alert if daily totals diverge > 5% from expectations

---

## References

- Taostats API Docs: https://docs.taostats.io/reference/welcome-to-the-taostats-api
- GitHub Examples: https://github.com/taostat/awesome-taostats-api-examples
- Rate Limit: 5 requests/minute (implement 12-second delay)
- All amounts in rao (1 TAO = 1e9 rao)
