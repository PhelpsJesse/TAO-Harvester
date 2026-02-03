"""Direct test of Taostats API without the TaostatsClient wrapper."""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TAOSTATS_API_KEY")
WALLET = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")

print(f"API Key: {API_KEY[:20]}..." if API_KEY else "No API key")
print(f"Wallet: {WALLET}")

# Try the simplest possible request
url = "https://api.taostats.io/api/account/latest/v1"
headers = {"Authorization": API_KEY} if API_KEY else {}
params = {"address": WALLET, "network": "finney", "page": 1, "limit": 10}

print(f"\nRequesting: {url}")
print(f"Params: {params}")
print(f"Headers: {headers}")

try:
    print("\nSending request with 5-second timeout...")
    response = requests.get(url, params=params, headers=headers, timeout=5)
    print(f"Status code: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    print(f"Response body: {response.text[:500]}")
    
    if response.ok:
        data = response.json()
        print(f"\nParsed JSON keys: {list(data.keys())}")
        if "data" in data:
            print(f"Data items: {len(data.get('data', []))}")
            if data["data"]:
                print(f"First item keys: {list(data['data'][0].keys())}")
                print(f"First item: {data['data'][0]}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
        
except requests.Timeout:
    print("Request timed out after 5 seconds")
except requests.ConnectionError as e:
    print(f"Connection error: {e}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
