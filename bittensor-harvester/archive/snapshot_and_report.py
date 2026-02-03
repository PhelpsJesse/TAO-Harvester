"""
Snapshot alpha balances for configured validators/subnets and produce CSV report.

Produces CSV with columns:
date,address,netuid,previous_balance,current_balance,delta_alpha,harvestable_alpha,previous_block,current_block

Run:
  python snapshot_and_report.py

Output:
  reports/alpha_report_<YYYYMMDD>.csv
"""

import os
import csv
from datetime import date
from src.config import HarvesterConfig
from src.database import Database
from src.chain import ChainClient
from src.taostats import TaostatsClient


def main():
    config = HarvesterConfig.from_env()

    db = Database(config.db_path)
    db.connect()

    chain = ChainClient(rpc_url=config.substrate_rpc_url, db=db)

    validators = config.get_validator_list()
    if not validators:
        print("No validators configured. Set VALIDATOR_HOTKEYS or HARVESTER_WALLET_ADDRESS in .env")
        return

    subnets = config.get_subnet_list()

    today = date.today().isoformat()
    out_dir = os.path.join(os.getcwd(), "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"alpha_report_{today}.csv")

    headers = [
        "date",
        "address",
        "netuid",
        "previous_balance",
        "current_balance",
        "delta_alpha",
        "harvestable_alpha",
        "previous_block",
        "current_block",
    ]

    rows = []
    # Prepare Taostats fallback client (if API key provided)
    taostats = TaostatsClient(api_key=os.getenv("TAOSTATS_API_KEY", ""))

    for addr in validators:
        for netuid in subnets:
            try:
                try:
                    # Primary: Take snapshot via RPC (stores in DB)
                    snapshot = chain.get_alpha_balance_snapshot(addr, netuid)
                    # Compute daily delta (uses DB to find yesterday)
                    delta, meta = chain.get_daily_alpha_delta(addr, netuid)
                    previous_balance = meta.get("previous_balance", 0)
                    current_balance = meta.get("current_balance", snapshot.get("alpha_balance", 0))
                    previous_block = meta.get("previous_block", "")
                    current_block = meta.get("current_block", snapshot.get("block", ""))
                except Exception as rpc_err:
                    # Fallback to Taostats if RPC fails
                    print(f"RPC failed for {addr} SN{netuid}: {rpc_err} — falling back to Taostats")
                    taodata = taostats.get_account_balance(addr)
                    current_balance = taodata.get("current_balance", 0.0)
                    # Try to find yesterday's balance in returned history
                    history = taodata.get("balance_history", [])
                    previous_balance = 0.0
                    if len(history) > 1:
                        # assume first is latest, second is previous
                        prev = history[1]
                        previous_balance = prev.get("balance", 0) / 1e9 if prev.get("balance") else 0
                    delta = max(0, current_balance - previous_balance)
                    previous_block = ""
                    current_block = ""

                harvestable = delta * config.harvest_fraction

                row = {
                    "date": today,
                    "address": addr,
                    "netuid": netuid,
                    "previous_balance": previous_balance,
                    "current_balance": current_balance,
                    "delta_alpha": delta,
                    "harvestable_alpha": harvestable,
                    "previous_block": previous_block,
                    "current_block": current_block,
                }
                rows.append(row)
                print(f"OK: {addr} SN{netuid} delta={delta} harvestable={harvestable}")
            except Exception as e:
                print(f"Error processing {addr} SN{netuid}: {e}")

    # Write CSV
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Report written: {out_path}")
    db.disconnect()


if __name__ == "__main__":
    main()
