"""
Debug script to inspect storage key encoding and RPC response.
"""

from src.config import HarvesterConfig
from src.chain import ChainClient
import hashlib
import base58

def main():
    config = HarvesterConfig.from_env()
    chain = ChainClient(rpc_url=config.substrate_rpc_url)
    
    hotkey = config.harvester_wallet_address
    netuid = 1
    
    print(f"Hotkey: {hotkey}")
    print(f"NetUID: {netuid}\n")
    
    # Decode SS58 to account bytes
    try:
        decoded = base58.b58decode(hotkey)
        print(f"Decoded (hex): {decoded.hex()}")
        
        # Extract account ID (skip type byte and checksum)
        if decoded[0] < 64:
            account_id = decoded[1:33]
        else:
            account_id = decoded[2:34]
        
        print(f"Account ID (32 bytes): {account_id.hex()}\n")
        
        # Compute hashes
        pallet_hash = hashlib.blake2b(b"SubtensorModule", digest_size=16).digest()
        storage_hash = hashlib.blake2b(b"TotalHotkeyAlpha", digest_size=16).digest()
        account_hash = hashlib.blake2b(account_id, digest_size=16).digest()
        
        print(f"Pallet hash (Blake2_128): {pallet_hash.hex()}")
        print(f"Storage hash (Blake2_128): {storage_hash.hex()}")
        print(f"Account hash (Blake2_128): {account_hash.hex()}")
        
        # Build storage key
        netuid_bytes = netuid.to_bytes(2, byteorder='little')
        storage_key = f"0x{pallet_hash.hex()}{storage_hash.hex()}{account_hash.hex()}{account_id.hex()}{netuid_bytes.hex()}"
        
        print(f"\nFull storage key ({len(storage_key)//2} bytes):")
        print(f"{storage_key}\n")
        
        # Query RPC directly
        print("Querying RPC...")
        result = chain._rpc_call("state_getStorage", [storage_key])
        
        print(f"RPC Response: {result}")
        print(f"Response type: {type(result)}")
        
        if result:
            print(f"\nParsing response as u128...")
            hex_str = result.lstrip("0x") if isinstance(result, str) else result
            if hex_str:
                alpha_bytes = bytes.fromhex(hex_str)
                print(f"Bytes: {alpha_bytes.hex()}")
                print(f"Length: {len(alpha_bytes)}")
                alpha_value = int.from_bytes(alpha_bytes[:16], byteorder='little')
                print(f"Alpha (raw): {alpha_value}")
                print(f"Alpha (float): {float(alpha_value) / 1e9}")
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
