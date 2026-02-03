"""
Import daily alpha and TAO-equivalent snapshots from Taostats.

- Fetches per-subnet alpha balances and TAO equivalents for a wallet
- Stores alpha snapshots in `alpha_snapshots`
- Stores combined alpha/TAO and `tao_per_alpha` in `subnet_snapshots`

Usage:
  python -m src.import_snapshot --address <SS58> [--date YYYY-MM-DD]

Reads config from .env if not provided via CLI.
"""

import argparse
from datetime import datetime
from typing import List, Dict

from src.config import HarvesterConfig
from src.database import Database
from src.taostats import TaostatsClient


def import_snapshots(address: str, snapshot_date: str = None, api_key: str = "") -> Dict:
    """Query Taostats and write daily snapshots into the database."""
    db = Database()
    db.connect()
    try:
        client = TaostatsClient(api_key=api_key)
        data = client.get_subnet_balances_with_tao(address)

        subnet_alpha = data.get("subnet_alpha", {}) or {}
        subnet_tao = data.get("subnet_tao", {}) or {}

        if not subnet_alpha and not subnet_tao:
            return {
                "success": False,
                "reason": "No subnet balances returned by Taostats",
                "inserted_alpha": 0,
                "inserted_subnet": 0,
            }

        # Prepare alpha snapshots
        alpha_snapshots: List[Dict] = []
        subnet_snapshots: List[Dict] = []
        for netuid in sorted(set(list(subnet_alpha.keys()) + list(subnet_tao.keys()))):
            alpha_val = float(subnet_alpha.get(netuid, 0.0) or 0.0)
            tao_val = float(subnet_tao.get(netuid, 0.0) or 0.0)
            tao_per_alpha = (tao_val / alpha_val) if alpha_val > 0 else None

            alpha_snapshots.append({
                "netuid": netuid,
                "alpha_balance": alpha_val,
                "snapshot_date": snapshot_date or datetime.utcnow().date().isoformat(),
                "block_number": 0,
            })

            subnet_snapshots.append({
                "netuid": netuid,
                "alpha_balance": alpha_val,
                "tao_balance": tao_val if tao_val > 0 else None,
                "tao_per_alpha": tao_per_alpha,
                "snapshot_date": snapshot_date or datetime.utcnow().date().isoformat(),
            })

        db.insert_alpha_snapshots_batch(address, alpha_snapshots)
        db.insert_subnet_snapshots_batch(address, subnet_snapshots)

        return {
            "success": True,
            "reason": "OK",
            "inserted_alpha": len(alpha_snapshots),
            "inserted_subnet": len(subnet_snapshots),
        }
    finally:
        db.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Import daily Taostats snapshots")
    parser.add_argument("--address", help="Wallet SS58 address", default=None)
    parser.add_argument("--date", help="Snapshot date YYYY-MM-DD", default=None)
    parser.add_argument("--api-key", help="Taostats API key", default=None)
    args = parser.parse_args()

    cfg = HarvesterConfig.from_env()
    address = args.address or cfg.harvester_wallet_address
    if not address:
        raise SystemExit("Missing wallet address. Provide --address or set HARVESTER_WALLET_ADDRESS in .env")

    api_key = args.api_key if args.api_key is not None else cfg.taostats_api_key
    result = import_snapshots(address=address, snapshot_date=args.date, api_key=api_key)
    if not result.get("success"):
        print(f"Snapshot import failed: {result.get('reason')}")
        raise SystemExit(1)

    print(f"Imported snapshots for {address}: alpha={result['inserted_alpha']} subnets={result['inserted_subnet']}")


if __name__ == "__main__":
    main()
