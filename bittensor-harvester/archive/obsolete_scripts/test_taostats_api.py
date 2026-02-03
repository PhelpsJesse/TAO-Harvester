#!/usr/bin/env python3
"""
Test script: Load and test Taostats API key.

Usage:
  python test_taostats_api.py --test-connection
  python test_taostats_api.py --get-earnings <address> [--netuid 1]
  python test_taostats_api.py --get-subnet <netuid>
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import HarvesterConfig
from src.taostats import TaostatsClient


def main():
    parser = argparse.ArgumentParser(
        description="Taostats API Testing Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_taostats_api.py --test-connection
  python test_taostats_api.py --get-earnings 5YOUR_ADDRESS --netuid 1
  python test_taostats_api.py --get-subnet 1
  python test_taostats_api.py --get-validator 5YOUR_ADDRESS --netuid 1
        """,
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test API connection and key validity",
    )
    parser.add_argument(
        "--get-earnings",
        metavar="ADDRESS",
        help="Get earnings for a validator address",
    )
    parser.add_argument(
        "--get-validator",
        metavar="ADDRESS",
        help="Get detailed validator information",
    )
    parser.add_argument(
        "--get-subnet",
        metavar="NETUID",
        type=int,
        help="Get subnet emissions data",
    )
    parser.add_argument(
        "--get-delegators",
        metavar="ADDRESS",
        help="Get delegators for a validator",
    )
    parser.add_argument(
        "--netuid",
        type=int,
        default=1,
        help="Subnet ID (default: 1)",
    )

    args = parser.parse_args()

    if not any([
        args.test_connection,
        args.get_earnings,
        args.get_validator,
        args.get_subnet,
        args.get_delegators,
    ]):
        parser.print_help()
        return 0

    # Load config
    config = HarvesterConfig.from_env()

    # Initialize Taostats client
    client = TaostatsClient(api_key=config.taostats_api_key)

    print(f"\n{'='*60}")
    print("Taostats API Testing")
    print(f"{'='*60}\n")

    # Test connection
    if args.test_connection:
        print("Testing API connection...")
        if config.taostats_api_key:
            is_valid = client.check_api_key_valid()
            if is_valid:
                print("✓ API key is valid and authenticated!")
            else:
                print("✗ API key is invalid or connection failed")
                print("  Please check your TAOSTATS_API_KEY in .env")
        else:
            print("⚠ No API key configured (TAOSTATS_API_KEY not set)")
            print("  Some endpoints may have rate limits without authentication")
        return 0

    # Get earnings
    if args.get_earnings:
        print(f"Fetching earnings for {args.get_earnings} (netuid={args.netuid})...")
        result = client.get_validator_earnings(args.get_earnings, args.netuid)
        print_json(result)
        return 0

    # Get validator info
    if args.get_validator:
        print(f"Fetching validator info for {args.get_validator} (netuid={args.netuid})...")
        result = client.get_validator_info(args.get_validator, args.netuid)
        print_json(result)
        return 0

    # Get subnet
    if args.get_subnet:
        print(f"Fetching subnet {args.get_subnet} information...")
        result = client.get_subnet_emissions(args.get_subnet)
        print_json(result)
        return 0

    # Get delegators
    if args.get_delegators:
        print(f"Fetching delegators for {args.get_delegators} (netuid={args.netuid})...")
        delegators = client.get_delegators(args.get_delegators, args.netuid)
        print_json({"delegators": delegators, "count": len(delegators)})
        return 0

    return 0


def print_json(data):
    """Pretty print JSON data."""
    import json
    print(json.dumps(data, indent=2, default=str))
    print()


if __name__ == "__main__":
    sys.exit(main())
