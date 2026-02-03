"""Generate holdings CSV from Taostats current snapshot."""
import csv
from src.taostats import TaostatsClient
from src.config import HarvesterConfig

def main():
    cfg = HarvesterConfig.from_env()
    client = TaostatsClient(api_key=cfg.taostats_api_key)
    
    address = cfg.harvester_wallet_address
    print(f"Fetching current holdings from Taostats...")
    
    result = client.get_subnet_balances_with_tao(address)
    subnet_alpha = result.get("subnet_alpha", {})
    
    if not subnet_alpha:
        print("No alpha balances found")
        return
    
    # Write CSV in pivot format: single row with current snapshot
    with open("holdings_current.csv", "w", newline="") as f:
        w = csv.writer(f)
        # Header
        w.writerow(["Subnet", "Alpha (Current)"])
        # Data
        for netuid in sorted(subnet_alpha.keys()):
            alpha = subnet_alpha.get(netuid, 0)
            w.writerow([netuid, f"{alpha:.12f}"])
    
    print(f"✓ Created holdings_current.csv with {len(subnet_alpha)} subnets")
    for netuid in sorted(subnet_alpha.keys()):
        print(f"  Subnet {netuid}: {subnet_alpha[netuid]:.6f} alpha")

if __name__ == "__main__":
    main()
