"""Smoke tests for V2 daily planner workflow."""

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from v2.tao_harvester.adapters.taostats.mock import MockTaostatsAdapter
from v2.tao_harvester.config.app_config import AppConfig, HarvestRules
from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.workflows.daily_planner import DailyPlannerWorkflow


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

        self.assertEqual(result.snapshot_count, 3)
        self.assertEqual(result.reconciliation_count, 3)
        self.assertGreater(result.total_estimated_earned_alpha, 0.0)
        self.assertGreater(result.planned_harvest_alpha, 0.0)
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
        reconciliation_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM reconciliations").fetchone()["c"]
        harvest_plan_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM harvest_plans").fetchone()["c"]
        stage_rows = self.repository.conn.execute("SELECT COUNT(*) AS c FROM run_stages").fetchone()["c"]

        self.assertEqual(snapshot_rows, 3)
        self.assertEqual(transfer_rows, 1)
        self.assertEqual(stake_rows, 1)
        self.assertEqual(reconciliation_rows, 3)
        self.assertEqual(harvest_plan_rows, 1)
        self.assertEqual(stage_rows, 4)


if __name__ == "__main__":
    unittest.main()
