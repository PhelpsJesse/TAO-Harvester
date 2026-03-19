"""Smoke tests for V2 daily planner workflow."""

import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from v2.tao_harvester.adapters.taostats.mock import MockTaostatsAdapter
from v2.tao_harvester.config.app_config import AppConfig, HarvestRules
from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TradeEventRecord
from v2.tao_harvester.workflows.daily_planner import DailyPlannerWorkflow


class _NegativeAnomalyAdapter(MockTaostatsAdapter):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str):
        return [
            AlphaSnapshot(
                snapshot_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=1,
                alpha_balance=100.0,
                source="mock",
                observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        ]

    def fetch_transfers(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_trade_events(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return [
            TradeEventRecord(
                trade_id="anomaly-buy-1",
                wallet_address=wallet_address,
                netuid=1,
                direction="buy_alpha",
                alpha_amount=250.0,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source="mock",
            )
        ]


class _TradeAdjustedAdapter(MockTaostatsAdapter):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str):
        if snapshot_date == date(2026, 3, 9):
            amount = 100.0
        else:
            amount = 110.0
        return [
            AlphaSnapshot(
                snapshot_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=1,
                alpha_balance=amount,
                source="mock",
                observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        ]

    def fetch_transfers(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_trade_events(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return [
            TradeEventRecord(
                trade_id=f"trade-buy-{snapshot_date.isoformat()}",
                wallet_address=wallet_address,
                netuid=1,
                direction="buy_alpha",
                alpha_amount=10.0,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source="mock",
            )
        ]


class _CapByBalanceAdapter(MockTaostatsAdapter):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str):
        amount = 0.0 if snapshot_date == date(2026, 3, 9) else 20.0
        return [
            AlphaSnapshot(
                snapshot_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=1,
                alpha_balance=amount,
                source="mock",
                observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        ]

    def fetch_transfers(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_trade_events(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        if snapshot_date != date(2026, 3, 10):
            return []
        return [
            TradeEventRecord(
                trade_id="trade-sell-1",
                wallet_address=wallet_address,
                netuid=1,
                direction="sell_alpha",
                alpha_amount=50.0,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source="mock",
            )
        ]


class _TradeAmountFromStakeHistoryAdapter(MockTaostatsAdapter):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str):
        if snapshot_date == date(2026, 3, 9):
            amount = 100.0
        else:
            amount = 120.0
        return [
            AlphaSnapshot(
                snapshot_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=1,
                alpha_balance=amount,
                source="mock",
                observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        ]

    def fetch_transfers(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        if snapshot_date != date(2026, 3, 10):
            return []
        return [
            StakeHistoryRecord(
                event_id="tx-123",
                wallet_address=wallet_address,
                netuid=1,
                action="manual_stake",
                alpha_amount=20.0,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source="mock",
            )
        ]

    def fetch_trade_events(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        if snapshot_date != date(2026, 3, 10):
            return []
        return [
            TradeEventRecord(
                trade_id="tx-123-0",
                wallet_address=wallet_address,
                netuid=1,
                direction="buy_alpha",
                alpha_amount=5.0,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source="mock",
            )
        ]


class _FailingIngestionAdapter(MockTaostatsAdapter):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str):
        return [
            AlphaSnapshot(
                snapshot_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=1,
                alpha_balance=100.0,
                source="mock",
                observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        ]

    def fetch_transfers(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        raise RuntimeError("Taostats transfer fetch failed; upstream data required for reconciliation is unavailable")

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []

    def fetch_trade_events(self, snapshot_date: date, wallet_address: str, window_start=None, window_end=None):
        return []


class TestV2DailyPlannerWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)

        self.repository = SQLiteRepository(self.temp_db)
        schema_path = Path(__file__).resolve().parents[1] / "v2" / "tao_harvester" / "db" / "schema.sql"
        self.repository.init_schema(str(schema_path))

        self.config = AppConfig(
            db_path=self.temp_db,
            taostats_base_url="https://api.taostats.io",
            harvester_address="5TestHarvesterAddress",
            kraken_deposit_whitelist=(),
            rules=HarvestRules(),
            default_dry_run=True,
        )
        self.workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=MockTaostatsAdapter(),
            config=self.config,
        )

    def tearDown(self):
        self.repository.close()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_run_persists_expected_planning_data(self):
        run_date = date(2026, 3, 10)

        result = self.workflow.run(run_date=run_date, dry_run=True)

        self.assertEqual(result.snapshot_count, 6)
        self.assertEqual(result.reconciliation_count, 3)
        self.assertGreater(result.total_estimated_earned_alpha, 0.0)
        self.assertEqual(result.planned_harvest_alpha, 0.0)
        self.assertFalse(result.transfer_batch_created)

        total_from_db = self.repository.sum_estimated_earned_alpha(run_date, self.config.harvester_address)
        self.assertAlmostEqual(total_from_db, result.total_estimated_earned_alpha)

        by_subnet = self.repository.get_daily_earnings_by_subnet(run_date, self.config.harvester_address)
        self.assertEqual(len(by_subnet), 3)
        self.assertEqual(sorted(row["netuid"] for row in by_subnet), [1, 8, 19])
        self.assertAlmostEqual(
            sum(row["estimated_earned_alpha"] for row in by_subnet),
            result.total_estimated_earned_alpha,
        )

    def test_rerun_same_day_is_idempotent(self):
        run_date = date(2026, 3, 10)

        first = self.workflow.run(run_date=run_date, dry_run=True)
        second = self.workflow.run(run_date=run_date, dry_run=True)

        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.reconciliation_count, second.reconciliation_count)
        self.assertAlmostEqual(first.planned_harvest_alpha, second.planned_harvest_alpha)
        self.assertAlmostEqual(first.total_estimated_earned_alpha, second.total_estimated_earned_alpha)

        snapshot_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM snapshots").fetchone()["c"]
        transfer_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM transfer_events").fetchone()["c"]
        stake_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM stake_history_events").fetchone()["c"]
        trade_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM trade_events").fetchone()["c"]
        reconciliation_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM reconciliations").fetchone()["c"]
        harvest_plan_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM harvest_plans").fetchone()["c"]
        stage_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM run_stages").fetchone()["c"]

        self.assertEqual(snapshot_rows, 6)
        self.assertEqual(transfer_rows, 1)
        self.assertEqual(stake_rows, 1)
        self.assertEqual(trade_rows, 0)
        self.assertEqual(reconciliation_rows, 3)
        self.assertEqual(harvest_plan_rows, 1)
        self.assertEqual(stage_rows, 4)

    def test_catchup_run_processes_each_missed_day(self):
        first_date = date(2026, 3, 10)
        catchup_date = date(2026, 3, 13)

        first = self.workflow.run(run_date=first_date, dry_run=True)
        second = self.workflow.run(run_date=catchup_date, dry_run=True)

        self.assertEqual(first.reconciliation_count, 3)
        self.assertEqual(second.reconciliation_count, 9)
        self.assertGreater(second.total_estimated_earned_alpha, first.total_estimated_earned_alpha)

        reconciliation_days = [
            row["d"]
            for row in self.repository.conn.execute(
                """
                SELECT DISTINCT reconciliation_date AS d
                FROM reconciliations
                WHERE wallet_address = ?
                ORDER BY d
                """,
                (self.config.harvester_address,),
            ).fetchall()
        ]
        self.assertEqual(
            reconciliation_days,
            ["2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13"],
        )

    def test_backfill_over_seven_days_requires_manual_reconciliation(self):
        first_date = date(2026, 3, 10)
        too_far_date = date(2026, 3, 20)

        self.workflow.run(run_date=first_date, dry_run=True)

        with self.assertRaises(ValueError) as ctx:
            self.workflow.run(run_date=too_far_date, dry_run=True)
        self.assertIn("manual reconciliation required", str(ctx.exception))
        self.assertIn("automated backfill window exceeded", str(ctx.exception))

    def test_negative_raw_earned_alpha_blocks_harvest_plan(self):
        run_date = date(2026, 3, 10)
        workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=_NegativeAnomalyAdapter(),
            config=self.config,
        )

        result = workflow.run(run_date=run_date, dry_run=True)

        self.assertEqual(result.reconciliation_count, 1)
        self.assertEqual(result.planned_harvest_alpha, 0.0)
        self.assertEqual(result.total_estimated_earned_alpha, 0.0)

        anomaly_count = self.repository.count_negative_raw_earned_anomalies(run_date, self.config.harvester_address)
        self.assertEqual(anomaly_count, 1)

        row = self.repository.conn.execute(
            """
            SELECT state, reason
            FROM harvest_plans
            WHERE plan_date = ? AND wallet_address = ? AND dry_run = 1
            """,
            (run_date.isoformat(), self.config.harvester_address),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["state"], "skipped")
        self.assertIn("anomaly detected", row["reason"])

    def test_trade_adjustment_removes_manual_buy_from_earnings(self):
        run_date = date(2026, 3, 10)
        workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=_TradeAdjustedAdapter(),
            config=self.config,
        )

        result = workflow.run(run_date=run_date, dry_run=True)

        self.assertEqual(result.reconciliation_count, 1)
        self.assertEqual(result.total_estimated_earned_alpha, 0.0)

        row = self.repository.conn.execute(
            """
            SELECT gross_growth_alpha, net_trade_adjustment_alpha, estimated_staking_earned_alpha
            FROM reconciliations
            WHERE reconciliation_date = ? AND wallet_address = ? AND netuid = 1
            """,
            (run_date.isoformat(), self.config.harvester_address),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(float(row["gross_growth_alpha"]), 10.0)
        self.assertAlmostEqual(float(row["net_trade_adjustment_alpha"]), 10.0)
        self.assertAlmostEqual(float(row["estimated_staking_earned_alpha"]), 0.0)

    def test_daily_earnings_rows_include_only_earnings_fields(self):
        run_date = date(2026, 3, 10)
        workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=_NegativeAnomalyAdapter(),
            config=self.config,
        )
        workflow.run(run_date=run_date, dry_run=True)

        rows = self.repository.get_daily_earnings_by_subnet(run_date, self.config.harvester_address)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["netuid"], 1)
        self.assertEqual(set(rows[0].keys()), {"netuid", "estimated_earned_alpha"})
        self.assertAlmostEqual(float(rows[0]["estimated_earned_alpha"]), 0.0)

    def test_estimated_earnings_capped_by_current_balance(self):
        run_date = date(2026, 3, 10)
        workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=_CapByBalanceAdapter(),
            config=self.config,
        )
        workflow.run(run_date=run_date, dry_run=True)

        row = self.repository.conn.execute(
            """
            SELECT current_alpha, gross_growth_alpha, net_trade_adjustment_alpha,
                   estimated_staking_earned_alpha, notes
            FROM reconciliations
            WHERE reconciliation_date = ? AND wallet_address = ? AND netuid = 1
            """,
            (run_date.isoformat(), self.config.harvester_address),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(float(row["current_alpha"]), 20.0)
        self.assertAlmostEqual(float(row["gross_growth_alpha"]), 20.0)
        self.assertAlmostEqual(float(row["net_trade_adjustment_alpha"]), -50.0)
        self.assertAlmostEqual(float(row["estimated_staking_earned_alpha"]), 20.0)
        self.assertIn("capped_by_current_alpha=true", str(row["notes"]))

    def test_trade_adjustment_prefers_stake_history_alpha_amount(self):
        run_date = date(2026, 3, 10)
        workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=_TradeAmountFromStakeHistoryAdapter(),
            config=self.config,
        )
        workflow.run(run_date=run_date, dry_run=True)

        row = self.repository.conn.execute(
            """
            SELECT gross_growth_alpha, net_trade_adjustment_alpha, estimated_staking_earned_alpha
            FROM reconciliations
            WHERE reconciliation_date = ? AND wallet_address = ? AND netuid = 1
            """,
            (run_date.isoformat(), self.config.harvester_address),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(float(row["gross_growth_alpha"]), 20.0)
        self.assertAlmostEqual(float(row["net_trade_adjustment_alpha"]), 20.0)
        self.assertAlmostEqual(float(row["estimated_staking_earned_alpha"]), 0.0)

    def test_ingest_failure_marks_run_failed_and_raises(self):
        run_date = date(2026, 3, 10)
        workflow = DailyPlannerWorkflow(
            repository=self.repository,
            ingestion=_FailingIngestionAdapter(),
            config=self.config,
        )

        with self.assertRaises(RuntimeError) as ctx:
            workflow.run(run_date=run_date, dry_run=True)
        self.assertIn("upstream data required for reconciliation", str(ctx.exception))

        run_row = self.repository.conn.execute(
            """
            SELECT status, error_message
            FROM runs
            WHERE run_date = ? AND workflow_name = ? AND tier = ? AND dry_run = 1
            """,
            (run_date.isoformat(), DailyPlannerWorkflow.WORKFLOW_NAME, DailyPlannerWorkflow.TIER),
        ).fetchone()
        self.assertIsNotNone(run_row)
        self.assertEqual(run_row["status"], "failed")
        self.assertIn("upstream data required for reconciliation", str(run_row["error_message"]))


if __name__ == "__main__":
    unittest.main()
