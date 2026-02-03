"""
Export historical alpha balance per subnet per day.
This is the core data needed for emissions calculations.
"""

import os
import sys
import csv
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.database import Database

load_dotenv()

API_KEY = os.getenv("TAOSTATS_API_KEY")
WALLET = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")

headers = {
    "accept": "application/json",
    "Authorization": API_KEY
}

# Date range for last 30 days
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
start_timestamp = int(start_date.timestamp())
end_timestamp = int(end_date.timestamp())

print(f"Building historical alpha balance database for: {WALLET}")
print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} (30 days)\n")

# Wait a moment if rate limited from previous run
print("Waiting 15 seconds to avoid rate limits...")
time.sleep(15)

# Step 1: Get all subnets where wallet has alpha
print("Step 1: Finding all subnets with alpha balances...")
url = f"https://api.taostats.io/api/dtao/stake_balance/latest/v1?coldkey={WALLET}&limit=200"
response = requests.get(url, headers=headers, timeout=10)
response.raise_for_status()
data = response.json()

subnets = data['data']
print(f"Found {len(subnets)} subnets with alpha balances\n")

# Rate limiting: wait after the initial API call before starting subnet requests
print("Waiting 15 seconds before fetching subnet histories...")
time.sleep(15)

# Step 2: For each subnet, get historical balance data
all_history = []
db = Database()

for idx, subnet_data in enumerate(subnets):
    # Rate limiting: wait 15 seconds before each request (except the first)
    if idx > 0:
        print(f"  Waiting 15 seconds before next subnet...")
        time.sleep(15)
    
    netuid = subnet_data['netuid']
    hotkey = subnet_data['hotkey']['ss58']
    current_balance = float(subnet_data['balance']) / 1e9
    
    print(f"Subnet {netuid} (hotkey {hotkey[:10]}...)")
    print(f"  Current balance: {current_balance:.6f} alpha")
    
    # Get historical data for this subnet
    page = 1
    total_pages = 1
    subnet_history = []
    
    while page <= total_pages:
        history_url = f"https://api.taostats.io/api/dtao/stake_balance/history/v1?hotkey={hotkey}&coldkey={WALLET}&netuid={netuid}&timestamp_start={start_timestamp}&timestamp_end={end_timestamp}&limit=200&page={page}"
        hist_response = requests.get(history_url, headers=headers, timeout=10)
        hist_response.raise_for_status()
        hist_data = hist_response.json()
        
        subnet_history.extend(hist_data['data'])
        total_pages = hist_data['pagination']['total_pages']
        page += 1
        
        # Rate limiting: 5 requests/minute = 12 seconds minimum
        # Using 15 seconds to be safe
        if page <= total_pages:
            print(f"    Waiting 15 seconds for rate limiting...")
            time.sleep(15)
    
    print(f"  Retrieved {len(subnet_history)} historical records")
    
    # Process and store
    for record in subnet_history:
        timestamp = record['timestamp']
        date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        block = record.get('block_number', 0)
        
        # Alpha balance
        balance = float(record.get('balance', 0)) / 1e9
        
        # TAO equivalent
        balance_as_tao = float(record.get('balance_as_tao', 0)) / 1e9
        
        all_history.append({
            'date': date.strftime('%Y-%m-%d'),
            'timestamp': timestamp,
            'block_number': block,
            'subnet': netuid,
            'hotkey': hotkey,
            'alpha_balance': balance,
            'tao_equivalent': balance_as_tao
        })
    
    print()

# Step 3: Get alpha swap transactions
print("="*60)
print("Step 3: Fetching alpha swap transactions...")
print("="*60)

all_transactions = []
page = 1
max_pages = 50  # Limit to avoid excessive API calls

while page <= max_pages:
    tx_url = f"https://api.taostats.io/api/extrinsic/v1?signer={WALLET}&timestamp_start={start_timestamp}&timestamp_end={end_timestamp}&limit=200&page={page}"
    
    try:
        tx_response = requests.get(tx_url, headers=headers, timeout=10)
        if tx_response.status_code == 200:
            tx_data = tx_response.json()
            
            # Handle both dict and list responses
            if isinstance(tx_data, list):
                extrinsics = tx_data
            elif isinstance(tx_data, dict):
                extrinsics = tx_data.get('data', [])
            else:
                extrinsics = []
            
            if not extrinsics:
                break
            
            # Filter for swap/dtao transactions
            for ex in extrinsics:
                full_name = ex.get('full_name', '')
                if any(keyword in full_name.lower() for keyword in ['swap', 'dtao']):
                    extrinsic_id = ex.get('id')
                    block_number = ex.get('block_number')
                    timestamp = ex.get('timestamp')
                    extrinsic_hash = ex.get('hash', '')
                    
                    # Get event details
                    time.sleep(15)  # Rate limiting - 15 seconds between requests
                    event_url = f"https://api.taostats.io/api/event/v1?extrinsic_id={extrinsic_id}"
                    event_response = requests.get(event_url, headers=headers, timeout=10)
                    
                    if event_response.status_code == 200:
                        event_data = event_response.json()
                        
                        # Handle both list and dict responses
                        if isinstance(event_data, list):
                            events = event_data
                        elif isinstance(event_data, dict):
                            events = event_data.get('data', [])
                        else:
                            events = []
                        
                        for event in events:
                            if not isinstance(event, dict):
                                continue
                                
                            event_name = event.get('name', '')
                            args = event.get('args', {})
                            
                            # Ensure args is a dict
                            if not isinstance(args, dict):
                                continue
                            
                            # Look for swap/alpha events
                            if any(keyword in event_name for keyword in ['Swap', 'Alpha']):
                                date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                                netuid = args.get('netuid', args.get('subnet_id'))
                                alpha_amount = float(args.get('alpha_amount', args.get('amount', 0))) / 1e9
                                tao_amount = float(args.get('tao_amount', 0)) / 1e9
                                
                                # Determine transaction type
                                is_sell = 'alpha_for_tao' in full_name.lower()
                                tx_type = 'sell' if is_sell else 'buy'
                                
                                if netuid and alpha_amount > 0:
                                    all_transactions.append({
                                        'date': date.strftime('%Y-%m-%d'),
                                        'timestamp': timestamp,
                                        'block_number': block_number,
                                        'subnet': netuid,
                                        'transaction_type': tx_type,
                                        'alpha_amount': alpha_amount,
                                        'tao_amount': tao_amount,
                                        'extrinsic_id': extrinsic_id,
                                        'extrinsic_hash': extrinsic_hash,
                                        'notes': f"{full_name} - {event_name}"
                                    })
                                    
                                    print(f"  {date.strftime('%Y-%m-%d')} SN{netuid}: {tx_type.upper()} {alpha_amount:.2f} alpha")
            
            # Check pagination
            if isinstance(tx_data, dict):
                total_pages = tx_data.get('pagination', {}).get('total_pages', 1)
            else:
                total_pages = 1
            
            if page >= total_pages or page >= max_pages:
                break
            
            print(f"  Waiting 15 seconds before next page...")
            page += 1
            time.sleep(15)  # Rate limiting between pages
        else:
            print(f"  API returned {tx_response.status_code}, stopping transaction fetch")
            break
    except Exception as e:
        print(f"  Error fetching transactions: {e}")
        break

print(f"\nFound {len(all_transactions)} swap transactions\n")

# Step 4: Export to CSV
csv_path = "alpha_balance_history.csv"
print(f"Exporting {len(all_history)} records to {csv_path}...")

with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'date', 'timestamp', 'block_number', 'subnet', 'hotkey', 
        'alpha_balance', 'tao_equivalent'
    ])
    writer.writeheader()
    writer.writerows(all_history)

print(f"✓ Exported to {csv_path}\n")

# Step 4: Export to CSV
csv_path = "alpha_balance_history.csv"
print(f"Exporting {len(all_history)} balance records to {csv_path}...")

with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'date', 'timestamp', 'block_number', 'subnet', 'hotkey', 
        'alpha_balance', 'tao_equivalent'
    ])
    writer.writeheader()
    writer.writerows(all_history)

print(f"✓ Exported to {csv_path}\n")

# Export transactions to CSV
if all_transactions:
    tx_csv_path = "alpha_transactions.csv"
    print(f"Exporting {len(all_transactions)} transaction records to {tx_csv_path}...")
    
    with open(tx_csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'date', 'timestamp', 'block_number', 'subnet', 'transaction_type',
            'alpha_amount', 'tao_amount', 'extrinsic_id', 'extrinsic_hash', 'notes'
        ])
        writer.writeheader()
        writer.writerows(all_transactions)
    
    print(f"✓ Exported to {tx_csv_path}\n")

# Step 5: Store in database
print("Storing in database...")
db = Database()
db.connect()  # Connect to database

if all_history:
    db.insert_many("alpha_balance_history", all_history)
    print(f"✓ Stored {len(all_history)} balance records to database")

if all_transactions:
    db.insert_many("alpha_transactions", all_transactions)
    print(f"✓ Stored {len(all_transactions)} transaction records to database")

db.disconnect()
print("\n✅ Complete!")

print()

# Step 6: Summary
print("="*60)
print("SUMMARY")
print("="*60)
dates = sorted(set(r['date'] for r in all_history))
if dates:
    print(f"Date range: {dates[0]} to {dates[-1]} ({len(dates)} days)")
    print(f"Subnets tracked: {len(subnets)}")
    print(f"Total records: {len(all_history)}")
    
    # Show per-subnet totals
    print(f"\nCurrent alpha per subnet:")
    for subnet_data in sorted(subnets, key=lambda x: x['netuid']):
        netuid = subnet_data['netuid']
        balance = float(subnet_data['balance']) / 1e9
        tao_equiv = float(subnet_data['balance_as_tao']) / 1e9
        print(f"  Subnet {netuid:3d}: {balance:12.6f} alpha ({tao_equiv:8.6f} TAO)")
    
    total_alpha = sum(float(s['balance']) / 1e9 for s in subnets)
    total_tao = sum(float(s['balance_as_tao']) / 1e9 for s in subnets)
    print(f"\n  Total:        {total_alpha:12.6f} alpha ({total_tao:8.6f} TAO)")
else:
    print("No historical data found")
