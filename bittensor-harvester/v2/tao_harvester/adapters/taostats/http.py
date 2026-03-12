from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import time
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
        self._account_latest_cache: dict[str, dict[str, Any]] = {}
        if api_key:
            self.session.headers.update({"Authorization": api_key})
        self.source_name = "taostats_http"

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._get_with_retry(path, params)

    def _get_with_retry(self, path: str, params: dict[str, Any], retries: int = 6) -> dict[str, Any]:
        for attempt in range(retries + 1):
            response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout_sec)
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()
            if attempt >= retries:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_seconds = max(0.5, float(retry_after))
                except ValueError:
                    wait_seconds = min(12.0, 1.0 * (2**attempt))
            else:
                wait_seconds = min(12.0, 1.0 * (2**attempt))
            time.sleep(wait_seconds)
        raise RuntimeError("rate limit retry exhausted")

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
        try:
            payload = self._account_latest_cache.get(wallet_address)
            if payload is None:
                payload = self._get("/api/account/latest/v1", {"address": wallet_address, "network": "finney"})
                self._account_latest_cache[wallet_address] = payload
            items = payload.get("data", [])
        except Exception as exc:
            logger.warning("Taostats snapshot fetch failed: %s", exc)
            return []

        if not items:
            return []

        account_latest = items[0]
        latest_timestamp = self._parse_ts(account_latest.get("timestamp"))
        latest_date = latest_timestamp.date()

        if snapshot_date == latest_date:
            alpha_entries = account_latest.get("alpha_balances", [])
        elif snapshot_date == (latest_date - timedelta(days=1)):
            alpha_entries = account_latest.get("alpha_balances_24hr_ago", [])
        else:
            alpha_entries = []

        if alpha_entries:
            return self._map_alpha_entries_to_snapshots(alpha_entries, snapshot_date, wallet_address)

        coldkey = self._extract_ss58(account_latest.get("address")) or wallet_address
        current_alpha_entries = account_latest.get("alpha_balances", [])
        return self._fetch_historical_snapshots(snapshot_date=snapshot_date, wallet_address=wallet_address, coldkey=coldkey, reference_alpha_entries=current_alpha_entries)

    def _map_alpha_entries_to_snapshots(self, alpha_entries: list[dict[str, Any]], snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]:
        snapshots: list[AlphaSnapshot] = []
        for entry in alpha_entries:
            try:
                netuid = int(entry.get("netuid"))
                if netuid <= 0:
                    continue
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

    def _fetch_historical_snapshots(
        self,
        snapshot_date: date,
        wallet_address: str,
        coldkey: str,
        reference_alpha_entries: list[dict[str, Any]],
    ) -> list[AlphaSnapshot]:
        snapshots: list[AlphaSnapshot] = []
        date_iso = snapshot_date.isoformat()

        for entry in reference_alpha_entries:
            hotkey = str(entry.get("hotkey") or "")
            netuid_raw = entry.get("netuid")
            if not hotkey or netuid_raw is None:
                continue
            try:
                netuid = int(netuid_raw)
            except (TypeError, ValueError):
                continue
            if netuid <= 0:
                continue

            try:
                payload = self._get_with_retry(
                    "/api/dtao/stake_balance/history/v1",
                    {
                        "coldkey": coldkey,
                        "hotkey": hotkey,
                        "netuid": netuid,
                        "date_start": date_iso,
                        "date_end": date_iso,
                        "order": "timestamp_desc",
                        "limit": 1,
                    },
                )
            except Exception as exc:
                logger.warning("Taostats historical snapshot fetch failed for netuid=%s: %s", netuid, exc)
                continue

            data = payload.get("data", [])
            if not data:
                continue

            hist = data[0]
            raw_balance = hist.get("balance") or 0
            alpha_balance = self._normalize_amount(raw_balance)
            snapshots.append(
                AlphaSnapshot(
                    snapshot_date=snapshot_date,
                    wallet_address=wallet_address,
                    netuid=netuid,
                    alpha_balance=alpha_balance,
                    source=self.source_name,
                    observed_at=self._parse_ts(hist.get("timestamp")),
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
            if netuid <= 0:
                continue

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
            if netuid <= 0:
                continue

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
