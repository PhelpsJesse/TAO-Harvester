from __future__ import annotations

from dataclasses import dataclass

from v2.tao_harvester.config.app_config import HarvestRules


@dataclass(frozen=True)
class HarvestPolicyDecision:
    can_harvest: bool
    planned_harvest_alpha: float
    reason: str


class HarvestPolicyService:
    """Pure policy decisions for harvest planning (no side effects)."""

    def decide(self, estimated_earned_alpha: float, rules: HarvestRules) -> HarvestPolicyDecision:
        planned = estimated_earned_alpha * rules.harvest_fraction
        if planned < rules.min_harvest_alpha:
            return HarvestPolicyDecision(
                can_harvest=False,
                planned_harvest_alpha=0.0,
                reason=(
                    f"below threshold: planned_alpha={planned:.6f} "
                    f"< min={rules.min_harvest_alpha:.6f}"
                ),
            )
        return HarvestPolicyDecision(can_harvest=True, planned_harvest_alpha=planned, reason="ok")
