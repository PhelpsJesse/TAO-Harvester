from __future__ import annotations

from datetime import date, datetime, timezone

from v2.tao_harvester.adapters.taostats.base import TaostatsIngestionPort
from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TradeEventRecord, TransferRecord


class MockTaostatsAdapter(TaostatsIngestionPort):
    source_name = "taostats_mock"

    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]:
        base = {
            1: 120.0,
            8: 45.0,
            19: 12.5,
        }
        drift = (snapshot_date.toordinal() % 3) * 0.2
        return [
            AlphaSnapshot(
                snapshot_date=snapshot_date,
                wallet_address=wallet_address,
                netuid=netuid,
                alpha_balance=amount + drift,
                source=self.source_name,
                observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    tao_per_alpha=1.0,
                )
            for netuid, amount in base.items()
        ]

    def fetch_transfers(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TransferRecord]:
        return [
            TransferRecord(
                transfer_id=f"mock-transfer-{snapshot_date.isoformat()}-n8",
                wallet_address=wallet_address,
                netuid=8,
                direction="in",
                alpha_amount=0.25,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source=self.source_name,
            )
        ]

    def fetch_stake_history(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[StakeHistoryRecord]:
        return [
            StakeHistoryRecord(
                event_id=f"mock-stake-{snapshot_date.isoformat()}-n1",
                wallet_address=wallet_address,
                netuid=1,
                action="manual_stake",
                alpha_amount=0.1,
                occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
                source=self.source_name,
            )
        ]

    def fetch_trade_events(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TradeEventRecord]:
        return []
