"""
Test the Taostats accounting endpoint specifically to see if it can provide
daily emissions per subnet.
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from taostats import TaostatsClient
from config import HarvesterConfig

def test_accounting():
    """Test if we can get daily emissions per subnet."""
    cfg = HarvesterConfig()
    client = TaostatsClient(cfg.taostats_api_key)
    
    address = cfg.harvester_wallet_address
    print(f"Testing accounting endpoint for address: {address}")
    print("=" * 80)
    
    # Test a few subnet IDs
    test_subnets = [1, 3, 21, 27]  # Common subnets
    
    for netuid in test_subnets:
        print(f"\nSubnet {netuid}:")
        print("-" * 40)
        
        result = client.get_accounting_by_date(address, netuid)
        
        if 'error' in result:
            print(f"  ❌ Error: {result['error']}")
        else:
            print(f"  ✓ Success!")
            print(f"  Last 24h emission: {result['last_24h_emission']:.6f} TAO")
            
            if result['daily_data']:
                print(f"  Daily data entries: {len(result['daily_data'])}")
                print("\n  Recent emissions:")
                for entry in result['daily_data'][:3]:  # Show first 3 days
                    emission = entry.get('emission', 0) / 1e9  # Convert rao to TAO
                    date = entry.get('date', 'unknown')
                    print(f"    {date}: {emission:.6f} TAO")
            else:
                print("  No daily data returned")

if __name__ == "__main__":
    test_accounting()
