import unittest
from typing import cast
from unittest.mock import patch

from v2.tao_harvester.modules.opentensor_staking_foundation import (
    REQUIRED_EXECUTION_CONFIRMATION,
    build_staker_for_execution,
    build_unstake_requests,
    require_openclaw_db_sync_for_execution,
    run_staking_requests_with_verification,
    run_staking_requests,
    validate_execution_confirmation,
)
from v2.tao_harvester.config.app_config import AppConfig
from v2.tao_harvester.services.execution_interfaces import (
    AlphaStakeAction,
    AlphaStakeRequest,
    AlphaStakeResult,
    NoopOpenTensorStaker,
    OpenTensorStakingPort,
)


class _FakeVerifier:
    def __init__(self, balance_maps):
        self.balance_maps = list(balance_maps)
        self.calls = 0

    def fetch_balance_map(self):
        index = min(self.calls, len(self.balance_maps) - 1)
        self.calls += 1
        return dict(self.balance_maps[index])


class _AcceptingStaker(OpenTensorStakingPort):
    def submit_alpha_stake(self, request: AlphaStakeRequest) -> AlphaStakeResult:
        return AlphaStakeResult(
            accepted=True,
            tx_hash="0xabc",
            status="submitted",
            reason=f"submitted netuid={request.netuid}",
        )


class TestOpenTensorStakingFoundation(unittest.TestCase):
    def test_build_unstake_requests_filters_invalid_rows(self):
        payload = {
            "execution_handoff": {
                "subnets": [
                    {"netuid": 1, "alpha_to_harvest": 4.5},
                    {"netuid": 2, "alpha_to_harvest": 0.0},
                    {"netuid": 0, "alpha_to_harvest": 1.0},
                ]
            }
        }

        requests = build_unstake_requests(payload)

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].netuid, 1)
        self.assertEqual(requests[0].action, AlphaStakeAction.UNSTAKE)
        self.assertAlmostEqual(requests[0].alpha_amount, 4.5)

    def test_validate_execution_confirmation_requires_exact_token(self):
        with self.assertRaises(ValueError):
            validate_execution_confirmation(execute=True, confirmation="wrong")

        validate_execution_confirmation(execute=True, confirmation=REQUIRED_EXECUTION_CONFIRMATION)

    def test_noop_staker_is_fail_closed(self):
        staker = NoopOpenTensorStaker()
        requests = [
            AlphaStakeRequest(
                netuid=1,
                alpha_amount=2.0,
                action=AlphaStakeAction.UNSTAKE,
                note="test",
            )
        ]

        results = run_staking_requests(requests=requests, execute=True, staker=staker)

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].accepted)
        self.assertEqual(results[0].status, "not_implemented")

    def test_execute_mode_records_pre_post_taostats_verification(self):
        requests = [
            AlphaStakeRequest(
                netuid=118,
                alpha_amount=2.0,
                action=AlphaStakeAction.UNSTAKE,
                note="test",
            )
        ]
        verifier = _FakeVerifier([
            {118: 10.0, 60: 3.0},
            {118: 8.0, 60: 3.0},
        ])

        attempts = run_staking_requests_with_verification(
            requests=requests,
            execute=True,
            staker=_AcceptingStaker(),
            verifier=verifier,
        )

        self.assertEqual(len(attempts), 1)
        verification = cast(dict[str, object], attempts[0]["verification"])
        self.assertEqual(verification["verification_source"], "taostats_account_latest")
        self.assertAlmostEqual(float(cast(float, verification["before_alpha_balance"])), 10.0)
        self.assertAlmostEqual(float(cast(float, verification["after_alpha_balance"])), 8.0)
        self.assertAlmostEqual(float(cast(float, verification["target_delta_alpha"])), -2.0)
        self.assertEqual(verification["changed_netuids"], [118])
        self.assertTrue(verification["unexpected_change_detected"])
        self.assertEqual(verifier.calls, 2)

    def test_intent_only_mode_skips_taostats_verification(self):
        requests = [
            AlphaStakeRequest(
                netuid=118,
                alpha_amount=2.0,
                action=AlphaStakeAction.UNSTAKE,
                note="test",
            )
        ]
        verifier = _FakeVerifier([{118: 10.0}])

        attempts = run_staking_requests_with_verification(
            requests=requests,
            execute=False,
            staker=NoopOpenTensorStaker(),
            verifier=verifier,
        )

        verification = cast(dict[str, object], attempts[0]["verification"])
        self.assertEqual(verification["status"], "not_run")
        self.assertEqual(verifier.calls, 0)

    @patch("v2.tao_harvester.modules.opentensor_staking_foundation.validate_local_db")
    @patch("v2.tao_harvester.modules.opentensor_staking_foundation.fetch_remote_db")
    def test_execute_mode_requires_openclaw_db_sync(self, mock_fetch, mock_validate):
        config = AppConfig.from_env()
        mock_validate.return_value = {"validation": "ok", "latest_reconciliation_date": "2026-03-26"}

        report = require_openclaw_db_sync_for_execution(
            execute=True,
            config=config,
            skip_fetch=False,
            expected_db_date="2026-03-26",
            max_db_staleness_days=1,
            min_db_snapshots=1,
            min_db_reconciliations=1,
        )

        self.assertEqual(cast(str, report["validation"]), "ok")
        mock_fetch.assert_called_once_with(config)
        mock_validate.assert_called_once()

    @patch("v2.tao_harvester.modules.opentensor_staking_foundation.validate_local_db")
    @patch("v2.tao_harvester.modules.opentensor_staking_foundation.fetch_remote_db")
    def test_skip_fetch_uses_existing_local_db_copy(self, mock_fetch, mock_validate):
        config = AppConfig.from_env()
        mock_validate.return_value = {"validation": "ok"}

        require_openclaw_db_sync_for_execution(
            execute=True,
            config=config,
            skip_fetch=True,
            expected_db_date="2026-03-26",
            max_db_staleness_days=1,
            min_db_snapshots=1,
            min_db_reconciliations=1,
        )

        mock_fetch.assert_not_called()
        mock_validate.assert_called_once()

    def test_build_staker_backend_defaults_to_noop(self):
        config = AppConfig.from_env()
        staker = build_staker_for_execution(config)
        self.assertIsInstance(staker, NoopOpenTensorStaker)

    def test_build_staker_backend_rejects_unknown_backend(self):
        base = AppConfig.from_env()
        custom = AppConfig(
            db_path=base.db_path,
            taostats_base_url=base.taostats_base_url,
            harvester_address=base.harvester_address,
            kraken_deposit_whitelist=base.kraken_deposit_whitelist,
            rules=base.rules,
            openclaw_handoff=base.openclaw_handoff,
            opentensor_staker_backend="bogus",
            opentensor_network=base.opentensor_network,
            opentensor_wallet_name=base.opentensor_wallet_name,
            opentensor_wallet_hotkey=base.opentensor_wallet_hotkey,
            default_dry_run=base.default_dry_run,
            catchup_missed_days=base.catchup_missed_days,
        )

        with self.assertRaises(ValueError):
            build_staker_for_execution(custom)


if __name__ == "__main__":
    unittest.main()
