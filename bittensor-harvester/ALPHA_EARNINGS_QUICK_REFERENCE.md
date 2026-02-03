# Quick Reference: Daily Alpha Earnings API Calls

**File for copying quick code snippets for daily alpha tracking**

---

## One-Liner: Get Today's Alpha Earnings

```python
# Get alpha earned today for validator on subnet 1
import requests
from datetime import datetime, timedelta

api_key = "your_api_key"
hotkey = "5YOUR_HOTKEY"
netuid = 1

day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
day_end = day_start + timedelta(days=1)

url = "https://api.taostats.io/api/dtao/hotkey_emission/v1"
params = {
    "hotkey": hotkey,
    "netuid": netuid,
    "timestamp_start": int(day_start.timestamp()),
    "timestamp_end": int(day_end.timestamp()),
    "limit": 200
}

response = requests.get(url, params=params, headers={"Authorization": api_key})
data = response.json()

total_alpha_tao = sum(float(e['emission']) / 1e9 for e in data['data'])
print(f"Alpha earned today (subnet {netuid}): {total_alpha_tao:.4f} TAO")
```

---

## Multi-Subnet Breakdown

```python
# Get alpha earnings broken down by all subnets
import requests
from datetime import datetime, timedelta

def get_all_subnet_earnings(hotkey, subnets, api_key):
    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    
    results = {}
    
    for netuid in subnets:
        url = "https://api.taostats.io/api/dtao/hotkey_emission/v1"
        params = {
            "hotkey": hotkey,
            "netuid": netuid,
            "timestamp_start": int(day_start.timestamp()),
            "timestamp_end": int(day_end.timestamp()),
            "limit": 200
        }
        
        response = requests.get(url, params=params, headers={"Authorization": api_key})
        data = response.json()
        
        total_alpha = sum(float(e['emission']) / 1e9 for e in data['data'])
        results[netuid] = total_alpha
        
        # 12 second delay to respect rate limits
        import time
        time.sleep(12)
    
    return results

# Usage:
# earnings = get_all_subnet_earnings("5YOUR_HOTKEY", [1, 3, 18, 25, 38, 39, 40], api_key)
# print(earnings)
# Output: {1: 0.1234, 3: 0.5678, 18: 0.9012, ...}
```

---

## Daily Snapshot Method

```python
# Take daily snapshot and compare with yesterday
import requests
from datetime import datetime, timedelta

def get_alpha_snapshot(hotkey, netuid, api_key):
    """Get current alpha balance via alpha shares endpoint"""
    url = "https://api.taostats.io/api/dtao/hotkey_alpha_shares/latest/v1"
    params = {"hotkey": hotkey, "netuid": netuid}
    
    response = requests.get(url, params=params, headers={"Authorization": api_key})
    data = response.json()
    
    if not data['data']:
        return None
    
    entry = data['data'][0]
    return {
        "timestamp": entry['timestamp'],
        "alpha_balance_tao": int(entry['alpha']) / 1e9,
        "shares": int(entry['shares'])
    }

def compare_daily_snapshots(hotkey, netuid, yesterday_snapshot, api_key):
    """Compare snapshots to calculate daily delta"""
    today_snapshot = get_alpha_snapshot(hotkey, netuid, api_key)
    
    if not today_snapshot or not yesterday_snapshot:
        return None
    
    alpha_earned = today_snapshot['alpha_balance_tao'] - yesterday_snapshot['alpha_balance_tao']
    
    return {
        "alpha_earned_tao": alpha_earned,
        "yesterday_balance": yesterday_snapshot['alpha_balance_tao'],
        "today_balance": today_snapshot['alpha_balance_tao']
    }

# Usage:
# yesterday = get_alpha_snapshot(hotkey, 1, api_key)
# [next day...]
# today = get_alpha_snapshot(hotkey, 1, api_key)
# delta = compare_daily_snapshots(hotkey, 1, yesterday, api_key)
# print(f"Alpha earned: {delta['alpha_earned_tao']:.4f} TAO")
```

---

## Historical Lookback (Last 7 Days)

```python
# Get last 7 days of alpha earnings
import requests
from datetime import datetime, timedelta

def get_last_n_days_earnings(hotkey, netuid, days=7, api_key=""):
    daily_earnings = {}
    
    for day_offset in range(days):
        target_date = (datetime.utcnow() - timedelta(days=day_offset)).date()
        date_str = target_date.isoformat()
        
        day_start = datetime.strptime(date_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        
        url = "https://api.taostats.io/api/dtao/hotkey_emission/v1"
        params = {
            "hotkey": hotkey,
            "netuid": netuid,
            "timestamp_start": int(day_start.timestamp()),
            "timestamp_end": int(day_end.timestamp()),
            "limit": 200,
            "order": "timestamp_asc"
        }
        
        response = requests.get(url, params=params, headers={"Authorization": api_key})
        data = response.json()
        
        total_alpha = sum(float(e['emission']) / 1e9 for e in data['data'])
        daily_earnings[date_str] = total_alpha
        
        import time
        time.sleep(12)  # Rate limit
    
    return daily_earnings

# Usage:
# earnings = get_last_n_days_earnings("5HOTKEY", 1, days=7, api_key="key")
# for date, amount in sorted(earnings.items()):
#     print(f"{date}: {amount:.4f} TAO")
```

---

## Get Subnet Total Emissions (For Benchmarking)

```python
# See how much alpha was emitted to entire subnet today
import requests
from datetime import datetime, timedelta

def get_subnet_total_emissions(netuid, api_key):
    today = datetime.utcnow().date()
    day_start = datetime.strptime(today.isoformat(), "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    
    url = "https://api.taostats.io/api/dtao/subnet_emission/v1"
    params = {
        "netuid": netuid,
        "timestamp_start": int(day_start.timestamp()),
        "timestamp_end": int(day_end.timestamp()),
        "limit": 200
    }
    
    response = requests.get(url, params=params, headers={"Authorization": api_key})
    data = response.json()
    
    total_emission = sum(float(e['emission']) / 1e9 for e in data['data'])
    
    return {
        "date": today.isoformat(),
        "netuid": netuid,
        "total_subnet_alpha_emission_tao": total_emission,
        "num_samples": len(data['data'])
    }

# Usage:
# subnet_total = get_subnet_total_emissions(1, api_key)
# print(f"Total alpha emitted to subnet 1: {subnet_total['total_subnet_alpha_emission_tao']} TAO")
```

---

## Estimate Daily Alpha from APY

```python
# Quick estimate of daily earnings using APY (forecast only!)
import requests

def estimate_daily_from_apy(hotkey, netuid, alpha_staked_tao, api_key):
    """FORECAST ONLY - not for accounting"""
    
    url = "https://api.taostats.io/api/dtao/validator/yield/latest/v1"
    params = {
        "hotkey": hotkey,
        "netuid": netuid
    }
    
    response = requests.get(url, params=params, headers={"Authorization": api_key})
    data = response.json()
    
    if not data['data']:
        return None
    
    entry = data['data'][0]
    one_day_apy = float(entry['one_day_apy'])
    
    estimated_daily = alpha_staked_tao * one_day_apy
    
    return {
        "alpha_staked": alpha_staked_tao,
        "one_day_apy": one_day_apy,
        "estimated_daily_alpha": estimated_daily,
        "note": "This is a forecast based on APY, not actual earnings"
    }

# Usage:
# estimate = estimate_daily_from_apy("5HOTKEY", 1, 1000.5, api_key)
# print(f"Estimated daily alpha: {estimate['estimated_daily_alpha']:.4f} TAO")
```

---

## Full Daily Report Generator

```python
# Generate complete daily report for validator
import requests
from datetime import datetime, timedelta
import json

class DailyAlphaReport:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.taostats.io"
    
    def generate_report(self, hotkey, subnets, date_str=None):
        """Generate complete daily alpha report"""
        
        if not date_str:
            date_str = datetime.utcnow().date().isoformat()
        
        report = {
            "date": date_str,
            "hotkey": hotkey,
            "generated_at": datetime.utcnow().isoformat(),
            "subnets": {},
            "totals": {"total_alpha_tao": 0, "total_emissions_count": 0}
        }
        
        day_start = datetime.strptime(date_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        ts_start = int(day_start.timestamp())
        ts_end = int(day_end.timestamp())
        
        for netuid in subnets:
            # Get hotkey emissions
            url = f"{self.base_url}/api/dtao/hotkey_emission/v1"
            params = {
                "hotkey": hotkey,
                "netuid": netuid,
                "timestamp_start": ts_start,
                "timestamp_end": ts_end,
                "limit": 200
            }
            
            response = requests.get(url, params=params, headers={"Authorization": self.api_key})
            data = response.json()
            
            alpha_earned = sum(float(e['emission']) / 1e9 for e in data['data'])
            
            report["subnets"][netuid] = {
                "alpha_earned_tao": alpha_earned,
                "num_emissions": len(data['data'])
            }
            
            report["totals"]["total_alpha_tao"] += alpha_earned
            report["totals"]["total_emissions_count"] += len(data['data'])
            
            import time
            time.sleep(12)
        
        return report

# Usage:
# reporter = DailyAlphaReport(api_key="your_key")
# report = reporter.generate_report(
#     "5YOUR_HOTKEY",
#     subnets=[1, 3, 18, 25, 38, 39, 40],
#     date_str="2026-02-01"
# )
# print(json.dumps(report, indent=2))
# 
# Output:
# {
#   "date": "2026-02-01",
#   "hotkey": "5YOUR_HOTKEY",
#   "subnets": {
#     "1": {"alpha_earned_tao": 0.1234, "num_emissions": 42},
#     "3": {"alpha_earned_tao": 0.5678, "num_emissions": 38},
#     ...
#   },
#   "totals": {
#     "total_alpha_tao": 5.1234,
#     "total_emissions_count": 300
#   }
# }
```

---

## Error Handling Template

```python
# Proper error handling and retry logic
import requests
import time
from typing import Optional, Dict

def get_emissions_with_retry(hotkey, netuid, date, api_key, max_retries=3):
    """Get emissions with exponential backoff retry"""
    
    day_start = datetime.strptime(date, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    
    url = "https://api.taostats.io/api/dtao/hotkey_emission/v1"
    params = {
        "hotkey": hotkey,
        "netuid": netuid,
        "timestamp_start": int(day_start.timestamp()),
        "timestamp_end": int(day_end.timestamp()),
        "limit": 200
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Authorization": api_key},
                timeout=10
            )
            
            if response.status_code == 429:  # Rate limited
                wait_time = int(response.headers.get('Retry-After', 60))
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            print(f"Timeout on attempt {attempt+1}/{max_retries}")
            time.sleep(2 ** attempt)  # Exponential backoff
            
        except requests.exceptions.ConnectionError as e:
            print(f"Connection error on attempt {attempt+1}/{max_retries}: {e}")
            time.sleep(2 ** attempt)
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                print(f"Authentication failed - check API key")
                return None
            print(f"HTTP error {response.status_code}: {e}")
            time.sleep(2 ** attempt)
    
    print(f"Failed after {max_retries} attempts")
    return None

# Usage:
# data = get_emissions_with_retry("5HOTKEY", 1, "2026-02-01", api_key)
# if data:
#     total_alpha = sum(float(e['emission']) / 1e9 for e in data['data'])
#     print(f"Alpha: {total_alpha} TAO")
```

---

## Store Results in CSV

```python
# Simple CSV storage for daily earnings
import csv
from datetime import datetime

def save_daily_earnings_to_csv(filename, earnings_data):
    """
    earnings_data = {
        "date": "2026-02-01",
        "hotkey": "5HOTKEY",
        "subnets": {1: 0.1234, 3: 0.5678, 18: 0.9012},
        "total": 5.1234
    }
    """
    
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # Write header if file is empty
        if f.tell() == 0:
            writer.writerow(["date", "hotkey", "subnet", "alpha_earned_tao"])
        
        for netuid, alpha in earnings_data["subnets"].items():
            writer.writerow([
                earnings_data["date"],
                earnings_data["hotkey"],
                netuid,
                f"{alpha:.9f}"
            ])

# Usage:
# daily_data = {
#     "date": "2026-02-01",
#     "hotkey": "5HOTKEY",
#     "subnets": {1: 0.1234, 3: 0.5678},
#     "total": 0.1912
# }
# save_daily_earnings_to_csv("daily_alpha_earnings.csv", daily_data)
```

---

## Key Parameters Reference

| Parameter | Format | Example | Notes |
|-----------|--------|---------|-------|
| `hotkey` | SS58 address | `5GKH9FPP...` | Validator hotkey |
| `netuid` | Integer | `1` | Subnet ID |
| `timestamp_start` | Unix seconds | `1706745600` | Use `int(datetime.timestamp())` |
| `timestamp_end` | Unix seconds | `1706832000` | 24 hours later |
| `block_start` | Integer | `5000000` | ~6 blocks/minute |
| `block_end` | Integer | `5100000` | Set range for day |
| `limit` | Integer | `200` | Max per request |
| `page` | Integer | `1` | For pagination |
| `order` | String | `timestamp_asc` | Options: asc/desc variants |

---

## Common Issues & Solutions

| Problem | Solution |
|---------|----------|
| Getting 401 Unauthorized | Check API key format, ensure no extra spaces |
| Rate limited (429) | Implement 12-second delay between requests |
| Empty results | Check date format (YYYY-MM-DD) and timestamp range |
| Multi-validator incomplete | Use RPC as primary source, Taostats as secondary |
| Timestamp parsing errors | Handle both with/without milliseconds in responses |

