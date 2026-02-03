"""
SQLite database schema and connection management.

Stores:
- Run metadata (block cursors, timestamps)
- Reward ledger (per-subnet accumulated rewards)
- Harvest actions (alpha → TAO conversions)
- Daily caps (enforcement of limits)
- Withdrawal metadata (last USD withdrawal timestamp)
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: str = "data/harvester.db"):
        """Initialize database connection and create schema if needed."""
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Connect to SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def disconnect(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def _init_schema(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        # Runs: track state and block cursors
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                last_block INTEGER,
                last_event_cursor INTEGER,
                status TEXT NOT NULL DEFAULT 'in_progress',
                notes TEXT
            )
        """)

        # Rewards: per-subnet accumulated earnings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                netuid INTEGER NOT NULL,
                block_number INTEGER NOT NULL,
                alpha_amount REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                tx_hash TEXT,
                notes TEXT,
                UNIQUE(netuid, block_number, tx_hash)
            )
        """)

        # Harvests: alpha → TAO conversions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS harvests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                harvest_date TEXT NOT NULL,
                alpha_amount REAL NOT NULL,
                tao_amount REAL NOT NULL,
                conversion_rate REAL,
                destination_address TEXT NOT NULL,
                tx_hash TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                executed_at TEXT,
                notes TEXT
            )
        """)

        # Daily caps: enforce limits
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_caps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                tao_harvested REAL DEFAULT 0.0,
                tao_limit REAL NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)

        # Kraken sales: TAO → USD
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kraken_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TEXT NOT NULL,
                tao_amount REAL NOT NULL,
                usd_amount REAL NOT NULL,
                sale_price REAL,
                kraken_order_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                executed_at TEXT,
                notes TEXT
            )
        """)

        # Withdrawals: USD → checking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                withdrawal_date TEXT NOT NULL,
                usd_amount REAL NOT NULL,
                destination_account TEXT NOT NULL,
                kraken_withdrawal_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                executed_at TEXT,
                notes TEXT
            )
        """)

        # Alpha snapshots: daily balance tracking for delta calculation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alpha_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                block_number INTEGER NOT NULL,
                alpha_balance REAL NOT NULL,
                snapshot_date TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                UNIQUE(address, netuid, snapshot_date)
            )
        """)

        # Subnet snapshots: daily alpha + TAO snapshot data for reporting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subnet_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                alpha_balance REAL NOT NULL,
                tao_balance REAL,
                tao_per_alpha REAL,
                snapshot_date TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                UNIQUE(address, netuid, snapshot_date)
            )
        """)

        # Alpha balance history: complete historical record from Taostats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alpha_balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                block_number INTEGER,
                subnet INTEGER NOT NULL,
                hotkey TEXT NOT NULL,
                alpha_balance REAL NOT NULL,
                tao_equivalent REAL,
                UNIQUE(date, subnet, hotkey)
            )
        """)
        
        # Alpha transactions: buy/sell/swap transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alpha_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                block_number INTEGER,
                subnet INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                alpha_amount REAL NOT NULL,
                tao_amount REAL,
                extrinsic_id TEXT,
                extrinsic_hash TEXT,
                notes TEXT,
                UNIQUE(block_number, subnet, extrinsic_hash)
            )
        """)

        # Transfer history: major alpha transfers for emission calculations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alpha_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                transfer_date TEXT NOT NULL,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                transfer_type TEXT,
                extrinsic_id TEXT,
                recorded_at TEXT NOT NULL,
                UNIQUE(address, extrinsic_id)
            )
        """)

        # Daily emissions: calculated deltas for graphing over time
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_emissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                emission_date TEXT NOT NULL,
                previous_balance REAL NOT NULL,
                current_balance REAL NOT NULL,
                net_transfers REAL NOT NULL DEFAULT 0.0,
                emissions_earned REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                UNIQUE(address, netuid, emission_date)
            )
        """)

        # Config state: last runs, thresholds
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)

        # Chain metadata: track last processed block for incremental queries
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chain_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                notes TEXT
            )
        """)

        # Block-level balances: historical alpha balance at each block for detailed tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS block_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                block_number INTEGER NOT NULL,
                alpha_balance REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                UNIQUE(address, netuid, block_number)
            )
        """)
        
        # Create index for efficient block range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_block_balances_lookup 
            ON block_balances(address, netuid, block_number)
        """)

        self.conn.commit()

    def insert_run(self, notes: str = None) -> int:
        """Create a new run record."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO runs (started_at, status, notes)
            VALUES (?, ?, ?)
            """,
            (now, "in_progress", notes),
        )
        self.conn.commit()
        return cursor.lastrowid

    def finish_run(self, run_id: int, last_block: int, last_event_cursor: int = None):
        """Mark a run as completed."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            UPDATE runs
            SET completed_at = ?, status = ?, last_block = ?, last_event_cursor = ?
            WHERE id = ?
            """,
            (now, "completed", last_block, last_event_cursor, run_id),
        )
        self.conn.commit()

    def insert_reward(
        self,
        netuid: int,
        block_number: int,
        alpha_amount: float,
        tx_hash: str = None,
        notes: str = None,
    ):
        """Record a reward event."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO rewards (netuid, block_number, alpha_amount, recorded_at, tx_hash, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (netuid, block_number, alpha_amount, now, tx_hash, notes),
        )
        self.conn.commit()

    def get_accumulated_rewards(self, netuid: int = None) -> dict:
        """Get total accumulated rewards by netuid."""
        cursor = self.conn.cursor()
        if netuid:
            cursor.execute(
                "SELECT SUM(alpha_amount) as total FROM rewards WHERE netuid = ?",
                (netuid,),
            )
            result = cursor.fetchone()
            return {"netuid": netuid, "total": result[0] or 0.0}
        else:
            cursor.execute(
                "SELECT netuid, SUM(alpha_amount) as total FROM rewards GROUP BY netuid"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}

    def insert_harvest(
        self,
        harvest_date: str,
        alpha_amount: float,
        tao_amount: float,
        destination_address: str,
        conversion_rate: float = None,
        tx_hash: str = None,
        notes: str = None,
    ):
        """Record a harvest (alpha → TAO conversion)."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO harvests
            (harvest_date, alpha_amount, tao_amount, conversion_rate, destination_address, tx_hash, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (harvest_date, alpha_amount, tao_amount, conversion_rate, destination_address, tx_hash, notes),
        )
        self.conn.commit()

    def get_last_run(self) -> dict:
        """Get the last completed run metadata."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, last_block, last_event_cursor, completed_at FROM runs WHERE status = ? ORDER BY completed_at DESC LIMIT 1",
            ("completed",),
        )
        row = cursor.fetchone()
        if row:
            return {
                "id": row[0],
                "last_block": row[1],
                "last_event_cursor": row[2],
                "completed_at": row[3],
            }
        return None

    def set_config_state(self, key: str, value: str):
        """Store/update a configuration state value."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO config_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
            """,
            (key, value, now, value, now),
        )
        self.conn.commit()

    def get_config_state(self, key: str) -> str:
        """Retrieve a configuration state value."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM config_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_daily_total_harvest(self, date: str) -> float:
        """Get total TAO harvested on a specific date."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT tao_harvested FROM daily_caps WHERE date = ?",
            (date,),
        )
        row = cursor.fetchone()
        return row[0] if row else 0.0

    def update_daily_harvest(self, date: str, tao_amount: float, limit: float):
        """Update daily harvest total."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        current = self.get_daily_total_harvest(date)
        new_total = current + tao_amount
        cursor.execute(
            """
            INSERT INTO daily_caps (date, tao_harvested, tao_limit, recorded_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET tao_harvested = ?
            """,
            (date, new_total, limit, now, new_total),
        )
        self.conn.commit()

    def insert_alpha_snapshot(self, address: str, netuid: int, alpha_balance: float, 
                              snapshot_date: str = None, block_number: int = 0):
        """Insert a daily alpha balance snapshot for a specific subnet."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        if snapshot_date is None:
            snapshot_date = datetime.utcnow().date().isoformat()
        
        cursor.execute(
            """
            INSERT INTO alpha_snapshots 
            (address, netuid, block_number, alpha_balance, snapshot_date, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(address, netuid, snapshot_date) 
            DO UPDATE SET alpha_balance = ?, block_number = ?, recorded_at = ?
            """,
            (address, netuid, block_number, alpha_balance, snapshot_date, now,
             alpha_balance, block_number, now),
        )
        self.conn.commit()

    def insert_alpha_snapshots_batch(self, address: str, snapshots: list):
        """Insert multiple alpha snapshots at once.
        
        Args:
            address: Wallet address
            snapshots: List of dicts with keys: netuid, alpha_balance, snapshot_date, block_number
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        for snapshot in snapshots:
            netuid = snapshot['netuid']
            alpha_balance = snapshot['alpha_balance']
            snapshot_date = snapshot.get('snapshot_date', datetime.utcnow().date().isoformat())
            block_number = snapshot.get('block_number', 0)
            
            cursor.execute(
                """
                INSERT INTO alpha_snapshots 
                (address, netuid, block_number, alpha_balance, snapshot_date, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(address, netuid, snapshot_date) 
                DO UPDATE SET alpha_balance = ?, block_number = ?, recorded_at = ?
                """,
                (address, netuid, block_number, alpha_balance, snapshot_date, now,
                 alpha_balance, block_number, now),
            )
        self.conn.commit()

    def insert_subnet_snapshots_batch(self, address: str, snapshots: list):
        """Insert multiple subnet snapshots (alpha + TAO) at once.

        Args:
            address: Wallet address
            snapshots: List of dicts with keys: netuid, alpha_balance, tao_balance,
                tao_per_alpha, snapshot_date
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()

        for snapshot in snapshots:
            netuid = snapshot['netuid']
            alpha_balance = snapshot['alpha_balance']
            tao_balance = snapshot.get('tao_balance')
            tao_per_alpha = snapshot.get('tao_per_alpha')
            snapshot_date = snapshot.get('snapshot_date', datetime.utcnow().date().isoformat())

            cursor.execute(
                """
                INSERT INTO subnet_snapshots
                (address, netuid, alpha_balance, tao_balance, tao_per_alpha, snapshot_date, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address, netuid, snapshot_date)
                DO UPDATE SET alpha_balance = ?, tao_balance = ?, tao_per_alpha = ?, recorded_at = ?
                """,
                (
                    address, netuid, alpha_balance, tao_balance, tao_per_alpha, snapshot_date, now,
                    alpha_balance, tao_balance, tao_per_alpha, now,
                ),
            )
        self.conn.commit()

    def insert_block_balances_batch(self, address: str, block_data: list):
        """Insert multiple block-level balance records at once.
        
        Args:
            address: Wallet address
            block_data: List of dicts with keys: netuid, block_number, alpha_balance
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        for record in block_data:
            netuid = record['netuid']
            block_number = record['block_number']
            alpha_balance = record['alpha_balance']
            
            cursor.execute(
                """
                INSERT INTO block_balances
                (address, netuid, block_number, alpha_balance, recorded_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(address, netuid, block_number)
                DO UPDATE SET alpha_balance = ?, recorded_at = ?
                """,
                (address, netuid, block_number, alpha_balance, now,
                 alpha_balance, now),
            )
        self.conn.commit()
    
    def get_last_block_processed(self, address: str) -> int:
        """Get the most recent block number stored in block_balances table.
        
        Returns:
            Block number, or None if no blocks stored yet
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT MAX(block_number) 
            FROM block_balances 
            WHERE address = ?
            """,
            (address,)
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def get_alpha_snapshot(self, address: str, netuid: int, snapshot_date: str) -> dict:
        """Get a specific alpha snapshot."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT netuid, alpha_balance, block_number, snapshot_date, recorded_at
            FROM alpha_snapshots
            WHERE address = ? AND netuid = ? AND snapshot_date = ?
            """,
            (address, netuid, snapshot_date),
        )
        row = cursor.fetchone()
        if row:
            return {
                "netuid": row[0],
                "alpha_balance": row[1],
                "block_number": row[2],
                "snapshot_date": row[3],
                "recorded_at": row[4],
            }
        return None

    def get_latest_snapshot(self, address: str, netuid: int) -> dict:
        """Get the most recent snapshot for a specific subnet."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT netuid, alpha_balance, block_number, snapshot_date, recorded_at
            FROM alpha_snapshots
            WHERE address = ? AND netuid = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (address, netuid),
        )
        row = cursor.fetchone()
        if row:
            return {
                "netuid": row[0],
                "alpha_balance": row[1],
                "block_number": row[2],
                "snapshot_date": row[3],
                "recorded_at": row[4],
            }
        return None

    def get_all_snapshots_by_date(self, address: str, snapshot_date: str) -> list:
        """Get all subnet snapshots for a specific date."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT netuid, alpha_balance, block_number, snapshot_date, recorded_at
            FROM alpha_snapshots
            WHERE address = ? AND snapshot_date = ?
            ORDER BY netuid
            """,
            (address, snapshot_date),
        )
        return [
            {
                "netuid": row[0],
                "alpha_balance": row[1],
                "block_number": row[2],
                "snapshot_date": row[3],
                "recorded_at": row[4],
            }
            for row in cursor.fetchall()
        ]

    def insert_daily_emission(self, address: str, netuid: int, emission_date: str,
                              previous_balance: float, current_balance: float,
                              net_transfers: float, emissions_earned: float):
        """Insert a daily emission record for graphing over time."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        cursor.execute(
            """
            INSERT INTO daily_emissions 
            (address, netuid, emission_date, previous_balance, current_balance, 
             net_transfers, emissions_earned, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(address, netuid, emission_date) 
            DO UPDATE SET 
                previous_balance = ?,
                current_balance = ?,
                net_transfers = ?,
                emissions_earned = ?,
                recorded_at = ?
            """,
            (address, netuid, emission_date, previous_balance, current_balance,
             net_transfers, emissions_earned, now,
             previous_balance, current_balance, net_transfers, emissions_earned, now),
        )
        self.conn.commit()

    def get_emissions_history(self, address: str, netuid: int = None, 
                              start_date: str = None, end_date: str = None) -> list:
        """Get emissions history for graphing.
        
        Args:
            address: Wallet address
            netuid: Optional subnet filter (None = all subnets)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            
        Returns:
            List of emission records sorted by date
        """
        cursor = self.conn.cursor()
        
        query = """
            SELECT emission_date, netuid, previous_balance, current_balance,
                   net_transfers, emissions_earned
            FROM daily_emissions
            WHERE address = ?
        """
        params = [address]
        
        if netuid is not None:
            query += " AND netuid = ?"
            params.append(netuid)
        
        if start_date:
            query += " AND emission_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND emission_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY emission_date, netuid"
        
        cursor.execute(query, params)
        
        return [
            {
                "emission_date": row[0],
                "netuid": row[1],
                "previous_balance": row[2],
                "current_balance": row[3],
                "net_transfers": row[4],
                "emissions_earned": row[5],
            }
            for row in cursor.fetchall()
        ]

    def insert_alpha_transfer(self, address: str, transfer_date: str, from_address: str,
                             to_address: str, amount: float, transfer_type: str = None,
                             extrinsic_id: str = None):
        """Record an alpha transfer for emission calculations."""
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        try:
            cursor.execute(
                """
                INSERT INTO alpha_transfers 
                (address, transfer_date, from_address, to_address, amount, transfer_type, extrinsic_id, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (address, transfer_date, from_address, to_address, amount, transfer_type, extrinsic_id, now),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Transfer already recorded
            pass

    def insert_alpha_transfers_batch(self, address: str, transfers: list):
        """Insert multiple alpha transfers at once.
        
        Args:
            address: Wallet address
            transfers: List of dicts with keys: transfer_date, from_address, to_address, amount, transfer_type, extrinsic_id
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        
        for transfer in transfers:
            try:
                cursor.execute(
                    """
                    INSERT INTO alpha_transfers 
                    (address, transfer_date, from_address, to_address, amount, transfer_type, extrinsic_id, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (address, transfer['transfer_date'], transfer['from_address'], 
                     transfer['to_address'], transfer['amount'], 
                     transfer.get('transfer_type'), transfer.get('extrinsic_id'), now),
                )
            except sqlite3.IntegrityError:
                # Transfer already recorded, skip
                continue
        self.conn.commit()

    def get_transfers_by_date_range(self, address: str, start_date: str, end_date: str) -> list:
        """Get all transfers within a date range."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT transfer_date, from_address, to_address, amount, transfer_type, extrinsic_id
            FROM alpha_transfers
            WHERE address = ? AND transfer_date >= ? AND transfer_date <= ?
            ORDER BY transfer_date
            """,
            (address, start_date, end_date),
        )
        return [
            {
                "transfer_date": row[0],
                "from_address": row[1],
                "to_address": row[2],
                "amount": row[3],
                "transfer_type": row[4],
                "extrinsic_id": row[5],
            }
            for row in cursor.fetchall()
        ]

    # Chain metadata tracking methods
    
    def get_last_processed_block(self) -> Optional[int]:
        """Get the last block number that was processed for emissions tracking.
        
        Returns:
            Last block number, or None if never run before
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT value FROM chain_metadata WHERE key = 'last_processed_block'
            """
        )
        row = cursor.fetchone()
        if row:
            return int(row[0])
        return None
    
    def set_last_processed_block(self, block_number: int, notes: str = None):
        """Update the last processed block number.
        
        Args:
            block_number: Block number that was just processed
            notes: Optional notes about the processing run
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT OR REPLACE INTO chain_metadata (key, value, updated_at, notes)
            VALUES ('last_processed_block', ?, ?, ?)
            """,
            (str(block_number), now, notes),
        )
        self.conn.commit()
    
    def get_chain_metadata(self, key: str) -> Optional[str]:
        """Get arbitrary chain metadata value.
        
        Args:
            key: Metadata key
            
        Returns:
            Value string, or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT value FROM chain_metadata WHERE key = ?
            """,
            (key,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    
    def set_chain_metadata(self, key: str, value: str, notes: str = None):
        """Set arbitrary chain metadata value.
        
        Args:
            key: Metadata key
            value: Value to store
            notes: Optional notes
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT OR REPLACE INTO chain_metadata (key, value, updated_at, notes)
            VALUES (?, ?, ?, ?)
            """,
            (key, value, now, notes),
        )
        self.conn.commit()

    def insert_many(self, table: str, records: list):
        """Generic bulk insert for any table.
        
        Args:
            table: Table name
            records: List of dicts with column: value pairs
        """
        if not records:
            return
        
        cursor = self.conn.cursor()
        
        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_str = ', '.join(columns)
        
        sql = f"INSERT OR REPLACE INTO {table} ({column_str}) VALUES ({placeholders})"
        
        # Convert records to tuples
        values = [tuple(record[col] for col in columns) for record in records]
        
        cursor.executemany(sql, values)
        self.conn.commit()


    def __enter__(self):
        """Context manager support."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.disconnect()
