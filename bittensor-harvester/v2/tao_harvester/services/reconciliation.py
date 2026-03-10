from __future__ import annotations

from datetime import date, timedelta

from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.domain.models import ReconciliationResult


class ReconciliationService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def reconcile_day(self, snapshot_date: date, wallet_address: str) -> list[ReconciliationResult]:
        previous_date = snapshot_date - timedelta(days=1)
        current_map = self.repository.get_snapshot_map(snapshot_date, wallet_address)
        previous_map = self.repository.get_snapshot_map(previous_date, wallet_address)
        transfer_map = self.repository.get_transfer_net_by_netuid(snapshot_date, wallet_address)
        manual_stake_map = self.repository.get_manual_stake_net_by_netuid(snapshot_date, wallet_address)

        netuids = sorted(set(current_map.keys()) | set(previous_map.keys()) | set(transfer_map.keys()) | set(manual_stake_map.keys()))
        output: list[ReconciliationResult] = []

        for netuid in netuids:
            current_alpha = float(current_map.get(netuid, 0.0))
            previous_alpha = float(previous_map.get(netuid, 0.0))
            gross_growth = current_alpha - previous_alpha
            net_transfers = float(transfer_map.get(netuid, 0.0))
            net_manual = float(manual_stake_map.get(netuid, 0.0))
            estimated_earned = max(0.0, gross_growth - net_transfers - net_manual)

            result = ReconciliationResult(
                reconciliation_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=netuid,
                previous_alpha=previous_alpha,
                current_alpha=current_alpha,
                gross_growth_alpha=gross_growth,
                net_transfers_alpha=net_transfers,
                net_manual_stake_alpha=net_manual,
                estimated_staking_earned_alpha=estimated_earned,
                notes="estimated_earned = max(0, gross_growth - net_transfers - net_manual_stake)",
            )
            self.repository.upsert_reconciliation(result)
            output.append(result)
        return output
