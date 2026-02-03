"""
Scan all subnets for alpha balance on a given hotkey.

Run:
  python scan_subnets.py
"""

from src.config import HarvesterConfig
from src.chain import ChainClient

def main():
    config = HarvesterConfig.from_env()
    chain = ChainClient(rpc_url=config.substrate_rpc_url)
    
    hotkey = config.harvester_wallet_address
    print(f"Scanning subnets for hotkey: {hotkey}\n")
    
    found_alpha = []
    
    # Scan subnets 0-127 (typical range)
    for netuid in range(128):
        try:
            alpha = chain.get_alpha_balance(hotkey, netuid)
            if alpha > 0:
                found_alpha.append((netuid, alpha))
                print(f"✓ SN{netuid}: {alpha:.9f} alpha")
            else:
                print(f"  SN{netuid}: 0.0")
        except Exception as e:
            print(f"✗ SN{netuid}: {e}")
    
    print(f"\n=== Summary ===")
    if found_alpha:
        print(f"Found alpha on {len(found_alpha)} subnet(s):")
        for netuid, alpha in found_alpha:
            print(f"  SN{netuid}: {alpha:.9f} alpha")
        total = sum(a for _, a in found_alpha)
        print(f"Total: {total:.9f} alpha")
    else:
        print("No alpha found on any subnet.")

if __name__ == "__main__":
    main()
