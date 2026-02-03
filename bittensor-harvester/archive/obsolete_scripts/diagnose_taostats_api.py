#!/usr/bin/env python3
"""
Taostats API Connection Diagnostic

Tests various API endpoints to find working ones and verify key validation.
"""

import requests
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import HarvesterConfig


def test_api_connections():
    """Test various Taostats API endpoints to find working ones."""
    print("\n" + "="*70)
    print("Taostats API Diagnostic")
    print("="*70 + "\n")

    config = HarvesterConfig.from_env()
    api_key = config.taostats_api_key

    if not api_key:
        print("❌ No TAOSTATS_API_KEY found in .env")
        return

    print(f"API Key (first 20 chars): {api_key[:20]}...")
    print(f"Wallet Address: {config.harvester_wallet_address}")
    print(f"Netuid: {config.netuid}\n")

    # Test endpoints
    endpoints = [
        # Base endpoints
        ("Base URL", "https://api.taostats.io"),
        ("API v1", "https://api.taostats.io/api/v1"),
        ("Management API", "https://management-api.taostats.io/api/v1"),
        
        # Specific endpoints we're trying to use
        ("Validators List", f"https://api.taostats.io/api/v1/validators"),
        ("Subnets List", f"https://api.taostats.io/api/v1/subnets"),
        
        # Try with your address
        ("Validator Info", f"https://api.taostats.io/api/v1/validators/{config.harvester_wallet_address}"),
        ("Validator Earnings", f"https://api.taostats.io/api/v1/validators/{config.harvester_wallet_address}/earnings"),
    ]

    # Headers with API key
    headers = {"Authorization": f"Bearer {api_key}"}

    print("Testing endpoints:\n")
    for name, url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            status = response.status_code
            
            # Determine success/failure
            if status == 200:
                symbol = "✅"
            elif status in [400, 404]:
                symbol = "⚠️"
            else:
                symbol = "❌"
            
            print(f"{symbol} [{status}] {name}")
            print(f"   URL: {url}")
            
            # Show response if we got data
            if status == 200 and response.text:
                try:
                    data = response.json()
                    print(f"   Response: {json.dumps(data, indent=6)[:300]}...")
                except:
                    print(f"   Response: {response.text[:200]}")
            elif status != 404:
                # Show error for non-404 responses
                try:
                    error = response.json()
                    print(f"   Error: {error}")
                except:
                    print(f"   Response: {response.text[:200]}")
            
            print()
        except Exception as e:
            print(f"❌ {name}")
            print(f"   URL: {url}")
            print(f"   Error: {type(e).__name__}: {str(e)[:100]}")
            print()

    print("="*70)
    print("Diagnostic complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    test_api_connections()
