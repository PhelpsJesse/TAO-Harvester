import unittest
from datetime import date
from typing import cast

from v2.tao_harvester.modules.calculate_harvest import (
    HarvestCalculationSummary,
    build_execution_handoff_subnets,
    build_handoff_payload,
    summarize_harvest,
)


class TestCalculateHarvestModule(unittest.TestCase):
    def test_summarize_harvest_applies_threshold_only_to_harvestable(self):
        rows = [
            {"netuid": 1, "estimated_earned_alpha": 10.0, "estimated_earned_tao": 0.010, "tao_per_alpha": 0.001},
            {"netuid": 2, "estimated_earned_alpha": 3.0, "estimated_earned_tao": 0.004, "tao_per_alpha": 0.001333},
            {"netuid": 3, "estimated_earned_alpha": 7.0, "estimated_earned_tao": 0.006, "tao_per_alpha": 0.000857},
        ]

        summary = summarize_harvest(rows, subnet_tao_threshold=0.005, harvest_fraction=0.5)

        self.assertAlmostEqual(summary.estimated_earned_tao_all_subnets, 0.020)
        self.assertAlmostEqual(summary.harvestable_tao, 0.016)
        self.assertAlmostEqual(summary.alpha_to_harvest, 8.5)
        self.assertEqual(summary.eligible_subnet_count, 2)

    def test_build_execution_handoff_subnets_filters_and_sorts(self):
        rows = [
            {"netuid": 1, "estimated_earned_alpha": 10.0, "estimated_earned_tao": 0.010, "tao_per_alpha": 0.001},
            {"netuid": 2, "estimated_earned_alpha": 3.0, "estimated_earned_tao": 0.004, "tao_per_alpha": 0.001333},
            {"netuid": 3, "estimated_earned_alpha": 7.0, "estimated_earned_tao": 0.006, "tao_per_alpha": 0.000857},
        ]

        handoff = build_execution_handoff_subnets(rows, subnet_tao_threshold=0.005, harvest_fraction=0.5)

        self.assertEqual([row["netuid"] for row in handoff], [1, 3])
        self.assertAlmostEqual(float(handoff[0]["alpha_to_harvest"]), 5.0)
        self.assertAlmostEqual(float(handoff[1]["alpha_to_harvest"]), 3.5)

    def test_build_handoff_payload_contains_expected_contract(self):
        summary = HarvestCalculationSummary(
            threshold_tao=0.005,
            eligible_subnet_count=2,
            estimated_earned_tao_all_subnets=0.02,
            harvestable_tao=0.016,
            alpha_to_harvest=8.5,
        )
        payload = build_handoff_payload(
            run_date=date(2026, 3, 19),
            wallet_address="5Wallet",
            dry_run=True,
            run_id=42,
            snapshot_count=125,
            reconciliation_count=125,
            estimated_earned_alpha=21.0,
            summary=summary,
            execution_subnets=[
                {"netuid": 1, "alpha_to_harvest": 5.0, "estimated_tao_out": 0.01, "tao_per_alpha": 0.002}
            ],
        )
        execution_handoff = cast(dict[str, object], payload["execution_handoff"])
        totals = cast(dict[str, object], payload["totals"])

        self.assertEqual(payload["module"], "calculate_harvest")
        self.assertEqual(execution_handoff["target"], "opentensor_swap_alpha_to_tao")
        self.assertEqual(execution_handoff["status"], "intent_only")
        self.assertEqual(len(cast(list[object], execution_handoff["subnets"])), 1)
        self.assertAlmostEqual(float(cast(float, totals["harvestable_tao_threshold_applied"])), 0.016)


if __name__ == "__main__":
    unittest.main()
