import unittest
from datetime import datetime, timezone, date, timedelta

from v2.tao_harvester.cli import (
    apply_subnet_threshold_fields,
    resolve_run_date,
    summarize_tao_harvest_steps,
    validate_daily_report_date,
)


class TestV2CliRunDate(unittest.TestCase):
    def test_daily_report_defaults_to_yesterday_utc(self):
        now_utc = datetime(2026, 3, 17, 14, 0, 0, tzinfo=timezone.utc)
        run_date = resolve_run_date("daily-report", None, now_utc=now_utc)
        self.assertEqual(run_date.isoformat(), "2026-03-16")

    def test_daily_report_honors_explicit_date(self):
        now_utc = datetime(2026, 3, 17, 14, 0, 0, tzinfo=timezone.utc)
        run_date = resolve_run_date("daily-report", "2026-03-10", now_utc=now_utc)
        self.assertEqual(run_date.isoformat(), "2026-03-10")

    def test_rejects_daily_report_for_old_dates(self):
        now_utc = datetime(2026, 3, 18, 9, 0, 0, tzinfo=timezone.utc)
        old_date = date(2026, 3, 15)  # 3 days old
        with self.assertRaises(ValueError) as ctx:
            validate_daily_report_date(old_date, now_utc=now_utc)
        self.assertIn("can only run for recent dates", str(ctx.exception))
        self.assertIn("3 days old", str(ctx.exception))

    def test_accepts_daily_report_for_yesterday(self):
        now_utc = datetime(2026, 3, 18, 9, 0, 0, tzinfo=timezone.utc)
        yesterday = date(2026, 3, 17)
        validate_daily_report_date(yesterday, now_utc=now_utc)  # Should not raise

    def test_accepts_daily_report_for_today(self):
        now_utc = datetime(2026, 3, 18, 9, 0, 0, tzinfo=timezone.utc)
        today = date(2026, 3, 18)
        validate_daily_report_date(today, now_utc=now_utc)  # Should not raise


class TestHarvestSummary(unittest.TestCase):
    def test_summarize_tao_harvest_steps_separates_total_from_thresholded(self):
        rows = [
            {"netuid": 1, "estimated_earned_alpha": 10.0, "estimated_earned_tao": 0.010},
            {"netuid": 2, "estimated_earned_alpha": 3.0, "estimated_earned_tao": 0.004},
            {"netuid": 3, "estimated_earned_alpha": 7.0, "estimated_earned_tao": 0.006},
        ]

        summary = summarize_tao_harvest_steps(
            earnings_by_subnet=rows,
            subnet_tao_threshold=0.005,
            harvest_fraction=0.5,
        )

        self.assertAlmostEqual(float(summary["estimated_earned_tao_all_subnets"]), 0.020)
        self.assertAlmostEqual(float(summary["harvestable_tao"]), 0.016)
        self.assertEqual(int(summary["eligible_subnet_count"]), 2)
        self.assertAlmostEqual(float(summary["alpha_to_harvest"]), 8.5)

    def test_summarize_tao_harvest_steps_includes_all_when_threshold_zero(self):
        rows = [
            {"netuid": 1, "estimated_earned_alpha": 2.0, "estimated_earned_tao": 0.002},
            {"netuid": 2, "estimated_earned_alpha": 4.0, "estimated_earned_tao": 0.004},
        ]

        summary = summarize_tao_harvest_steps(
            earnings_by_subnet=rows,
            subnet_tao_threshold=0.0,
            harvest_fraction=1.0,
        )

        self.assertAlmostEqual(float(summary["estimated_earned_tao_all_subnets"]), 0.006)
        self.assertAlmostEqual(float(summary["harvestable_tao"]), 0.006)
        self.assertEqual(int(summary["eligible_subnet_count"]), 2)
        self.assertAlmostEqual(float(summary["alpha_to_harvest"]), 6.0)

    def test_apply_subnet_threshold_fields_marks_eligible_rows(self):
        rows = [
            {
                "netuid": 1,
                "estimated_earned_alpha": 8.0,
                "estimated_earned_tao": 0.008,
                "harvestable_tao": 0.004,
            },
            {
                "netuid": 2,
                "estimated_earned_alpha": 2.0,
                "estimated_earned_tao": 0.002,
                "harvestable_tao": 0.001,
            },
        ]

        enriched = apply_subnet_threshold_fields(
            earnings_by_subnet=rows,
            subnet_tao_threshold=0.005,
            harvest_fraction=0.5,
        )

        self.assertEqual(len(enriched), 2)
        self.assertTrue(bool(enriched[0]["meets_threshold"]))
        self.assertAlmostEqual(float(enriched[0]["threshold_harvestable_tao"]), 0.008)
        self.assertAlmostEqual(float(enriched[0]["threshold_alpha_to_harvest"]), 4.0)

        self.assertFalse(bool(enriched[1]["meets_threshold"]))
        self.assertAlmostEqual(float(enriched[1]["threshold_harvestable_tao"]), 0.0)
        self.assertAlmostEqual(float(enriched[1]["threshold_alpha_to_harvest"]), 0.0)


if __name__ == "__main__":
    unittest.main()
