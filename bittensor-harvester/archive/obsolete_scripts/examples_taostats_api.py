#!/usr/bin/env python3
"""
Example: Using Taostats API in the Harvester

Demonstrates how to integrate Taostats earnings data
into your testing and monitoring workflows.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import HarvesterConfig
from src.taostats import TaostatsClient


def example_basic_usage():
    """Example 1: Basic API key loading and validation."""
    print("\n" + "="*60)
    print("Example 1: Basic API Key Loading")
    print("="*60 + "\n")

    # Load config from environment
    config = HarvesterConfig.from_env()

    if config.taostats_api_key:
        print(f"✓ API Key loaded (length: {len(config.taostats_api_key)} chars)")
    else:
        print("✗ No API key configured")
        print("  Set TAOSTATS_API_KEY environment variable or add to .env")
        return

    # Initialize client
    client = TaostatsClient(api_key=config.taostats_api_key)

    # Validate API key
    if client.check_api_key_valid():
        print("✓ API key is valid and authenticated!")
    else:
        print("⚠ Could not validate API key")
        print("  This might be due to network issues or invalid key")


def example_get_earnings():
    """Example 2: Fetch validator earnings."""
    print("\n" + "="*60)
    print("Example 2: Fetching Validator Earnings")
    print("="*60 + "\n")

    config = HarvesterConfig.from_env()
    client = TaostatsClient(api_key=config.taostats_api_key)

    # Use harvester wallet if configured
    if not config.harvester_wallet_address:
        print("✗ HARVESTER_WALLET_ADDRESS not configured")
        print("  Set it in .env to test earnings fetching")
        return

    print(f"Fetching earnings for: {config.harvester_wallet_address}")
    print(f"Subnet (netuid): {config.netuid}\n")

    earnings = client.get_validator_earnings(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )

    if "error" in earnings:
        print(f"✗ Error: {earnings['error']}")
    else:
        print(f"Address: {earnings.get('address')}")
        print(f"Total Earnings: {earnings.get('total_earnings', 'N/A')}")
        print(f"Daily Earnings: {earnings.get('daily_earnings', 'N/A')}")
        print(f"Hourly Earnings: {earnings.get('hourly_earnings', 'N/A')}")
        if "period" in earnings:
            print(f"\nPeriod Averages:")
            print(f"  24h: {earnings['period'].get('day_24h', 'N/A')}")
            print(f"  7d:  {earnings['period'].get('day_7d', 'N/A')}")
            print(f"  30d: {earnings['period'].get('day_30d', 'N/A')}")
        print(f"\nUpdated: {earnings.get('timestamp')}")


def example_get_validator_info():
    """Example 3: Fetch detailed validator information."""
    print("\n" + "="*60)
    print("Example 3: Fetching Validator Details")
    print("="*60 + "\n")

    config = HarvesterConfig.from_env()
    client = TaostatsClient(api_key=config.taostats_api_key)

    if not config.harvester_wallet_address:
        print("✗ HARVESTER_WALLET_ADDRESS not configured")
        return

    print(f"Fetching validator info for: {config.harvester_wallet_address}\n")

    info = client.get_validator_info(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )

    if "error" in info:
        print(f"✗ Error: {info['error']}")
    else:
        print(f"Address: {info.get('address')}")
        print(f"Stake: {info.get('stake', 'N/A')} TAO")
        print(f"Delegation: {info.get('delegation', 'N/A')} TAO")
        print(f"Trust: {info.get('trust', 'N/A')}")
        print(f"Incentive: {info.get('incentive', 'N/A')}")
        print(f"Dividends: {info.get('dividends', 'N/A')}")
        print(f"Emission: {info.get('emission', 'N/A')}")


def example_get_subnet_emissions():
    """Example 4: Fetch subnet emission data."""
    print("\n" + "="*60)
    print("Example 4: Fetching Subnet Emissions")
    print("="*60 + "\n")

    config = HarvesterConfig.from_env()
    client = TaostatsClient(api_key=config.taostats_api_key)

    print(f"Fetching subnet {config.netuid} information...\n")

    subnet = client.get_subnet_emissions(netuid=config.netuid)

    if "error" in subnet:
        print(f"✗ Error: {subnet['error']}")
    else:
        print(f"Subnet ID: {subnet.get('netuid')}")
        print(f"Total Daily Emissions: {subnet.get('total_daily_emissions', 'N/A')} TAO")
        print(f"Total Validators: {subnet.get('total_validators', 'N/A')}")
        print(f"Avg Earnings/Validator: {subnet.get('average_earnings_per_validator', 'N/A')} TAO")


def example_monitor_earnings():
    """Example 5: Monitoring earnings over time."""
    print("\n" + "="*60)
    print("Example 5: Earnings Monitoring Pattern")
    print("="*60 + "\n")

    config = HarvesterConfig.from_env()
    client = TaostatsClient(api_key=config.taostats_api_key)

    if not config.harvester_wallet_address:
        print("✗ HARVESTER_WALLET_ADDRESS not configured")
        return

    print("This pattern would be used in production to track earnings:")
    print()
    print("""
    # In your main harvest cycle:
    from src.taostats import TaostatsClient
    
    client = TaostatsClient(api_key=config.taostats_api_key)
    
    # Before harvest
    earnings_before = client.get_validator_earnings(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )
    logger.info(f"Earnings before harvest: {earnings_before['total_earnings']}")
    
    # ... run harvest cycle ...
    
    # After harvest
    earnings_after = client.get_validator_earnings(
        address=config.harvester_wallet_address,
        netuid=config.netuid
    )
    delta = earnings_after['total_earnings'] - earnings_before['total_earnings']
    logger.info(f"Earned during cycle: {delta} TAO")
    """)


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Taostats API Integration Examples")
    print("="*60)

    try:
        # Load config once
        config = HarvesterConfig.from_env()

        # Run examples
        example_basic_usage()
        example_get_earnings()
        example_get_validator_info()
        example_get_subnet_emissions()
        example_monitor_earnings()

        print("\n" + "="*60)
        print("Examples completed!")
        print("="*60 + "\n")

        # Instructions
        print("Next steps:")
        print("  1. Ensure TAOSTATS_API_KEY is set in .env")
        print("  2. Run: python examples_taostats_api.py")
        print("  3. Or run the test script: python test_taostats_api.py --test-connection")
        print("  4. Read TAOSTATS_SETUP.md for detailed integration guide")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure to:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your TAOSTATS_API_KEY to .env")
        print("  3. Set HARVESTER_WALLET_ADDRESS in .env")
        print()


if __name__ == "__main__":
    main()
