"""
Fetch alpha swap transactions from Taostats API
"""

import os
import requests
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TAOSTATS_API_KEY")
WALLET = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")

headers = {
    "accept": "application/json",
    "Authorization": API_KEY
}

print(f"Fetching alpha transactions for wallet: {WALLET}\n")

# Get transactions from last 30 days
end_date = datetime.now()
start_date = end_date - timedelta(days=30)
start_timestamp = int(start_date.timestamp())
end_timestamp = int(end_date.timestamp())

# Fetch all extrinsics from the wallet
all_extrinsics = []
page = 1
total_pages = 1

print("Fetching all wallet extrinsics...")
while page <= total_pages:
    url = f"https://api.taostats.io/api/extrinsic/v1?signer={WALLET}&timestamp_start={start_timestamp}&timestamp_end={end_timestamp}&limit=200&page={page}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                all_extrinsics.extend(data['data'])
                total_pages = data.get('pagination', {}).get('total_pages', 1)
                print(f"  Page {page}/{total_pages}: {len(data['data'])} extrinsics")
                page += 1
                time.sleep(0.5)  # Rate limiting
            else:
                break
        else:
            print(f"  Warning: API returned {response.status_code}")
            break
    except Exception as e:
        print(f"  Error: {e}")
        break

print(f"\nTotal extrinsics fetched: {len(all_extrinsics)}\n")

# Filter for alpha-related transactions
alpha_transactions = {}

# These are the extrinsic names for alpha swaps
swap_types = [
    "SubtensorModule.swap_alpha_for_tao",
    "SubtensorModule.swap_tao_for_alpha", 
    "Dtao.swap_alpha_for_tao",
    "Dtao.swap_tao_for_alpha"
]

for extrinsic in all_extrinsics:
    full_name = extrinsic.get('full_name', '')
    
    # Check if it's a swap
    if any(swap in full_name for swap in swap_types):
        block_number = extrinsic.get('block_number')
        timestamp = extrinsic.get('timestamp')
        extrinsic_id = extrinsic.get('id')
        
        # Get the events to extract swap details
        event_url = f"https://api.taostats.io/api/event/v1?extrinsic_id={extrinsic_id}"
        try:
            event_response = requests.get(event_url, headers=headers, timeout=10)
            if event_response.status_code == 200:
                event_data = event_response.json()
                events = event_data.get('data', [])
                
                # Parse the swap details from events
                for event in events:
                    if 'Alpha' in event.get('name', '') or 'Swap' in event.get('name', ''):
                        args = event.get('args', {})
                        
                        date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                        netuid = args.get('netuid', args.get('subnet_id'))
                        amount = float(args.get('amount', args.get('alpha_amount', 0))) / 1e9
                        
                        # Determine if buy or sell
                        is_buy = 'tao_for_alpha' in full_name
                        
                        print(f"  {date} Block {block_number}: {'BUY' if is_buy else 'SELL'} {amount:.2f} alpha on SN{netuid}")
                        
                        key = (date, netuid)
                        if key not in alpha_transactions:
                            alpha_transactions[key] = {'buys': 0, 'sells': 0, 'block': block_number}
                        
                        if is_buy:
                            alpha_transactions[key]['buys'] += amount
                        else:
                            alpha_transactions[key]['sells'] += amount
            
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            print(f"  Error fetching events: {e}")
            continue

print(f"\n\nSummary:")
print(f"Total transaction days: {len(alpha_transactions)}")

if alpha_transactions:
    print("\nTransactions by date and subnet:")
    for (date, subnet), tx in sorted(alpha_transactions.items()):
        print(f"  {date} SN{subnet}: Buys={tx['buys']:.2f}, Sells={tx['sells']:.2f}, Block={tx['block']}")
    
    # Save to file for later use
    with open('alpha_transactions.json', 'w') as f:
        # Convert tuple keys to strings for JSON
        json_data = {f"{date}_{subnet}": tx for (date, subnet), tx in alpha_transactions.items()}
        json.dump(json_data, f, indent=2)
    print(f"\n✓ Saved transactions to alpha_transactions.json")
else:
    print("\nNo alpha swap transactions found in the last 30 days.")
    print("This is normal if you haven't manually swapped alpha recently.")
    print("Note: Emissions are NOT swaps - they appear as balance increases without transactions.")
