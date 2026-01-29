"""
Harvest planning and execution.

Decides when and how much to harvest based on policy.
Queues harvest actions for execution.
Verifies destination address is allowlisted.

Harvest chain:
1. Accumulate alpha rewards in accounting.
2. Check if harvestable amount meets threshold.
3. Apply daily/per-run caps.
4. Verify destination address.
5. Queue conversion action.
6. Execute on-chain (convert alpha → TAO, transfer to destination).
"""

from datetime import datetime
from typing import Dict, Optional
from src.database import Database
from src.accounting import Accounting


class HarvestPolicy:
    """Harvest policy enforcement."""

    # Allowlist of safe destinations
    DESTINATION_ALLOWLIST = {
        # TODO: Populate with verified addresses
        # Example: "5XsJq4dKXW8UmCkR9dMG4gXQgJxNQvwJK5x8E9K8QQQQQQQQq": "Kraken Deposit",
    }

    def __init__(self, db: Database, accounting: Accounting, config_harvest_dest: str):
        """Initialize harvest policy."""
        self.db = db
        self.accounting = accounting
        self.config_harvest_dest = config_harvest_dest
        
        # Add config destination to allowlist at init
        if config_harvest_dest:
            self.DESTINATION_ALLOWLIST[config_harvest_dest] = "Config Destination"

    def is_destination_allowed(self, address: str) -> bool:
        """Check if destination address is allowlisted."""
        return address in self.DESTINATION_ALLOWLIST

    def plan_harvest(
        self,
        harvestable_alpha: float,
        destination_address: str,
        min_threshold: float = 0.1,
        max_per_run: float = 10.0,
        max_per_day: float = 50.0,
        conversion_rate_alpha_to_tao: float = 1.0,
    ) -> Dict:
        """
        Plan a harvest action.

        Args:
            harvestable_alpha: Amount of alpha available to harvest
            destination_address: Target address for TAO transfer
            min_threshold: Minimum alpha to harvest (avoid dust)
            max_per_run: Cap per execution
            max_per_day: Cap per calendar day
            conversion_rate_alpha_to_tao: Rate for alpha → TAO (mock for now)

        Returns:
            {
                'can_proceed': bool,
                'reason': str,
                'harvest_plan': {
                    'alpha_amount': float,
                    'tao_amount': float,
                    'destination': str,
                    'conversion_rate': float
                } or None
            }
        """
        # Check destination allowlist
        if not self.is_destination_allowed(destination_address):
            return {
                "can_proceed": False,
                "reason": f"Destination {destination_address} not in allowlist",
                "harvest_plan": None,
            }

        # Apply policy constraints
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_harvested = self.db.get_daily_total_harvest(today)

        policy_result = self.accounting.apply_harvest_policy(
            harvestable_alpha=harvestable_alpha,
            min_threshold=min_threshold,
            max_per_run=max_per_run,
            max_per_day=max_per_day,
            today_harvested=today_harvested,
        )

        if not policy_result["can_harvest"]:
            return {
                "can_proceed": False,
                "reason": policy_result["reason"],
                "harvest_plan": None,
            }

        harvest_alpha = policy_result["amount"]
        harvest_tao = harvest_alpha * conversion_rate_alpha_to_tao

        return {
            "can_proceed": True,
            "reason": "OK",
            "harvest_plan": {
                "alpha_amount": harvest_alpha,
                "tao_amount": harvest_tao,
                "destination": destination_address,
                "conversion_rate": conversion_rate_alpha_to_tao,
            },
        }

    def queue_harvest(
        self,
        alpha_amount: float,
        tao_amount: float,
        destination_address: str,
        conversion_rate: float = 1.0,
    ) -> int:
        """
        Queue a harvest action in the database.

        Args:
            alpha_amount: Amount of alpha to harvest
            tao_amount: Equivalent amount in TAO
            destination_address: Allowlisted destination
            conversion_rate: alpha to TAO rate

        Returns:
            Harvest record ID
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        self.db.insert_harvest(
            harvest_date=today,
            alpha_amount=alpha_amount,
            tao_amount=tao_amount,
            destination_address=destination_address,
            conversion_rate=conversion_rate,
            notes="Queued by harvest policy",
        )
        
        # Update daily cap
        self.db.update_daily_harvest(today, tao_amount, 50.0)  # TODO: use config max_per_day

        # TODO: Return harvest ID (insert_harvest should return it)
        return self.db.conn.execute(
            "SELECT MAX(id) FROM harvests"
        ).fetchone()[0]

    def get_pending_harvests(self) -> list:
        """Get all pending harvest records."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT id, alpha_amount, tao_amount, destination_address FROM harvests WHERE status = ?",
            ("pending",),
        )
        return [dict(row) for row in cursor.fetchall()]
