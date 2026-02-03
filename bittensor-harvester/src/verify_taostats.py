"""Verify balance via Taostats API."""
import os
from src.taostats import TaostatsClient
from src.config import HarvesterConfig

def main():
    cfg = HarvesterConfig.from_env()
    client = TaostatsClient(api_key=cfg.taostats_api_key)
    
    address = cfg.harvester_wallet_address
    print(f"Querying Taostats for wallet: {address}\n")
    
    result = client.get_subnet_balances_with_tao(address)
    
    subnet_alpha = result.get("subnet_alpha", {})
    subnet_tao = result.get("subnet_tao", {})
    
    print("Alpha balances by subnet:")
    for netuid in sorted(subnet_alpha.keys()):
        alpha = subnet_alpha.get(netuid, 0)
        tao = subnet_tao.get(netuid, 0)
        print(f"  Subnet {netuid}: {alpha:.6f} alpha ({tao:.6f} TAO)")

if __name__ == "__main__":
    main()
