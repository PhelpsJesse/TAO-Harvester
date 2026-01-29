"""
Example usage of the harvester.

Demonstrates:
1. Loading configuration
2. Running a harvest cycle
3. Exporting tax data
"""

from src.config import HarvesterConfig
from src.main import run_harvest_cycle


def example_basic_run():
    """Run a basic harvest cycle (dry-run)."""
    print("="*60)
    print("Bittensor TAO Harvester - Example Run")
    print("="*60)
    
    config = HarvesterConfig.from_env()
    print(f"\nConfiguration:")
    print(f"  RPC: {config.substrate_rpc_url}")
    print(f"  NetUID: {config.netuid}")
    print(f"  Harvest fraction: {config.harvest_fraction * 100}%")
    print(f"  Min threshold: {config.min_harvest_threshold_tao} TAO")
    print(f"  Max per run: {config.max_harvest_per_run_tao} TAO")
    print(f"  Max per day: {config.max_harvest_per_day_tao} TAO")
    print(f"  Destination: {config.harvest_destination_address}")
    print()

    # Run cycle (dry-run)
    result = run_harvest_cycle(config, dry_run=True)
    
    print("\nCycle Result:")
    print(f"  Success: {result['success']}")
    print(f"  Run ID: {result['run_id']}")
    print(f"  Rewards earned: {result['rewards_earned']:.12f} alpha")
    print(f"  Harvested alpha: {result['harvested_alpha']:.12f}")
    print(f"  Harvested TAO: {result['harvested_tao']:.12f}")
    print(f"  Errors: {result['errors']}")
    print()

    if not result["success"]:
        print("Cycle failed. Check logs for details.")
        return False

    print("Cycle completed. Check CSVs for tax data.")
    return True


def example_validate_config():
    """Validate configuration before running."""
    print("Validating configuration...")
    config = HarvesterConfig.from_env()
    
    try:
        config.validate()
        print("Configuration valid!")
        return True
    except ValueError as e:
        print(f"Configuration invalid:\n{e}")
        return False


if __name__ == "__main__":
    # Validate first
    if not example_validate_config():
        import sys
        print("\nPlease set up .env file before running.")
        print("Copy .env.example to .env and fill in required values.")
        sys.exit(1)

    # Run example
    example_basic_run()
