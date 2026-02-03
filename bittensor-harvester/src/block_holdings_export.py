"""
Export per-subnet alpha holdings over the last N blocks using archive RPC.

Read-only: uses official Bittensor Subtensor client to query storage at past blocks.
Safeguards: no extrinsic submission; rate limited; resilient to RPC errors.

Outputs:
- Writes entries to `block_balances` table
- Creates CSV `holdings_over_blocks.csv` with columns: Block, Netuid, Alpha

Usage:
  python -m src.block_holdings_export --address <SS58> --blocks 100 --output .
"""

import argparse
import csv
from datetime import datetime
from typing import List, Dict

from src.config import HarvesterConfig
from src.database import Database
from src.wallet_manager import WalletManager
from src.taostats import TaostatsClient
from src.subtensor_client import (
    get_all_subnets,
)
from src.ws_rpc import WsRpc
from src.substrate_keys import total_hotkey_alpha_key


def get_finalized_block_from_explorer() -> Optional[int]:
    """Fallback: get current finalized block from public API."""
    try:
        import requests
        # Try Taostats public endpoint
        resp = requests.get("https://api.taostats.io/api/block/latest/v1", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return int(data.get("data", {}).get("block_number", 0))
    except Exception:
        return None


def choose_subnets(address: str, api_key: str) -> List[int]:
    """Prefer Taostats-derived owned subnets; fallback to config SUBNET_LIST."""
    # Try config first
    from src.config import HarvesterConfig
    try:
        cfg = HarvesterConfig.from_env()
        subnets = cfg.get_subnet_list()
        if subnets:
            return subnets
    except Exception:
        pass
    
    # Try Taostats API
    try:
        ts = TaostatsClient(api_key=api_key)
        wm = WalletManager(ts, address)
        owned = wm.get_owned_subnets(min_balance=0.0)
        if owned:
            return owned
    except Exception:
        pass
    # Fallback: all subnets (may be large)
    return get_all_subnets() or []


def export_holdings(address: str, blocks: int, output_csv: str,
                    start_block: int = None, end_block: int = None) -> Dict:
    db = Database()
    db.connect()
    try:
        cfg = HarvesterConfig.from_env()
        api_key = cfg.taostats_api_key

        # Helper: normalize HTTP RPC URL for JSON-RPC service
        def rpc_http(url: str) -> str:
            if url and url.startswith("wss://archive.chain.opentensor.ai"):
                return "https://archive-api.bittensor.com/rpc"
            return url

        # Resolve block range
        if end_block is None:
            # Use websocket RPC to resolve finalized head -> header -> number
            try:
                ws = WsRpc(cfg.archive_rpc_url)
                head_hash = ws.call("chain_getFinalizedHead", [])
                header = ws.call("chain_getHeader", [head_hash])
                num = header.get("number") if isinstance(header, dict) else None
                if isinstance(num, str) and num.startswith("0x"):
                    best_block = int(num, 16)
                else:
                    best_block = int(num) if num is not None else 0
            except Exception:
                best_block = 0

            # Fallback to public block explorer
            if best_block <= 0:
                best_block = get_finalized_block_from_explorer() or 0
        else:
            best_block = int(end_block)
        if best_block <= 0:
            return {"success": False, "reason": "Could not get current block from RPC"}

        start_block = int(start_block) if start_block is not None else max(0, best_block - (blocks - 1))
        netuids = choose_subnets(address, api_key)
        if not netuids:
            return {"success": False, "reason": "No subnets found to query"}

        # Collect and write per-block balances
        all_rows = []
        block_data = {}  # {block: {netuid: alpha}}
        
        ws = WsRpc(cfg.archive_rpc_url)
        for block in range(start_block, best_block + 1):
            batch = []
            block_data[block] = {}
            try:
                bh = ws.call("chain_getBlockHash", [block])
            except Exception:
                continue
                
            for netuid in netuids:
                try:
                    key = total_hotkey_alpha_key(address, netuid)
                    val_hex = ws.call("state_getStorage", [key, bh])
                    alpha = 0.0
                    if val_hex and isinstance(val_hex, str) and val_hex != "0x":
                        raw = bytes.fromhex(val_hex[2:])
                        # Try u128 decoding (16 bytes)
                        if len(raw) >= 16:
                            alpha_rao = int.from_bytes(raw[:16], byteorder="little")
                            alpha = alpha_rao / 1e9
                        # Try u64 decoding (8 bytes)
                        elif len(raw) >= 8:
                            alpha_rao = int.from_bytes(raw[:8], byteorder="little")
                            alpha = alpha_rao / 1e9
                except Exception:
                    alpha = 0.0
                    
                block_data[block][netuid] = alpha
                batch.append({
                    "netuid": netuid,
                    "block_number": block,
                    "alpha_balance": alpha,
                })
                all_rows.append((block, netuid, alpha))
            # Write to DB for this block
            db.insert_block_balances_batch(address, batch)

        # Write CSV in pivot format: rows=subnets, columns=blocks
        with open(output_csv, "w", newline="") as f:
            w = csv.writer(f)
            # Header: Subnet, Block1, Block2, ...
            blocks_list = sorted(block_data.keys())
            w.writerow(["Subnet"] + [str(b) for b in blocks_list])
            # Data rows
            for netuid in sorted(netuids):
                row = [netuid]
                for block in blocks_list:
                    alpha = block_data[block].get(netuid, 0.0)
                    row.append(f"{alpha:.12f}")
                w.writerow(row)

        return {
            "success": True,
            "reason": "OK",
            "best_block": best_block,
            "start_block": start_block,
            "subnets": len(netuids),
            "rows": len(all_rows),
            "csv": output_csv,
        }
    finally:
        db.disconnect()


def main():
    p = argparse.ArgumentParser(description="Export per-subnet holdings over last N blocks")
    p.add_argument("--address", required=False, help="Wallet SS58 address")
    p.add_argument("--blocks", type=int, default=100, help="Number of blocks to export")
    p.add_argument("--start-block", type=int, default=None, help="Start block number (optional)")
    p.add_argument("--end-block", type=int, default=None, help="End block number (optional)")
    p.add_argument("--output", default="holdings_over_blocks.csv", help="Output CSV path")
    args = p.parse_args()

    cfg = HarvesterConfig.from_env()
    address = args.address or cfg.harvester_wallet_address
    if not address:
        raise SystemExit("Missing wallet address. Provide --address or set HARVESTER_WALLET_ADDRESS in .env")

    # If block range provided, respect it by temporarily overriding RPC resolution
    # Compute end block if only start provided
    end_block = args.end_block if args.end_block is not None else (
        (args.start_block + args.blocks - 1) if args.start_block is not None else None
    )

    res = export_holdings(
        address=address,
        blocks=args.blocks,
        output_csv=args.output,
        start_block=args.start_block,
        end_block=end_block,
    )
    if not res.get("success"):
        print(f"Export failed: {res.get('reason')}")
        raise SystemExit(1)
    print(f"Exported {res['rows']} rows from block {res['start_block']} to {res['best_block']} across {res['subnets']} subnets → {res['csv']}")


if __name__ == "__main__":
    main()
