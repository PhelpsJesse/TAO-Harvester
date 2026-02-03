"""
Accounting & delta computation.

Tracks earned alpha rewards using database snapshots.
Applies harvest policy to determine harvestable amount.

Logic:
1. Daily snapshots stored in database (via import_snapshot.py)
2. Delta = today_balance - yesterday_balance - net_transfers
3. Record emissions as rewards in database
4. Apply harvest fraction (50%) to determine harvestable amount
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple, List
from src.database import Database


class Accounting:
    """Accounting system for reward tracking and delta computation using database snapshots."""

    def __init__(self, db: Database):
        """Initialize accounting with database connection."""
        self.db = db

    def compute_daily_delta(
        self, address: str, netuid: int, today_date: str = None, yesterday_date: str = None
    ) -> Tuple[float, float]:
        """
        Compute daily reward delta using database snapshots.

        Args:
            address: SS58 address
            netuid: Subnet ID
            today_date: Date string (YYYY-MM-DD), defaults to today
            yesterday_date: Date string (YYYY-MM-DD), defaults to yesterday

        Returns:
            (current_balance, earned_alpha)
        """
        if today_date is None:
            today_date = datetime.utcnow().date().isoformat()
        if yesterday_date is None:
            yesterday_date = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

        # Get snapshots from database
        today_snapshot = self.db.get_alpha_snapshot(address, netuid, today_date)
        yesterday_snapshot = self.db.get_alpha_snapshot(address, netuid, yesterday_date)

        current_balance = today_snapshot['alpha_balance'] if today_snapshot else 0.0
        prev_balance = yesterday_snapshot['alpha_balance'] if yesterday_snapshot else 0.0

        # Get net transfers between dates (to exclude from emissions calculation)
        transfers = self.db.get_transfers_by_date_range(address, yesterday_date, today_date)
        net_transfers = sum(t['amount'] for t in transfers if t['to_address'] == address) - \
                       sum(t['amount'] for t in transfers if t['from_address'] == address)

        # Earned = today - yesterday - net_transfers
        earned = max(0, current_balance - prev_balance - net_transfers)
        
        # Store in database for historical tracking/graphing
        if earned > 0 or current_balance != prev_balance:
            self.db.insert_daily_emission(
                address=address,
                netuid=netuid,
                emission_date=today_date,
                previous_balance=prev_balance,
                current_balance=current_balance,
                net_transfers=net_transfers,
                emissions_earned=earned
            )
        
        return current_balance, earned
    
    def compute_all_subnets_delta(
        self, address: str, today_date: str = None, yesterday_date: str = None
    ) -> Dict[int, Dict]:
        """
        Compute daily deltas for all subnets at once.

        Args:
            address: SS58 address
            today_date: Date string (YYYY-MM-DD), defaults to today
            yesterday_date: Date string (YYYY-MM-DD), defaults to yesterday

        Returns:
            {
                netuid: {
                    'current_balance': float,
                    'previous_balance': float,
                    'net_transfers': float,
                    'earned_alpha': float
                },
                ...
            }
        """
        if today_date is None:
            today_date = datetime.utcnow().date().isoformat()
        if yesterday_date is None:
            yesterday_date = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

        # Get all snapshots for both dates
        today_snapshots = self.db.get_all_snapshots_by_date(address, today_date)
        yesterday_snapshots = self.db.get_all_snapshots_by_date(address, yesterday_date)

        # Convert to dictionaries keyed by netuid
        today_by_subnet = {s['netuid']: s['alpha_balance'] for s in today_snapshots}
        yesterday_by_subnet = {s['netuid']: s['alpha_balance'] for s in yesterday_snapshots}

        # Get transfers
        transfers = self.db.get_transfers_by_date_range(address, yesterday_date, today_date)
        
        # Calculate net transfers (positive = received, negative = sent)
        net_transfers = sum(t['amount'] for t in transfers if t['to_address'] == address) - \
                       sum(t['amount'] for t in transfers if t['from_address'] == address)

        # Combine all subnet IDs
        all_netuids = set(today_by_subnet.keys()) | set(yesterday_by_subnet.keys())

        results = {}
        for netuid in all_netuids:
            current = today_by_subnet.get(netuid, 0.0)
            previous = yesterday_by_subnet.get(netuid, 0.0)
            
            # For now, distribute net transfers proportionally or assume zero per subnet
            # (More accurate would be per-subnet transfer tracking)
            subnet_net_transfers = 0.0  # TODO: Track transfers per subnet if needed
            
            earned = max(0, current - previous - subnet_net_transfers)
            
            results[netuid] = {
                'current_balance': current,
                'previous_balance': previous,
                'net_transfers': subnet_net_transfers,
                'earned_alpha': earned
            }
            
            # Store in database for historical tracking/graphing
            if earned > 0 or current != previous:
                self.db.insert_daily_emission(
                    address=address,
                    netuid=netuid,
                    emission_date=today_date,
                    previous_balance=previous,
                    current_balance=current,
                    net_transfers=subnet_net_transfers,
                    emissions_earned=earned
                )

        return results

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
