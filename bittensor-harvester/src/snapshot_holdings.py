"""Create a holdings snapshot CSV from current Taostats data."""

import os
import csv
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TAOSTATS_API_KEY")
WALLET = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")
SUBNET_LIST = [int(s.strip()) for s in os.getenv("SUBNET_LIST", "1,29,34,44,54,60,64,75,118,120,124").split(",")]

print(f"Fetching current holdings for wallet: {WALLET}")
print(f"Subnets: {SUBNET_LIST}\n")

# Direct API call without the TaostatsClient class to avoid built-in delays
url = "https://api.taostats.io/api/account/latest/v1"
headers = {"Authorization": API_KEY} if API_KEY else {}
params = {"address": WALLET, "network": "finney", "page": 1, "limit": 50}

try:
    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    if "data" not in data or not data["data"]:
        print("No data returned from API")
        exit(1)
    
    account_data = data["data"][0]
    alpha_balances_raw = account_data.get("alpha_balances", [])
    
    print(f"Found {len(alpha_balances_raw)} subnet balances")
    
    # Parse alpha balances
    subnet_alpha = {}
    subnet_tao = {}
    
    for entry in alpha_balances_raw:
        try:
            netuid = int(entry.get("netuid"))
            balance_raw = float(entry.get("balance", 0))
            tao_raw = float(entry.get("balance_as_tao", 0))
            
            # Normalize (divide by 1e9 if very large)
            alpha = balance_raw / 1e9 if balance_raw > 1e6 else balance_raw
            tao = tao_raw / 1e9 if tao_raw > 1e6 else tao_raw
            
            subnet_alpha[netuid] = alpha
            subnet_tao[netuid] = tao
        except Exception as e:
            print(f"Warning: Could not parse entry {entry}: {e}")
            continue
    
except requests.RequestException as e:
    print(f"Error fetching data: {e}")
    exit(1)

print(f"\nFound balances for {len(subnet_alpha)} subnets")

# Create CSV with subnet, alpha, and TAO equivalent
csv_path = "current_holdings.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Subnet", "Alpha Balance", "TAO Equivalent"])
    
    for subnet in sorted(SUBNET_LIST):
        alpha = subnet_alpha.get(subnet, 0.0)
        tao = subnet_tao.get(subnet, 0.0)
        writer.writerow([subnet, f"{alpha:.12f}", f"{tao:.12f}"])
    
    # Also add subnets not in the list but have balances
    other_subnets = set(subnet_alpha.keys()) - set(SUBNET_LIST)
    if other_subnets:
        writer.writerow([])  # Empty row
        writer.writerow(["Other Subnets", "", ""])
        for subnet in sorted(other_subnets):
            alpha = subnet_alpha.get(subnet, 0.0)
            tao = subnet_tao.get(subnet, 0.0)
            writer.writerow([subnet, f"{alpha:.12f}", f"{tao:.12f}"])

print(f"\nExported to {csv_path}")
print(f"\nSummary:")
print(f"  Total alpha across tracked subnets: {sum(subnet_alpha.get(s, 0) for s in SUBNET_LIST):.6f}")
print(f"  Total TAO equivalent: {sum(subnet_tao.get(s, 0) for s in SUBNET_LIST):.6f}")
