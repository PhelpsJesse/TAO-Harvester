from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TransferRecord


class TaostatsIngestionPort(ABC):
    @abstractmethod
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def fetch_transfers(self, snapshot_date: date, wallet_address: str) -> list[TransferRecord]:
        raise NotImplementedError

    @abstractmethod
    def fetch_stake_history(self, snapshot_date: date, wallet_address: str) -> list[StakeHistoryRecord]:
        raise NotImplementedError
