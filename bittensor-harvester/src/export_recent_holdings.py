"""Export subnet alpha holdings over the last 100 blocks (recent blocks)."""

import asyncio
import os
import csv
from typing import Dict, List, Tuple
from dotenv import load_dotenv
from src.ws_rpc import WsRpc
from src.substrate_keys import total_hotkey_alpha_key
from src.database import Database

load_dotenv()

ARCHIVE_RPC_URL = os.getenv("ARCHIVE_RPC_URL", "wss://archive.chain.opentensor.ai:443")
WALLET_SS58 = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")
SUBNET_LIST = [int(s.strip()) for s in os.getenv("SUBNET_LIST", "1,29,34,44,54,60,64,75,118,120,124").split(",")]


async def get_recent_block_range(rpc: WsRpc, num_blocks: int = 100) -> Tuple[int, int]:
    """Get the last N blocks from the finalized head."""
    head_hash = await rpc.call_async("chain_getFinalizedHead", [])
    head_header = await rpc.call_async("chain_getHeader", [head_hash])
    end_block = int(head_header["number"], 16)
    start_block = max(1, end_block - num_blocks + 1)
    print(f"Finalized head: block {end_block}")
    print(f"Querying range: {start_block} to {end_block} ({num_blocks} blocks)")
    return start_block, end_block


async def get_alpha_balance(rpc: WsRpc, block_hash: str, wallet_ss58: str, netuid: int) -> float:
    """Query alpha balance for a wallet on a subnet at a specific block."""
    storage_key = total_hotkey_alpha_key(wallet_ss58, netuid)
    result = await rpc.call_async("state_getStorage", [storage_key, block_hash])
    
    if result is None:
        return 0.0
    
    # Remove 0x prefix and decode as u128 (16 bytes = 32 hex chars)
    hex_value = result[2:] if result.startswith("0x") else result
    
    # Try u128 first (32 hex chars)
    if len(hex_value) == 32:
        # Little-endian u128
        int_value = int.from_bytes(bytes.fromhex(hex_value), "little")
    # Try u64 (16 hex chars)
    elif len(hex_value) == 16:
        int_value = int.from_bytes(bytes.fromhex(hex_value), "little")
    else:
        print(f"  Warning: Unexpected hex length {len(hex_value)} for subnet {netuid}")
        return 0.0
    
    # Convert from raw to human-readable (9 decimals)
    return int_value / 1e9


async def export_recent_holdings():
    """Export last 100 blocks of holdings to CSV."""
    rpc = WsRpc(ARCHIVE_RPC_URL)
    
    # Get recent block range (reduced to 10 blocks to avoid rate limiting)
    start_block, end_block = await get_recent_block_range(rpc, 10)
    
    # Collect data: {subnet: {block: alpha}}
    data: Dict[int, Dict[int, float]] = {subnet: {} for subnet in SUBNET_LIST}
    
    print(f"\nQuerying {len(SUBNET_LIST)} subnets across {end_block - start_block + 1} blocks...")
    print("Note: Adding delays to avoid rate limiting...")
    
    for block_num in range(start_block, end_block + 1):
        if (block_num - start_block) % 10 == 0:
            print(f"  Processing block {block_num} ({block_num - start_block + 1}/{end_block - start_block + 1})")
        
        block_hash = await rpc.call_async("chain_getBlockHash", [block_num])
        await asyncio.sleep(0.1)  # Small delay between block hash requests
        
        for subnet in SUBNET_LIST:
            alpha = await get_alpha_balance(rpc, block_hash, WALLET_SS58, subnet)
            data[subnet][block_num] = alpha
            await asyncio.sleep(0.05)  # Small delay between storage queries
    
    await rpc.close()
    
    # Write to CSV (pivot format: subnets as rows, blocks as columns)
    csv_path = "holdings_over_blocks.csv"
    block_range = range(start_block, end_block + 1)
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        
        # Header row
        writer.writerow(["Subnet"] + list(block_range))
        
        # Data rows
        for subnet in sorted(SUBNET_LIST):
            row = [subnet] + [f"{data[subnet].get(b, 0.0):.12f}" for b in block_range]
            writer.writerow(row)
    
    print(f"\nExported to {csv_path}")
    
    # Also save to database
    db = Database()
    rows = []
    for subnet in SUBNET_LIST:
        for block_num in block_range:
            alpha = data[subnet].get(block_num, 0.0)
            if alpha > 0:  # Only store non-zero balances
                rows.append({
                    "block_number": block_num,
                    "subnet": subnet,
                    "wallet": WALLET_SS58,
                    "alpha_balance": alpha
                })
    
    if rows:
        db.insert_many("block_balances", rows)
        print(f"Stored {len(rows)} non-zero balances to database")
    else:
        print("No non-zero balances found to store")


if __name__ == "__main__":
    asyncio.run(export_recent_holdings())
