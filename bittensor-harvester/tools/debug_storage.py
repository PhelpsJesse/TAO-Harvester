"""Debug storage key construction and RPC query."""
import os
from src.ws_rpc import WsRpc
from src.substrate_keys import total_hotkey_alpha_key, ss58_to_account_bytes
from src.config import HarvesterConfig

def main():
    cfg = HarvesterConfig.from_env()
    address = cfg.harvester_wallet_address
    
    print(f"Wallet: {address}")
    print(f"Account bytes: {ss58_to_account_bytes(address).hex()}")
    
    # Test with subnet 29 at block 4500000
    netuid = 29
    block = 4500000
    
    key = total_hotkey_alpha_key(address, netuid)
    print(f"\nStorage key for subnet {netuid}: {key}")
    
    ws = WsRpc(cfg.archive_rpc_url)
    try:
        bh = ws.call("chain_getBlockHash", [block])
        print(f"Block hash for {block}: {bh}")
        
        val_hex = ws.call("state_getStorage", [key, bh])
        print(f"Storage value: {val_hex}")
        
        if val_hex and val_hex != "0x":
            raw = bytes.fromhex(val_hex[2:])
            print(f"Raw bytes ({len(raw)}): {raw.hex()}")
            if len(raw) >= 16:
                alpha_rao = int.from_bytes(raw[:16], byteorder="little")
                print(f"Alpha (u128): {alpha_rao / 1e9}")
            elif len(raw) >= 8:
                alpha_rao = int.from_bytes(raw[:8], byteorder="little")
                print(f"Alpha (u64): {alpha_rao / 1e9}")
        else:
            print("No value at this key")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
