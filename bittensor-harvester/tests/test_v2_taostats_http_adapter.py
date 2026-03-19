import unittest
from datetime import date

from v2.tao_harvester.adapters.taostats.http import TaostatsHttpAdapter


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, wallet_address: str):
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict, int]] = []
        self.wallet_address = wallet_address

    def get(self, url: str, params: dict | None = None, timeout: int | None = None):
        params = params or {}
        self.calls.append((url, params, timeout))

        if url.endswith("/api/account/latest/v1"):
            return _FakeResponse(
                {
                    "data": [
                        {
                            "timestamp": "2026-03-12T15:28:36Z",
                            "address": {"ss58": self.wallet_address},
                            "alpha_balances": [
                                {"netuid": "1", "balance_rao": 3_250_000_000, "hotkey": "5Hot1"},
                                {"netuid": 2, "balance": 4.25, "hotkey": "5Hot1"},
                            ],
                            "alpha_balances_24hr_ago": [
                                {"netuid": "1", "balance_rao": 3_100_000_000, "hotkey": "5Hot1"},
                                {"netuid": 2, "balance": 4.0, "hotkey": "5Hot1"},
                            ],
                        }
                    ]
                }
            )

        if url.endswith("/api/dtao/stake_balance/history/v1"):
            return _FakeResponse(
                {
                    "data": [
                        {
                            "netuid": int(params.get("netuid", 0)),
                            "balance": 2_750_000_000,
                            "timestamp": "2026-03-10T23:59:59Z",
                        }
                    ]
                }
            )

        if url.endswith("/api/transfer/v1"):
            page = int(params.get("page", 1))
            if page == 1:
                return _FakeResponse(
                    {
                        "data": [
                            {
                                "extrinsic_id": "xfer-in-1",
                                "to": {"ss58": self.wallet_address},
                                "from": {"ss58": "5OtherFrom"},
                                "subnet_uid": "1",
                                "amount": 2_000_000_000,
                                "timestamp": "2026-03-10T09:00:00Z",
                            }
                        ],
                        "pagination": {"next_page": 2},
                    }
                )
            if page == 2:
                return _FakeResponse(
                    {
                        "data": [
                            {
                                "extrinsic_hash": "xfer-out-1",
                                "to": {"ss58": "5OtherTo"},
                                "from": {"ss58": self.wallet_address},
                                "netuid": 3,
                                "amount": 1.5,
                                "timestamp": "2026-03-10T10:00:00Z",
                            },
                            {
                                "id": "xfer-skip",
                                "to": {"ss58": "5A"},
                                "from": {"ss58": "5B"},
                                "netuid": 4,
                                "amount": 999,
                                "timestamp": "2026-03-10T10:30:00Z",
                            },
                        ],
                        "pagination": {"next_page": None},
                    }
                )

        if url.endswith("/api/delegation/v1"):
            return _FakeResponse(
                {
                    "data": [
                        {
                            "extrinsic_id": "stake-1",
                            "action": "DELEGATE",
                            "subnet_uid": "1",
                            "alpha": 500_000_000,
                            "timestamp": "2026-03-10T11:00:00Z",
                        },
                        {
                            "id": "unstake-1",
                            "action": "UNDELEGATE",
                            "netuid": 2,
                            "amount": 250_000_000,
                            "timestamp": "2026-03-10T12:00:00Z",
                        },
                        {
                            "id": "unknown-1",
                            "action": "SOMETHING_ELSE",
                            "netuid": 5,
                            "amount": 125_000_000,
                            "timestamp": "2026-03-10T13:00:00Z",
                        },
                    ],
                    "pagination": {"next_page": None},
                }
            )

        if url.endswith("/api/call/v1"):
            full_name = params.get("full_name")
            if full_name and full_name != "SubtensorModule.add_stake_limit":
                return _FakeResponse({"data": [], "pagination": {"next_page": None}})
            return _FakeResponse(
                {
                    "data": [
                        {
                            "id": "trade-buy-1",
                            "full_name": "SubtensorModule.add_stake_limit",
                            "timestamp": "2026-03-10T14:00:00Z",
                            "args": {"netuid": "2", "amountStaked": 3_500_000_000, "limitPrice": 1_000_000_000},
                        },
                        {
                            "id": "not-a-swap",
                            "full_name": "Utility.batch_all",
                            "timestamp": "2026-03-10T14:30:00Z",
                            "args": {},
                        },
                    ],
                    "pagination": {"next_page": None},
                }
            )

        return _FakeResponse({"data": [], "pagination": {"next_page": None}})


class _ErrorSession:
    def __init__(self):
        self.headers: dict[str, str] = {}

    def get(self, url: str, params: dict | None = None, timeout: int | None = None):
        raise RuntimeError("HTTP 401 Unauthorized")


class TestTaostatsHttpAdapter(unittest.TestCase):
    def test_add_stake_limit_amount_converts_tao_to_alpha(self):
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        alpha = adapter._extract_trade_alpha_amount(
            direction="buy_alpha",
            full_name="SubtensorModule.add_stake_limit",
            args={"amountStaked": "2000000000", "limitPrice": "4000000"},
        )
        self.assertAlmostEqual(float(alpha), 500.0)

    def test_add_stake_limit_missing_limit_price_uses_zero_alpha_placeholder(self):
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        alpha = adapter._extract_trade_alpha_amount(
            direction="buy_alpha",
            full_name="SubtensorModule.add_stake_limit",
            args={"amountStaked": "2000000000"},
        )
        self.assertAlmostEqual(float(alpha), 0.0)

    def test_maps_snapshots_transfers_stake_history_and_trade_events(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        fake_session = _FakeSession(wallet_address=wallet)
        fake_session.headers.update(adapter.session.headers)
        adapter.session = fake_session

        run_date = date(2026, 3, 12)
        snapshots = adapter.fetch_snapshots(run_date, wallet)
        transfers = adapter.fetch_transfers(run_date, wallet)
        stake_events = adapter.fetch_stake_history(run_date, wallet)
        trade_events = adapter.fetch_trade_events(date(2026, 3, 10), wallet)

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].netuid, 1)
        self.assertAlmostEqual(snapshots[0].alpha_balance, 3.25)
        self.assertEqual(snapshots[1].netuid, 2)
        self.assertAlmostEqual(snapshots[1].alpha_balance, 4.25)

        self.assertEqual(len(transfers), 2)
        self.assertEqual(transfers[0].transfer_id, "xfer-in-1")
        self.assertEqual(transfers[0].direction, "in")
        self.assertAlmostEqual(transfers[0].alpha_amount, 2.0)
        self.assertEqual(transfers[1].transfer_id, "xfer-out-1")
        self.assertEqual(transfers[1].direction, "out")
        self.assertAlmostEqual(transfers[1].alpha_amount, 1.5)

        self.assertEqual(len(stake_events), 3)
        self.assertEqual(stake_events[0].action, "manual_stake")
        self.assertAlmostEqual(stake_events[0].alpha_amount, 0.5)
        self.assertEqual(stake_events[1].action, "manual_unstake")
        self.assertAlmostEqual(stake_events[1].alpha_amount, 0.25)
        self.assertEqual(stake_events[2].action, "manual_stake")
        self.assertAlmostEqual(stake_events[2].alpha_amount, 0.125)

        self.assertEqual(len(trade_events), 1)
        self.assertEqual(trade_events[0].trade_id, "trade-buy-1")
        self.assertEqual(trade_events[0].direction, "buy_alpha")
        self.assertEqual(trade_events[0].netuid, 2)
        self.assertAlmostEqual(trade_events[0].alpha_amount, 3.5)

        transfer_calls = [call for call in fake_session.calls if call[0].endswith("/api/transfer/v1")]
        self.assertEqual(len(transfer_calls), 2)
        self.assertEqual(transfer_calls[0][1].get("address"), wallet)
        self.assertIsNone(transfer_calls[0][1].get("nominator"))
        self.assertEqual(transfer_calls[0][1].get("page"), 1)
        self.assertEqual(transfer_calls[1][1].get("page"), 2)

        delegation_calls = [call for call in fake_session.calls if call[0].endswith("/api/delegation/v1")]
        self.assertGreaterEqual(len(delegation_calls), 1)
        self.assertEqual(delegation_calls[0][1].get("nominator"), wallet)
        self.assertIsNone(delegation_calls[0][1].get("address"))

        call_calls = [call for call in fake_session.calls if call[0].endswith("/api/call/v1")]
        self.assertGreaterEqual(len(call_calls), 1)
        self.assertEqual(call_calls[0][1].get("origin_address"), wallet)
        self.assertIsNone(call_calls[0][1].get("address"))

        self.assertEqual(adapter.session.headers.get("Authorization"), "test-key")

    def test_uses_alpha_balances_24hr_ago_for_yesterday_snapshots(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        fake_session = _FakeSession(wallet_address=wallet)
        fake_session.headers.update(adapter.session.headers)
        adapter.session = fake_session

        snapshots = adapter.fetch_snapshots(date(2026, 3, 11), wallet)

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].netuid, 1)
        self.assertAlmostEqual(snapshots[0].alpha_balance, 3.1)
        self.assertEqual(snapshots[1].netuid, 2)
        self.assertAlmostEqual(snapshots[1].alpha_balance, 4.0)

    def test_rejects_historical_backfill_for_older_dates(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        fake_session = _FakeSession(wallet_address=wallet)
        fake_session.headers.update(adapter.session.headers)
        adapter.session = fake_session

        with self.assertRaises(RuntimeError) as ctx:
            adapter.fetch_snapshots(date(2026, 3, 10), wallet)

        self.assertIn("Historical backfill is disabled", str(ctx.exception))
        history_calls = [call for call in fake_session.calls if call[0].endswith("/api/dtao/stake_balance/history/v1")]
        self.assertEqual(len(history_calls), 0)

    def test_fails_closed_when_http_calls_fail(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        adapter.session = _ErrorSession()

        run_date = date(2026, 3, 10)

        with self.assertRaises(RuntimeError):
            adapter.fetch_snapshots(run_date, wallet)
        with self.assertRaises(RuntimeError):
            adapter.fetch_transfers(run_date, wallet)
        with self.assertRaises(RuntimeError):
            adapter.fetch_stake_history(run_date, wallet)
        with self.assertRaises(RuntimeError):
            adapter.fetch_trade_events(run_date, wallet)


if __name__ == "__main__":
    unittest.main()
