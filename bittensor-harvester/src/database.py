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


class Database:
    def __init__(self, db_path: str = "harvester.db"):
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

        # Config state: last runs, thresholds
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
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

    def __enter__(self):
        """Context manager support."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.disconnect()
