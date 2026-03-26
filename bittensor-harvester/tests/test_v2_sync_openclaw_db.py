import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from v2.tao_harvester.modules.sync_openclaw_db import validate_local_db


class TestSyncOpenClawDb(unittest.TestCase):
    def _build_db(self, status: str = "completed", with_negative_anomaly: bool = False) -> str:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        db_path = Path(tmp_dir.name) / "openclaw.db"

        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                workflow_name TEXT NOT NULL,
                tier TEXT NOT NULL,
                dry_run INTEGER NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT
            );
            CREATE TABLE run_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                stage_key TEXT NOT NULL,
                completed_at TEXT NOT NULL
            );
            CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                alpha_balance TEXT NOT NULL,
                tao_per_alpha TEXT,
                source TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE transfer_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                transfer_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                direction TEXT NOT NULL,
                alpha_amount TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE stake_history_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                event_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                action TEXT NOT NULL,
                alpha_amount TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE trade_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                trade_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                direction TEXT NOT NULL,
                alpha_amount TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE reconciliations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reconciliation_date TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                netuid INTEGER NOT NULL,
                previous_alpha TEXT NOT NULL,
                current_alpha TEXT NOT NULL,
                gross_growth_alpha TEXT NOT NULL,
                net_trade_adjustment_alpha TEXT NOT NULL,
                net_transfers_alpha TEXT NOT NULL,
                net_manual_stake_alpha TEXT NOT NULL,
                estimated_staking_earned_alpha TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE harvest_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_date TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                planned_harvest_alpha TEXT NOT NULL,
                estimated_tao_out TEXT NOT NULL,
                harvest_fraction TEXT NOT NULL,
                min_harvest_alpha TEXT NOT NULL,
                state TEXT NOT NULL,
                reason TEXT,
                dry_run INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE transfer_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_date TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                destination_address TEXT NOT NULL,
                tao_amount TEXT NOT NULL,
                state TEXT NOT NULL,
                reason TEXT,
                dry_run INTEGER NOT NULL,
                tx_hash TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time TEXT NOT NULL,
                actor TEXT NOT NULL,
                module TEXT NOT NULL,
                event_type TEXT NOT NULL,
                input_params TEXT NOT NULL,
                result TEXT NOT NULL,
                tx_hash TEXT,
                error_message TEXT,
                integrity_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        recon_date = "2026-03-26"
        conn.execute(
            """
            INSERT INTO runs (run_date, workflow_name, tier, dry_run, status, started_at, completed_at, error_message)
            VALUES (?, 'daily_planner', 'tier1', 1, ?, '2026-03-26T00:00:00', '2026-03-26T00:15:00', '')
            """,
            (recon_date, status),
        )
        conn.execute(
            """
            INSERT INTO snapshots (snapshot_date, wallet_address, netuid, alpha_balance, tao_per_alpha, source, observed_at, created_at)
            VALUES (?, 'wallet', 1, '10.0', '0.01', 'taostats_http', '2026-03-26T00:00:00', '2026-03-26T00:00:00')
            """,
            (recon_date,),
        )

        gross_growth = "1.0"
        net_trade = "0.0"
        net_transfer = "0.0"
        if with_negative_anomaly:
            gross_growth = "0.0"
            net_transfer = "1.0"

        conn.execute(
            """
            INSERT INTO reconciliations (
                reconciliation_date, wallet_address, netuid,
                previous_alpha, current_alpha, gross_growth_alpha,
                net_trade_adjustment_alpha, net_transfers_alpha, net_manual_stake_alpha,
                estimated_staking_earned_alpha, notes, created_at
            )
            VALUES (?, 'wallet', 1, '9.0', '10.0', ?, ?, ?, '0.0', '1.0', '', '2026-03-26T00:00:00')
            """,
            (recon_date, gross_growth, net_trade, net_transfer),
        )

        conn.commit()
        conn.close()
        return str(db_path)

    def test_validate_local_db_success(self):
        db_path = self._build_db(status="completed")
        report = validate_local_db(
            db_path=db_path,
            expected_date=date(2026, 3, 26),
            max_staleness_days=1,
            min_snapshots=1,
            min_reconciliations=1,
        )
        self.assertEqual(report["validation"], "ok")
        self.assertEqual(report["latest_run_status"], "completed")
        self.assertEqual(report["lag_days"], 0)

    def test_validate_local_db_rejects_stale_data(self):
        db_path = self._build_db(status="completed")
        with self.assertRaises(ValueError) as ctx:
            validate_local_db(
                db_path=db_path,
                expected_date=date(2026, 3, 30),
                max_staleness_days=1,
                min_snapshots=1,
                min_reconciliations=1,
            )
        self.assertIn("database is stale", str(ctx.exception))

    def test_validate_local_db_rejects_failed_latest_run(self):
        db_path = self._build_db(status="failed")
        with self.assertRaises(ValueError) as ctx:
            validate_local_db(
                db_path=db_path,
                expected_date=date(2026, 3, 26),
                max_staleness_days=1,
                min_snapshots=1,
                min_reconciliations=1,
            )
        self.assertIn("latest daily_planner run is not healthy", str(ctx.exception))

    def test_validate_local_db_reports_negative_anomaly_count(self):
        db_path = self._build_db(status="completed", with_negative_anomaly=True)
        report = validate_local_db(
            db_path=db_path,
            expected_date=date(2026, 3, 26),
            max_staleness_days=1,
            min_snapshots=1,
            min_reconciliations=1,
        )
        self.assertEqual(report["negative_anomaly_count"], 1)


if __name__ == "__main__":
    unittest.main()
