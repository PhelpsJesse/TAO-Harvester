"""
Accounting & delta computation.

Tracks earned alpha rewards using state-based deltas.
Applies harvest policy to determine harvestable amount.

Logic:
1. Snapshot alpha balance at start of day / last run.
2. Snapshot alpha balance at end of day / this run.
3. Delta = current - last = earned rewards.
4. Accumulate in database.
5. Apply 50% harvest fraction to determine harvestable amount.
"""

from datetime import datetime
from typing import Dict, Tuple
from src.database import Database
from src.chain import ChainClient


class Accounting:
    """Accounting system for reward tracking and delta computation."""

    def __init__(self, db: Database, chain: ChainClient):
        """Initialize accounting."""
        self.db = db
        self.chain = chain

    def compute_daily_delta(
        self, address: str, netuid: int, prev_balance: float = None
    ) -> Tuple[float, float]:
        """
        Compute daily reward delta using state snapshots.

        Args:
            address: SS58 address
            netuid: Subnet ID
            prev_balance: Previous balance (if None, query from DB)

        Returns:
            (current_balance, earned_alpha)
        """
        current_balance = self.chain.get_alpha_balance(address, netuid)

        if prev_balance is None:
            # TODO: Load from DB if we have a previous snapshot
            prev_balance = 0.0  # First run or no prior data

        earned = max(0, current_balance - prev_balance)
        return current_balance, earned

    def record_rewards(
        self, address: str, netuid: int, earned_alpha: float, block_number: int, tx_hash: str = None
    ):
        """Record earned rewards in ledger."""
        self.db.insert_reward(
            netuid=netuid,
            block_number=block_number,
            alpha_amount=earned_alpha,
            tx_hash=tx_hash,
            notes=f"Earned by {address[:6]}... on netuid {netuid}",
        )

    def get_harvestable_amount(
        self, netuid: int = None, harvest_fraction: float = 0.5
    ) -> Dict[str, float]:
        """
        Calculate harvestable alpha for one or all netuids.

        Returns:
            {'total_accumulated': float, 'harvestable': float, 'by_netuid': {netuid: amount}}
        """
        accumulated = self.db.get_accumulated_rewards(netuid)

        if isinstance(accumulated, dict) and "total" in accumulated:
            # Single netuid
            total = accumulated["total"]
            harvestable = total * harvest_fraction
            return {
                "total_accumulated": total,
                "harvestable": harvestable,
                "by_netuid": {netuid: harvestable},
            }
        else:
            # Multiple netuids
            total_acc = sum(accumulated.values())
            harvestable = total_acc * harvest_fraction
            by_netuid = {nuid: amount * harvest_fraction for nuid, amount in accumulated.items()}
            return {
                "total_accumulated": total_acc,
                "harvestable": harvestable,
                "by_netuid": by_netuid,
            }

    def apply_harvest_policy(
        self,
        harvestable_alpha: float,
        min_threshold: float = 0.1,
        max_per_run: float = 10.0,
        max_per_day: float = 50.0,
        today_harvested: float = 0.0,
    ) -> Dict:
        """
        Apply harvest policy constraints.

        Returns:
            {
                'can_harvest': bool,
                'reason': str,
                'amount': float (amount to harvest if allowed)
            }
        """
        if harvestable_alpha < min_threshold:
            return {
                "can_harvest": False,
                "reason": f"Below min threshold ({harvestable_alpha:.6f} < {min_threshold})",
                "amount": 0.0,
            }

        harvest_amount = min(harvestable_alpha, max_per_run)

        if today_harvested + harvest_amount > max_per_day:
            new_amount = max(0, max_per_day - today_harvested)
            return {
                "can_harvest": new_amount > 0,
                "reason": f"Daily cap reached (today: {today_harvested} + {harvest_amount} > {max_per_day})",
                "amount": new_amount,
            }

        return {
            "can_harvest": True,
            "reason": "OK",
            "amount": harvest_amount,
        }

    def get_daily_accounting_summary(self, date: str) -> Dict:
        """Get summary of accounting for a specific date."""
        # TODO: Aggregate rewards, harvests, and withdrawals for the day
        return {
            "date": date,
            "rewards_alpha": 0.0,
            "harvested_tao": 0.0,
            "sold_usd": 0.0,
            "withdrawn_usd": 0.0,
        }
