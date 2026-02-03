"""
CSV export for tax reporting.

Produces:
- rewards.csv: Income events (alpha earned)
- harvest.csv: Dispositions (alpha → TAO conversions)
- sales.csv: TAO → USD sales (taxable events)

Format: timestamp (UTC), asset, quantity, unit_price, total_value, tx_hash, notes
"""

import csv
from datetime import datetime
from pathlib import Path
from src.utils.database import Database


class TaxExporter:
    """Exports ledger data as tax-friendly CSVs."""

    def __init__(self, db: Database, output_dir: str = "."):
        """Initialize exporter."""
        self.db = db
        self.output_dir = Path(output_dir)

    def export_rewards(self, filename: str = "rewards.csv") -> str:
        """
        Export reward ledger as CSV.

        Columns: date, asset, quantity, netuid, tx_hash, notes
        """
        filepath = self.output_dir / filename
        
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT recorded_at, netuid, alpha_amount, tx_hash, notes
            FROM rewards
            ORDER BY recorded_at ASC
            """
        )
        rows = cursor.fetchall()

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Asset", "Quantity", "Subnet ID", "TX Hash", "Notes"])
            for row in rows:
                writer.writerow([
                    row[0],              # recorded_at
                    "ALPHA",             # asset
                    f"{row[2]:.12f}",    # alpha_amount
                    row[1],              # netuid
                    row[3] or "",        # tx_hash
                    row[4] or "",        # notes
                ])

        return str(filepath)

    def export_harvests(self, filename: str = "harvest.csv") -> str:
        """
        Export harvest ledger as CSV.

        Columns: date, from_asset, from_qty, to_asset, to_qty, rate, destination, tx_hash, status
        """
        filepath = self.output_dir / filename
        
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT harvest_date, alpha_amount, tao_amount, conversion_rate, destination_address, tx_hash, status
            FROM harvests
            ORDER BY harvest_date ASC
            """
        )
        rows = cursor.fetchall()

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "From Asset", "From Qty", "To Asset", "To Qty", 
                "Conversion Rate", "Destination", "TX Hash", "Status"
            ])
            for row in rows:
                writer.writerow([
                    row[0],                  # harvest_date
                    "ALPHA",                 # from_asset
                    f"{row[1]:.12f}",        # alpha_amount
                    "TAO",                   # to_asset
                    f"{row[2]:.12f}",        # tao_amount
                    f"{row[3] or 1.0:.6f}",  # conversion_rate
                    row[4],                  # destination_address
                    row[5] or "",            # tx_hash
                    row[6],                  # status
                ])

        return str(filepath)

    def export_sales(self, filename: str = "sales.csv") -> str:
        """
        Export Kraken sales ledger as CSV.

        Columns: date, from_asset, from_qty, to_asset, to_qty, unit_price, order_id, status
        """
        filepath = self.output_dir / filename
        
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT sale_date, tao_amount, usd_amount, sale_price, kraken_order_id, status
            FROM kraken_sales
            ORDER BY sale_date ASC
            """
        )
        rows = cursor.fetchall()

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "From Asset", "From Qty", "To Asset", "To Qty", 
                "Unit Price (USD/TAO)", "Order ID", "Status"
            ])
            for row in rows:
                writer.writerow([
                    row[0],                     # sale_date
                    "TAO",                      # from_asset
                    f"{row[1]:.12f}",           # tao_amount
                    "USD",                      # to_asset
                    f"{row[2]:.2f}",            # usd_amount
                    f"{row[3] or 0:.6f}",       # sale_price
                    row[4] or "",               # kraken_order_id
                    row[5],                     # status
                ])

        return str(filepath)

    def export_withdrawals(self, filename: str = "withdrawals.csv") -> str:
        """
        Export withdrawal ledger as CSV.

        Columns: date, asset, quantity, destination, withdrawal_id, status
        Note: Withdrawals are NOT taxable (money out), but good for tracking.
        """
        filepath = self.output_dir / filename
        
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT withdrawal_date, usd_amount, destination_account, kraken_withdrawal_id, status
            FROM withdrawals
            ORDER BY withdrawal_date ASC
            """
        )
        rows = cursor.fetchall()

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Date", "Asset", "Quantity", "Destination", "Withdrawal ID", "Status"
            ])
            for row in rows:
                writer.writerow([
                    row[0],              # withdrawal_date
                    "USD",               # asset
                    f"{row[1]:.2f}",     # usd_amount
                    row[2],              # destination_account
                    row[3] or "",        # kraken_withdrawal_id
                    row[4],              # status
                ])

        return str(filepath)

    def export_all(self, output_dir: str = ".") -> dict:
        """Export all ledgers."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "rewards": self.export_rewards(),
            "harvests": self.export_harvests(),
            "sales": self.export_sales(),
            "withdrawals": self.export_withdrawals(),
        }
