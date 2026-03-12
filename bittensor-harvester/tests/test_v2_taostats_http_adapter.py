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

        return _FakeResponse({"data": [], "pagination": {"next_page": None}})


class _ErrorSession:
    def __init__(self):
        self.headers: dict[str, str] = {}

    def get(self, url: str, params: dict | None = None, timeout: int | None = None):
        raise RuntimeError("HTTP 401 Unauthorized")


class TestTaostatsHttpAdapter(unittest.TestCase):
    def test_maps_snapshots_transfers_and_stake_history(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        fake_session = _FakeSession(wallet_address=wallet)
        fake_session.headers.update(adapter.session.headers)
        adapter.session = fake_session

        run_date = date(2026, 3, 12)
        snapshots = adapter.fetch_snapshots(run_date, wallet)
        transfers = adapter.fetch_transfers(run_date, wallet)
        stake_events = adapter.fetch_stake_history(run_date, wallet)

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

        transfer_calls = [call for call in fake_session.calls if call[0].endswith("/api/transfer/v1")]
        self.assertEqual(len(transfer_calls), 2)
        self.assertEqual(transfer_calls[0][1].get("page"), 1)
        self.assertEqual(transfer_calls[1][1].get("page"), 2)

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

    def test_fetches_historical_snapshots_for_older_dates(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        fake_session = _FakeSession(wallet_address=wallet)
        fake_session.headers.update(adapter.session.headers)
        adapter.session = fake_session

        snapshots = adapter.fetch_snapshots(date(2026, 3, 10), wallet)

        self.assertEqual(len(snapshots), 2)
        self.assertTrue(all(s.alpha_balance == 2.75 for s in snapshots))
        history_calls = [call for call in fake_session.calls if call[0].endswith("/api/dtao/stake_balance/history/v1")]
        self.assertEqual(len(history_calls), 2)

    def test_returns_empty_lists_when_http_calls_fail(self):
        wallet = "5WalletForTest"
        adapter = TaostatsHttpAdapter(base_url="https://api.taostats.io", api_key="test-key", timeout_sec=15)
        adapter.session = _ErrorSession()

        run_date = date(2026, 3, 10)

        snapshots = adapter.fetch_snapshots(run_date, wallet)
        transfers = adapter.fetch_transfers(run_date, wallet)
        stake_events = adapter.fetch_stake_history(run_date, wallet)

        self.assertEqual(snapshots, [])
        self.assertEqual(transfers, [])
        self.assertEqual(stake_events, [])


if __name__ == "__main__":
    unittest.main()
