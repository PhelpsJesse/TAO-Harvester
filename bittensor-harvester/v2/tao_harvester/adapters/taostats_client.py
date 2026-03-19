from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TradeEventRecord, TransferRecord


class TaostatsClientPort(Protocol):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]: ...

    def fetch_transfers(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TransferRecord]: ...

    def fetch_stake_history(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[StakeHistoryRecord]: ...

    def fetch_trade_events(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TradeEventRecord]: ...
