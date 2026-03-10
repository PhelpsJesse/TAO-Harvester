from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any
from datetime import timezone

import requests

from v2.tao_harvester.adapters.taostats.base import TaostatsIngestionPort
from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TransferRecord

logger = logging.getLogger(__name__)


class TaostatsHttpAdapter(TaostatsIngestionPort):
    def __init__(self, base_url: str, api_key: str | None = None, timeout_sec: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"Authorization": api_key})
        self.source_name = "taostats_http"

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout_sec)
        response.raise_for_status()
        return response.json()

    def _get_paged(self, path: str, base_params: dict[str, Any], limit: int = 200, max_pages: int = 10) -> list[dict[str, Any]]:
        page = 1
        collected: list[dict[str, Any]] = []
        while page <= max_pages:
            params = dict(base_params)
            params["page"] = page
            params["limit"] = limit
            payload = self._get(path, params)
            items = payload.get("data", [])
            if not items:
                break
            collected.extend(items)
            pagination = payload.get("pagination", {})
            next_page = pagination.get("next_page")
            if not next_page or next_page == page:
                break
            page = int(next_page)
        return collected

    @staticmethod
    def _parse_ts(raw: Any) -> datetime:
        if not raw:
            return datetime.now(timezone.utc).replace(tzinfo=None)
        if isinstance(raw, (int, float)):
            return datetime.fromtimestamp(float(raw), tz=timezone.utc).replace(tzinfo=None)
        text = str(raw)
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalize_amount(raw_amount: Any) -> float:
        try:
            value = float(raw_amount or 0)
        except (TypeError, ValueError):
            return 0.0
        if value > 1e6:
            return value / 1e9
        return value

    @staticmethod
    def _extract_ss58(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("ss58") or "")
        return str(value or "")

    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]:
        # TODO: Confirm canonical endpoint/fields for account latest balances.
        # Example placeholder endpoint used in prior codebase:
        # /api/account/latest/v1?address=...&network=finney
        try:
            payload = self._get("/api/account/latest/v1", {"address": wallet_address, "network": "finney"})
            items = payload.get("data", [])
        except Exception as exc:
            logger.warning("Taostats snapshot fetch failed: %s", exc)
            return []

        snapshots: list[AlphaSnapshot] = []
        for item in items:
            for entry in item.get("alpha_balances", []):
                try:
                    netuid = int(entry.get("netuid"))
                    raw_balance = entry.get("balance") or entry.get("balance_rao") or 0
                    alpha_balance = float(raw_balance)
                    if alpha_balance > 1e6:
                        alpha_balance = alpha_balance / 1e9
                except (TypeError, ValueError):
                    continue
                snapshots.append(
                    AlphaSnapshot(
                        snapshot_date=snapshot_date,
                        wallet_address=wallet_address,
                        netuid=netuid,
                        alpha_balance=alpha_balance,
                        source=self.source_name,
                        observed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                )
        return snapshots

    def fetch_transfers(self, snapshot_date: date, wallet_address: str) -> list[TransferRecord]:
        start_dt = datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 23, 59, 59, tzinfo=timezone.utc)
        params = {
            "address": wallet_address,
            "timestamp_start": int(start_dt.timestamp()),
            "timestamp_end": int(end_dt.timestamp()),
            "order": "block_number_asc",
        }

        try:
            items = self._get_paged("/api/transfer/v1", params)
        except Exception as exc:
            logger.warning("Taostats transfer fetch failed: %s", exc)
            return []

        transfers: list[TransferRecord] = []
        for item in items:
            transfer_id = str(item.get("extrinsic_id") or item.get("extrinsic_hash") or item.get("id") or "")
            if not transfer_id:
                continue

            to_ss58 = self._extract_ss58(item.get("to"))
            from_ss58 = self._extract_ss58(item.get("from"))

            direction = "in" if to_ss58 == wallet_address else "out"
            if to_ss58 != wallet_address and from_ss58 != wallet_address:
                continue

            netuid_raw = item.get("subnet_uid") or item.get("netuid")
            try:
                netuid = int(netuid_raw) if netuid_raw is not None else 0
            except (TypeError, ValueError):
                netuid = 0

            transfers.append(
                TransferRecord(
                    transfer_id=transfer_id,
                    wallet_address=wallet_address,
                    netuid=netuid,
                    direction=direction,
                    alpha_amount=self._normalize_amount(item.get("amount")),
                    occurred_at=self._parse_ts(item.get("timestamp")),
                    source=self.source_name,
                )
            )

        return transfers

    def fetch_stake_history(self, snapshot_date: date, wallet_address: str) -> list[StakeHistoryRecord]:
        start_dt = datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 23, 59, 59, tzinfo=timezone.utc)
        params = {
            "nominator": wallet_address,
            "timestamp_start": int(start_dt.timestamp()),
            "timestamp_end": int(end_dt.timestamp()),
            "order": "block_number_asc",
        }

        try:
            items = self._get_paged("/api/delegation/v1", params)
        except Exception as exc:
            logger.warning("Taostats stake-history fetch failed: %s", exc)
            return []

        stake_events: list[StakeHistoryRecord] = []
        for item in items:
            event_id = str(item.get("extrinsic_id") or item.get("extrinsic_hash") or item.get("id") or "")
            if not event_id:
                continue

            action_raw = str(item.get("action") or "").upper()
            if action_raw in {"DELEGATE", "ADD", "STAKE"}:
                action = "manual_stake"
            elif action_raw in {"UNDELEGATE", "REMOVE", "UNSTAKE"}:
                action = "manual_unstake"
            else:
                action = "manual_stake"

            netuid_raw = item.get("subnet_uid") or item.get("netuid")
            try:
                netuid = int(netuid_raw) if netuid_raw is not None else 0
            except (TypeError, ValueError):
                netuid = 0

            stake_events.append(
                StakeHistoryRecord(
                    event_id=event_id,
                    wallet_address=wallet_address,
                    netuid=netuid,
                    action=action,
                    alpha_amount=self._normalize_amount(item.get("alpha") or item.get("amount")),
                    occurred_at=self._parse_ts(item.get("timestamp")),
                    source=self.source_name,
                )
            )

        return stake_events
