from __future__ import annotations

from datetime import date

from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.domain.models import ReconciliationResult


class ReconciliationService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def reconcile_day(self, snapshot_date: date, wallet_address: str) -> list[ReconciliationResult]:
        previous_date = self.repository.get_latest_snapshot_date_before(snapshot_date, wallet_address)
        current_map = self.repository.get_snapshot_map(snapshot_date, wallet_address)
        previous_map = self.repository.get_snapshot_map(previous_date, wallet_address) if previous_date else {}
        trade_map = self.repository.get_trade_net_by_netuid(snapshot_date, wallet_address)
        transfer_map = self.repository.get_transfer_net_by_netuid(snapshot_date, wallet_address)

        netuids = sorted(
            set(current_map.keys())
            | set(previous_map.keys())
            | set(trade_map.keys())
            | set(transfer_map.keys())
        )
        output: list[ReconciliationResult] = []

        for netuid in netuids:
            current_alpha = float(current_map.get(netuid, 0.0))
            previous_alpha = float(previous_map.get(netuid, 0.0))
            gross_growth = current_alpha - previous_alpha
            net_trades = float(trade_map.get(netuid, 0.0))
            net_transfers = float(transfer_map.get(netuid, 0.0))
            net_manual = 0.0
            raw_estimated = gross_growth - net_trades - net_transfers
            estimated_earned = max(0.0, raw_estimated)
            max_harvestable_from_balance = max(0.0, current_alpha)
            if estimated_earned > max_harvestable_from_balance:
                estimated_earned = max_harvestable_from_balance
            note = "estimated_earned = max(0, gross_growth - net_trade_adjustment - net_transfers)"
            if raw_estimated < 0.0:
                note = f"{note}; clamped_from_negative=true"
            if estimated_earned < max(0.0, raw_estimated):
                note = f"{note}; capped_by_current_alpha=true"

            result = ReconciliationResult(
                reconciliation_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=netuid,
                previous_alpha=previous_alpha,
                current_alpha=current_alpha,
                gross_growth_alpha=gross_growth,
                net_trade_adjustment_alpha=net_trades,
                net_transfers_alpha=net_transfers,
                net_manual_stake_alpha=net_manual,
                estimated_staking_earned_alpha=estimated_earned,
                notes=note,
            )
            self.repository.upsert_reconciliation(result)
            output.append(result)
        return output
