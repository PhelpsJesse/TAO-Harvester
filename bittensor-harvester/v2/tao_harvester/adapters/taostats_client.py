from __future__ import annotations

from datetime import date
from typing import Protocol

from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TransferRecord


class TaostatsClientPort(Protocol):
    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]: ...

    def fetch_transfers(self, snapshot_date: date, wallet_address: str) -> list[TransferRecord]: ...

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str) -> list[StakeHistoryRecord]: ...
