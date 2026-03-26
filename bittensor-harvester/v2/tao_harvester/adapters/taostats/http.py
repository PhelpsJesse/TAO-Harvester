from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import time
from typing import Any
from datetime import timezone

import requests

from v2.tao_harvester.adapters.taostats.base import TaostatsIngestionPort
from v2.tao_harvester.domain.models import AlphaSnapshot, StakeHistoryRecord, TradeEventRecord, TransferRecord

logger = logging.getLogger(__name__)


class TaostatsHttpAdapter(TaostatsIngestionPort):
    CANONICAL_AMOUNT_UNIT = "alpha"
    DEFAULT_RETRIES = 3  # spec Section 21: retry attempts MUST NOT exceed 3
    DEFAULT_MAX_WAIT_SEC = 90.0
    POST_429_PAGE_DELAY_SEC = 12.0

    TRADE_CALL_NAMES = {
        "SubtensorModule.add_stake_limit": "buy_alpha",
        "SubtensorModule.remove_stake_limit": "sell_alpha",
    }
    TRADE_BUY_TOKENS = ("swap_tao_for_alpha", "buy_alpha", "add_stake", "delegate")
    TRADE_SELL_TOKENS = ("swap_alpha_for_tao", "sell_alpha", "remove_stake", "undelegate", "unstake")

    def __init__(self, base_url: str, api_key: str | None = None, timeout_sec: int = 20):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.session = requests.Session()
        self._account_latest_cache: dict[str, dict[str, Any]] = {}
        self._saw_rate_limit = False
        if api_key:
            self.session.headers.update({"Authorization": api_key})
        self.source_name = "taostats_http"

    def _get(
        self,
        path: str,
        params: dict[str, Any],
        retries: int | None = None,
        max_wait_sec: float | None = None,
    ) -> dict[str, Any]:
        return self._get_with_retry(
            path,
            params,
            retries=self.DEFAULT_RETRIES if retries is None else retries,
            max_wait_sec=self.DEFAULT_MAX_WAIT_SEC if max_wait_sec is None else max_wait_sec,
        )

    def _get_with_retry(
        self,
        path: str,
        params: dict[str, Any],
        retries: int = 3,
        max_wait_sec: float = DEFAULT_MAX_WAIT_SEC,
    ) -> dict[str, Any]:
        for attempt in range(retries + 1):
            response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout_sec)
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()
            self._saw_rate_limit = True
            if attempt >= retries:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    wait_seconds = max(0.5, float(retry_after))
                except ValueError:
                    wait_seconds = min(max_wait_sec, 1.0 * (2**attempt))
            else:
                wait_seconds = min(max_wait_sec, 1.0 * (2**attempt))
            logger.debug("429 on %s attempt=%s; waiting %.1fs", path, attempt, wait_seconds)
            time.sleep(wait_seconds)
        raise RuntimeError("rate limit retry exhausted")

    def _get_paged(
        self,
        path: str,
        base_params: dict[str, Any],
        limit: int = 200,
        max_pages: int = 100,
        retries: int | None = None,
        max_wait_sec: float | None = None,
        page_delay_sec: float | None = None,
    ) -> list[dict[str, Any]]:
        page = 1
        collected: list[dict[str, Any]] = []
        while page <= max_pages:
            params = dict(base_params)
            params["page"] = page
            params["limit"] = limit
            payload = self._get(path, params, retries=retries, max_wait_sec=max_wait_sec)
            items = payload.get("data", [])
            if not items:
                break
            collected.extend(items)
            pagination = payload.get("pagination", {})
            next_page = pagination.get("next_page")
            if not next_page or next_page == page:
                break
            delay = page_delay_sec
            if delay is None and self._saw_rate_limit:
                delay = self.POST_429_PAGE_DELAY_SEC
            if delay and delay > 0:
                logger.debug("pagination throttle on %s; sleeping %.1fs before next page", path, delay)
                time.sleep(delay)
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
        if raw_amount is None:
            return 0.0

        # Taostats frequently returns RAO as integer-like strings (even for tiny values).
        # Treat integer-like values as RAO and divide by 1e9; decimal-like values are treated as already normalized.
        if isinstance(raw_amount, str):
            text = raw_amount.strip()
            if not text:
                return 0.0
            if text.lstrip("+-").isdigit():
                try:
                    return int(text) / 1e9
                except ValueError:
                    return 0.0
            try:
                value = float(text)
            except ValueError:
                return 0.0
            if abs(value) > 1e6:
                return value / 1e9
            return value

        if isinstance(raw_amount, int):
            return raw_amount / 1e9

        try:
            value = float(raw_amount)
        except (TypeError, ValueError):
            return 0.0
        if abs(value) > 1e6:
            return value / 1e9
        return value

    @staticmethod
    def _extract_ss58(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("ss58") or "")
        return str(value or "")

    def _extract_alpha_amount(
        self,
        payload: dict[str, Any],
        preferred_keys: tuple[str, ...],
        fallback_keys: tuple[str, ...] = (),
    ) -> float:
        for key in preferred_keys:
            if payload.get(key) is not None:
                return self._normalize_amount(payload.get(key))
        for key in fallback_keys:
            if payload.get(key) is not None:
                return self._normalize_amount(payload.get(key))
        return 0.0

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def fetch_snapshots(self, snapshot_date: date, wallet_address: str) -> list[AlphaSnapshot]:
        try:
            payload = self._account_latest_cache.get(wallet_address)
            if payload is None:
                payload = self._get("/api/account/latest/v1", {"address": wallet_address, "network": "finney"})
                self._account_latest_cache[wallet_address] = payload
            items = payload.get("data", [])
        except Exception as exc:
            raise RuntimeError(
                "Taostats snapshot fetch failed; upstream data required for reconciliation is unavailable. "
                "Retry after cooldown."
            ) from exc

        if not items:
            return []

        account_latest = items[0]
        latest_timestamp = self._parse_ts(account_latest.get("timestamp"))
        latest_date = latest_timestamp.date()

        if snapshot_date == latest_date:
            alpha_entries = account_latest.get("alpha_balances", [])
            observed_at = latest_timestamp
        elif snapshot_date == (latest_date - timedelta(days=1)):
            alpha_entries = account_latest.get("alpha_balances_24hr_ago", [])
            observed_at = latest_timestamp - timedelta(hours=24)
        else:
            alpha_entries = []
            observed_at = latest_timestamp

        if alpha_entries:
            return self._map_alpha_entries_to_snapshots(alpha_entries, snapshot_date, wallet_address, observed_at)

        raise RuntimeError(
            "Snapshot date is outside Taostats account/latest coverage (latest and latest-1 only). "
            "Historical backfill is disabled to avoid inconsistent reconciliation baselines. "
            "Ensure the prior-day baseline snapshot already exists in the DB before running daily-report."
        )

    def _map_alpha_entries_to_snapshots(
        self,
        alpha_entries: list[dict[str, Any]],
        snapshot_date: date,
        wallet_address: str,
        observed_at: datetime,
    ) -> list[AlphaSnapshot]:
        snapshots: list[AlphaSnapshot] = []
        for entry in alpha_entries:
            try:
                netuid = int(entry.get("netuid"))
                if netuid <= 0:
                    continue
                raw_balance = entry.get("balance") or entry.get("balance_rao") or 0
                alpha_balance = self._normalize_amount(raw_balance)
                raw_balance_as_tao = entry.get("balance_as_tao") or entry.get("balance_alpha_as_tao")
                tao_equivalent = self._normalize_amount(raw_balance_as_tao) if raw_balance_as_tao is not None else None
                tao_per_alpha = (tao_equivalent / alpha_balance) if (tao_equivalent is not None and alpha_balance > 0) else None
            except (TypeError, ValueError):
                continue
            snapshots.append(
                AlphaSnapshot(
                    snapshot_date=snapshot_date,
                    wallet_address=wallet_address,
                    netuid=netuid,
                    alpha_balance=alpha_balance,
                    source=self.source_name,
                    observed_at=observed_at.replace(tzinfo=None),
                    tao_per_alpha=tao_per_alpha,
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
                    retries=10,
                    max_wait_sec=90.0,
                )
            except Exception as exc:
                if "429" in str(exc):
                    raise RuntimeError(
                        "Taostats rate limit reached during historical snapshot backfill; "
                        "aborting to avoid partial daily report. Retry after cooldown."
                    ) from exc
                logger.warning("Taostats historical snapshot fetch failed for netuid=%s: %s", netuid, exc)
                continue
            time.sleep(12.0)  # throttle to respect 5 req/min Taostats API rate limit (60 sec / 5 = 12 sec/request)

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
                    tao_per_alpha=None,
                )
            )

        return snapshots

    def fetch_transfers(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TransferRecord]:
        start_dt = self._as_utc(window_start) or datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = self._as_utc(window_end) or datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 23, 59, 59, tzinfo=timezone.utc)
        params = {
            "address": wallet_address,
            "timestamp_start": int(start_dt.timestamp()),
            "timestamp_end": int(end_dt.timestamp()),
            "order": "block_number_asc",
        }

        try:
            items = self._get_paged("/api/transfer/v1", params, limit=1000, max_pages=20)
        except Exception as exc:
            raise RuntimeError(
                "Taostats transfer fetch failed; upstream data required for reconciliation is unavailable or incomplete. "
                "Retry after cooldown."
            ) from exc

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
                    alpha_amount=self._extract_alpha_amount(
                        item,
                        preferred_keys=("alpha", "alpha_amount", "amount_alpha", "amountAlpha"),
                        fallback_keys=("amount",),
                    ),
                    occurred_at=self._parse_ts(item.get("timestamp")),
                    source=self.source_name,
                )
            )

        return transfers

    def fetch_stake_history(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[StakeHistoryRecord]:
        start_dt = self._as_utc(window_start) or datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = self._as_utc(window_end) or datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 23, 59, 59, tzinfo=timezone.utc)
        params = {
            "nominator": wallet_address,
            "timestamp_start": int(start_dt.timestamp()),
            "timestamp_end": int(end_dt.timestamp()),
            "order": "block_number_asc",
        }

        try:
            items = self._get_paged("/api/delegation/v1", params, limit=1000, max_pages=20)
        except Exception as exc:
            raise RuntimeError(
                "Taostats stake-history fetch failed; upstream data required for reconciliation is unavailable or incomplete. "
                "Retry after cooldown."
            ) from exc

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
                    alpha_amount=self._extract_alpha_amount(
                        item,
                        preferred_keys=("alpha", "alpha_amount", "amount_alpha", "amountAlpha"),
                        fallback_keys=("amount",),
                    ),
                    occurred_at=self._parse_ts(item.get("timestamp")),
                    source=self.source_name,
                )
            )

        return stake_events

    def fetch_trade_events(
        self,
        snapshot_date: date,
        wallet_address: str,
        window_start: datetime | None = None,
        window_end: datetime | None = None,
    ) -> list[TradeEventRecord]:
        start_dt = self._as_utc(window_start) or datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = self._as_utc(window_end) or datetime(snapshot_date.year, snapshot_date.month, snapshot_date.day, 23, 59, 59, tzinfo=timezone.utc)
        params = {
            "origin_address": wallet_address,
            "timestamp_start": int(start_dt.timestamp()),
            "timestamp_end": int(end_dt.timestamp()),
            "order": "block_number_asc",
        }

        try:
            calls: list[dict[str, Any]] = []
            for full_name in self.TRADE_CALL_NAMES:
                filtered_params = dict(params)
                filtered_params["full_name"] = full_name
                calls.extend(
                    self._get_paged(
                        "/api/call/v1",
                        filtered_params,
                        limit=1000,
                        max_pages=20,
                        # Keep call ingestion fast once delegation paging has been rate-shaped.
                        page_delay_sec=0.0,
                    )
                )
        except Exception as exc:
            raise RuntimeError(
                "Taostats trade-event fetch failed; upstream data required for reconciliation is unavailable or incomplete. "
                "Retry after cooldown."
            ) from exc

        trades: list[TradeEventRecord] = []
        seen_trade_ids: set[str] = set()
        for call in calls:
            full_name = str(call.get("full_name") or "")
            args = call.get("args") or {}
            direction = self.TRADE_CALL_NAMES.get(full_name) or self._infer_trade_direction(full_name, args)
            if direction is None:
                continue

            trade = self._extract_trade_call(wallet_address, direction, full_name, call)
            if trade is None or trade.trade_id in seen_trade_ids:
                continue
            seen_trade_ids.add(trade.trade_id)
            trades.append(trade)

        return trades

    def _infer_trade_direction(self, full_name: str, args: dict[str, Any]) -> str | None:
        if "amountStaked" in args or "amount_staked" in args:
            return "buy_alpha"
        if "amountUnstaked" in args or "amount_unstaked" in args:
            return "sell_alpha"

        lowered = full_name.lower()
        if any(token in lowered for token in self.TRADE_BUY_TOKENS):
            return "buy_alpha"
        if any(token in lowered for token in self.TRADE_SELL_TOKENS):
            return "sell_alpha"
        return None

    def _extract_trade_call(
        self,
        wallet_address: str,
        direction: str,
        full_name: str,
        call: dict[str, Any],
    ) -> TradeEventRecord | None:
        trade_id = str(call.get("id") or call.get("extrinsic_id") or "")
        if not trade_id:
            return None

        args = call.get("args") or {}
        netuid_raw = args.get("netuid") or args.get("subnet_id")
        if netuid_raw is None:
            return None
        try:
            netuid = int(netuid_raw)
        except (TypeError, ValueError):
            return None
        if netuid <= 0:
            return None

        alpha_amount = self._extract_trade_alpha_amount(direction=direction, full_name=full_name, args=args)
        if alpha_amount is None:
            return None

        return TradeEventRecord(
            trade_id=trade_id,
            wallet_address=wallet_address,
            netuid=netuid,
            direction=direction,
            alpha_amount=alpha_amount,
            occurred_at=self._parse_ts(call.get("timestamp")),
            source=self.source_name,
        )

    @staticmethod
    def _parse_intlike(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            text = value.strip()
            if text.lstrip("+-").isdigit():
                try:
                    return int(text)
                except ValueError:
                    return None
        return None

    def _extract_trade_alpha_amount(self, direction: str, full_name: str, args: dict[str, Any]) -> float | None:
        # Prefer explicit alpha-denominated fields when present.
        for key in ("alpha_amount", "alphaAmount", "amount_alpha", "amountAlpha"):
            if key in args and args.get(key) is not None:
                return self._normalize_amount(args.get(key))

        if direction == "buy_alpha":
            if full_name == "SubtensorModule.add_stake_limit":
                # Taostats call args encode add_stake_limit as TAO in (`amountStaked`) and
                # limit price in RAO-per-alpha (`limitPrice`), so convert to canonical alpha amount.
                tao_in_rao = self._parse_intlike(args.get("amountStaked") or args.get("amount_staked"))
                limit_price_rao_per_alpha = self._parse_intlike(args.get("limitPrice") or args.get("limit_price"))
                if tao_in_rao is not None and limit_price_rao_per_alpha and limit_price_rao_per_alpha > 0:
                    return float(tao_in_rao) / float(limit_price_rao_per_alpha)
                logger.debug(
                    "Could not convert add_stake_limit amount to alpha (missing/invalid limitPrice); "
                    "using 0 alpha placeholder for trade_id matching fallback."
                )
                return 0.0

            raw = args.get("amountStaked") or args.get("amount_staked") or args.get("amount")
            if raw is not None:
                return self._normalize_amount(raw)

        if direction == "sell_alpha":
            raw = args.get("amountUnstaked") or args.get("amount_unstaked") or args.get("amount")
            if raw is not None:
                return self._normalize_amount(raw)

        return None
