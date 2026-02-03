"""
Historical wallet balance export using Taostats proven API endpoints.
Based on community scripts from https://github.com/taostat/awesome-taostats-api-examples
"""

import os
import csv
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TAOSTATS_API_KEY")
WALLET = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")

# Date range (last 30 days)
end_date = int(datetime.now().timestamp())
start_date = int((datetime.now() - timedelta(days=30)).timestamp())

print(f"Fetching historical balance data for: {WALLET}")
print(f"Date range: {datetime.fromtimestamp(start_date)} to {datetime.fromtimestamp(end_date)}")

# Use the proven /api/account/history/v1 endpoint from community scripts
total_history = []
count = 200
page = 1

headers = {
    "accept": "application/json",
    "Authorization": API_KEY
}

print("\nFetching daily balance history...")
while count > 0:
    url = f"https://api.taostats.io/api/account/history/v1?address={WALLET}&timestamp_start={start_date}&timestamp_end={end_date}&limit={count}&page={page}&order=timestamp_asc"
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    resJson = response.json()
    
    new_count = resJson['pagination']['total_items']
    total_history += resJson['data']
    
    print(f"  Loaded page {page}, total records: {len(total_history)}")
    
    if new_count < 200 and new_count == count:
        break
    else:
        count = new_count
        page += 1

print(f"\nTotal daily snapshots retrieved: {len(total_history)}")

# Export to CSV
csv_path = "wallet_balance_history.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Date", 
        "Free Balance (TAO)", 
        "Staked Balance (TAO)", 
        "Total Balance (TAO)",
        "Free Change",
        "Staked Change", 
        "Total Change"
    ])
    
    for index, record in enumerate(total_history):
        timestamp = record['timestamp']
        date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        total = float(record['balance_total']) / 1e9
        staked = float(record['balance_staked']) / 1e9
        free = float(record['balance_free']) / 1e9
        
        # Calculate day-over-day changes
        total_change = 0
        staked_change = 0
        free_change = 0
        
        if index > 0:
            prev = total_history[index - 1]
            total_change = total - float(prev['balance_total']) / 1e9
            staked_change = staked - float(prev['balance_staked']) / 1e9
            free_change = free - float(prev['balance_free']) / 1e9
        
        writer.writerow([
            date.strftime("%Y-%m-%d"),
            f"{free:.9f}",
            f"{staked:.9f}",
            f"{total:.9f}",
            f"{free_change:.9f}",
            f"{staked_change:.9f}",
            f"{total_change:.9f}"
        ])

print(f"\n✓ Exported to {csv_path}")
print(f"\nSummary:")
if total_history:
    first = total_history[0]
    last = total_history[-1]
    print(f"  Start date: {first['timestamp'][:10]}")
    print(f"  End date: {last['timestamp'][:10]}")
    print(f"  Starting balance: {float(first['balance_total']) / 1e9:.2f} TAO")
    print(f"  Ending balance: {float(last['balance_total']) / 1e9:.2f} TAO")
    print(f"  Net change: {(float(last['balance_total']) - float(first['balance_total'])) / 1e9:.2f} TAO")
