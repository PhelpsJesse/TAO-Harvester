from __future__ import annotations

from datetime import date

from v2.tao_harvester.adapters.taostats.base import TaostatsIngestionPort
from v2.tao_harvester.db.repository import SQLiteRepository


class SnapshotService:
    """Tier-1 read-only snapshot and event ingestion service."""

    def __init__(self, repository: SQLiteRepository, ingestion: TaostatsIngestionPort):
        self.repository = repository
        self.ingestion = ingestion

    def ingest_day(self, snapshot_date: date, wallet_address: str) -> dict[str, int]:
        snapshots = self.ingestion.fetch_snapshots(snapshot_date, wallet_address)
        transfers = self.ingestion.fetch_transfers(snapshot_date, wallet_address)
        stake_history = self.ingestion.fetch_stake_history(snapshot_date, wallet_address)

        for snapshot in snapshots:
            self.repository.upsert_snapshot(snapshot)
        for transfer in transfers:
            self.repository.insert_transfer_event(snapshot_date, transfer)
        for event in stake_history:
            self.repository.insert_stake_history_event(snapshot_date, event)

        return {
            "snapshot_count": len(snapshots),
            "transfer_count": len(transfers),
            "stake_event_count": len(stake_history),
        }
