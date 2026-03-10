from __future__ import annotations

from dataclasses import dataclass

from v2.tao_harvester.config.app_config import HarvestRules


@dataclass(frozen=True)
class TransferBatchDecision:
    create_batch: bool
    tao_amount: float
    reason: str


class TransferBatchService:
    """Policy service for deciding whether transfer batches should be created."""

    def decide(self, expected_harvest_tao: float, rules: HarvestRules) -> TransferBatchDecision:
        if expected_harvest_tao < rules.transfer_batch_threshold_tao:
            return TransferBatchDecision(create_batch=False, tao_amount=0.0, reason="below batch threshold")

        return TransferBatchDecision(
            create_batch=True,
            tao_amount=min(expected_harvest_tao, rules.max_harvest_tao_per_day),
            reason="threshold met",
        )
