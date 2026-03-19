from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TradeEventRecord, TransferRecord


class TaostatsIngestionPort(ABC):
    @abstractmethod
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def fetch_transfers(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TransferRecord]:
        raise NotImplementedError

    @abstractmethod
    def fetch_stake_history(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[StakeHistoryRecord]:
        raise NotImplementedError

    @abstractmethod
    def fetch_trade_events(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TradeEventRecord]:
        raise NotImplementedError
