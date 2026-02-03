#!/usr/bin/env python3
"""
Test script: Kraken API integration

Tests the Kraken API client without requiring real API keys (gracefully degraded).
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import HarvesterConfig
from src.kraken import KrakenClient


def test_kraken_client():
    """Test Kraken client initialization and basic methods."""
    print("\n" + "="*70)
    print("Kraken API Client Test")
    print("="*70 + "\n")

    config = HarvesterConfig.from_env()
    
    # Check if Kraken keys are configured
    has_kraken_keys = bool(config.kraken_api_key and config.kraken_api_secret)
    
    print(f"Kraken API Key: {'✓ Configured' if config.kraken_api_key else '✗ Not configured'}")
    print(f"Kraken API Secret: {'✓ Configured' if config.kraken_api_secret else '✗ Not configured'}")
    print()

    # Initialize client
    kraken = KrakenClient(
        api_key=config.kraken_api_key,
        api_secret=config.kraken_api_secret,
    )

    print("Client Initialization:")
    print(f"  Status: {'✓ Ready' if kraken.is_configured else '✗ Missing credentials'}")
    print(f"  Trade Client: {kraken.trade_client is not None}")
    print(f"  Funding Client: {kraken.funding_client is not None}")
    print(f"  Market Client: {kraken.market_client is not None}")
    print()

    # Test connection (if keys configured)
    if has_kraken_keys:
        print("Testing Connection...")
        is_connected = kraken.check_connection()
        print(f"  Connection: {'✓ Success' if is_connected else '✗ Failed'}")
        print()
    else:
        print("⚠ Skipping connection test (no API keys configured)")
        print()

    # Test getting price (public endpoint, no auth needed)
    print("Testing Public Endpoints:")
    print("  Getting TAOUSD price...")
    price = kraken._get_last_price("TAOUSD")
    if price:
        print(f"    ✓ Last TAOUSD Price: ${price:.2f}")
    else:
        print(f"    ℹ Price unavailable (might not be listed on Kraken yet)")
    print()

    # Test sell order validation (dry-run, no actual order)
    if has_kraken_keys:
        print("Testing Order Validation (Dry-Run):")
        result = kraken.sell_tao_for_usd(
            tao_amount=1.0,
            order_type="market",
            validate=True,  # Validate only, don't submit
        )
        print(f"  Order Validation: {'✓ Success' if result['success'] else '✗ Failed'}")
        print(f"  Reason: {result['reason']}")
        if result['raw_response']:
            print(f"  Order ID (if validated): {result.get('order_id', 'N/A')}")
        print()
    else:
        print("⚠ Skipping order validation (no API keys configured)")
        print()

    # Test account balance (if keys configured)
    if has_kraken_keys:
        print("Testing Account Balance:")
        balance = kraken.get_account_balance()
        if balance:
            print(f"  ✓ Account balances retrieved")
            for asset, amount in list(balance.items())[:5]:  # Show first 5
                print(f"    {asset}: {amount}")
        else:
            print(f"  ℹ No balance data available")
        print()
    else:
        print("⚠ Skipping balance check (no API keys configured)")
        print()

    print("="*70)
    print("Test Complete")
    print("="*70 + "\n")

    if not has_kraken_keys:
        print("Note: To test with real API calls, add your Kraken API credentials to .env:")
        print("  KRAKEN_API_KEY=your_key_here")
        print("  KRAKEN_API_SECRET=your_secret_here")
        print()


if __name__ == "__main__":
    test_kraken_client()
