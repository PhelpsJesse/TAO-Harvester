#!/usr/bin/env python3
"""
Quick start script: Initialize and run a test cycle.

Usage:
  python quickstart.py --help
  python quickstart.py --test-cycle
  python quickstart.py --run-cycle
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import HarvesterConfig
from src.main import run_harvest_cycle


def main():
    parser = argparse.ArgumentParser(
        description="Bittensor Harvester - Quick Start",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python quickstart.py --test-cycle      # Run with mock data (dry-run)
  python quickstart.py --run-cycle       # Run live (requires .env setup)
  python quickstart.py --check-config    # Validate configuration
        """,
    )

    parser.add_argument(
        "--test-cycle",
        action="store_true",
        help="Run test cycle with mock data (dry-run)",
    )
    parser.add_argument(
        "--run-cycle",
        action="store_true",
        help="Run live harvest cycle (requires .env)",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate configuration",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Don't execute on-chain actions (default: true)",
    )

    args = parser.parse_args()

    if not any([args.test_cycle, args.run_cycle, args.check_config]):
        parser.print_help()
        return 0

    # Load config
    config = HarvesterConfig.from_env()

    # Check config
    if args.check_config:
        print("Checking configuration...")
        try:
            config.validate()
            print("✓ Configuration is valid!")
            return 0
        except ValueError as e:
            print(f"✗ Configuration error:\n{e}")
            return 1

    # Test cycle
    if args.test_cycle:
        print("Running test cycle (dry-run with mock data)...")
        result = run_harvest_cycle(config, dry_run=True)
        return 0 if result["success"] else 1

    # Live cycle
    if args.run_cycle:
        try:
            config.validate()
        except ValueError as e:
            print(f"Configuration invalid:\n{e}")
            print("\nSetup .env file first:")
            print("  cp .env.example .env")
            print("  # Edit .env with your values")
            return 1

        print("Running harvest cycle (live)...")
        result = run_harvest_cycle(config, dry_run=args.dry_run)
        return 0 if result["success"] else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
