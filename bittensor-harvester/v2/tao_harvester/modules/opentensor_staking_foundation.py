from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol

from dotenv import load_dotenv

from v2.tao_harvester.adapters.taostats.http import TaostatsHttpAdapter
from v2.tao_harvester.config.app_config import AppConfig
from v2.tao_harvester.modules.sync_openclaw_db import fetch_remote_db, validate_local_db
from v2.tao_harvester.security.secrets import EnvSecretProvider
from v2.tao_harvester.services.execution_interfaces import (
    AlphaStakeAction,
    AlphaStakeRequest,
    AlphaStakeResult,
    NoopOpenTensorStaker,
    OpenTensorStakingPort,
)

REQUIRED_EXECUTION_CONFIRMATION = "I_UNDERSTAND_EXECUTION_RISK"


class StakeStateVerifierPort(Protocol):
    def fetch_balance_map(self) -> dict[int, float]: ...


class TaostatsStakeStateVerifier:
    def __init__(self, wallet_address: str, adapter: TaostatsHttpAdapter):
        self.wallet_address = wallet_address
        self.adapter = adapter

    def fetch_balance_map(self) -> dict[int, float]:
        snapshots = self.adapter.fetch_snapshots(date.today(), self.wallet_address)
        return {snapshot.netuid: snapshot.alpha_balance for snapshot in snapshots}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare OpenTensor alpha staking transaction intents")
    parser.add_argument("--input", required=True, help="Path to calculate_harvest output JSON")
    parser.add_argument("--output", default=None, help="Optional output JSON path")
    parser.add_argument("--execute", action="store_true", help="Attempt execution (disabled by default)")
    parser.add_argument(
        "--confirm-execution",
        default=None,
        help=f"Required when --execute is set. Must equal {REQUIRED_EXECUTION_CONFIRMATION}",
    )
    parser.add_argument("--skip-db-sync-fetch", action="store_true", help="Use existing local OpenClaw DB copy")
    parser.add_argument("--expected-db-date", default=None, help="Require DB freshness for YYYY-MM-DD")
    parser.add_argument(
        "--max-db-staleness-days",
        type=int,
        default=1,
        help="Maximum allowed DB lag in days (default=1)",
    )
    parser.add_argument("--min-db-snapshots", type=int, default=1, help="Minimum snapshots on latest DB date")
    parser.add_argument(
        "--min-db-reconciliations",
        type=int,
        default=1,
        help="Minimum reconciliations on latest DB date",
    )
    return parser


def validate_execution_confirmation(execute: bool, confirmation: str | None) -> None:
    if not execute:
        return
    if confirmation != REQUIRED_EXECUTION_CONFIRMATION:
        raise ValueError(
            "execution confirmation mismatch: --execute requires "
            f"--confirm-execution {REQUIRED_EXECUTION_CONFIRMATION}"
        )


def _parse_handoff_subnets(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    execution_handoff = payload.get("execution_handoff")
    if not isinstance(execution_handoff, dict):
        raise ValueError("invalid input: missing execution_handoff object")
    subnets = execution_handoff.get("subnets")
    if not isinstance(subnets, list):
        raise ValueError("invalid input: missing execution_handoff.subnets list")
    return [row for row in subnets if isinstance(row, dict)]


def build_unstake_requests(payload: Mapping[str, Any]) -> list[AlphaStakeRequest]:
    requests: list[AlphaStakeRequest] = []
    for row in _parse_handoff_subnets(payload):
        netuid = int(row.get("netuid", 0) or 0)
        alpha_to_harvest = float(row.get("alpha_to_harvest", 0.0) or 0.0)
        if netuid <= 0 or alpha_to_harvest <= 0:
            continue
        requests.append(
            AlphaStakeRequest(
                netuid=netuid,
                alpha_amount=alpha_to_harvest,
                action=AlphaStakeAction.UNSTAKE,
                note="Generated from calculate_harvest execution_handoff",
            )
        )
    return requests


def run_staking_requests(
    requests: list[AlphaStakeRequest],
    execute: bool,
    staker: OpenTensorStakingPort,
) -> list[AlphaStakeResult]:
    if not execute:
        return [
            AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="intent_only",
                reason="Execution disabled; intent payload generated only",
            )
            for _ in requests
        ]
    return [staker.submit_alpha_stake(request) for request in requests]


def build_stake_verification(
    request: AlphaStakeRequest,
    before_balances: Mapping[int, float],
    after_balances: Mapping[int, float],
) -> dict[str, object]:
    changed_netuids = sorted(
        {
            netuid
            for netuid in set(before_balances) | set(after_balances)
            if abs(before_balances.get(netuid, 0.0) - after_balances.get(netuid, 0.0)) > 1e-12
        }
    )
    before_target = float(before_balances.get(request.netuid, 0.0))
    after_target = float(after_balances.get(request.netuid, 0.0))
    return {
        "verification_source": "taostats_account_latest",
        "target_netuid": request.netuid,
        "before_alpha_balance": before_target,
        "after_alpha_balance": after_target,
        "target_delta_alpha": after_target - before_target,
        "changed_netuids": changed_netuids,
        "unexpected_change_detected": len(changed_netuids) > 0,
    }


def run_staking_requests_with_verification(
    requests: list[AlphaStakeRequest],
    execute: bool,
    staker: OpenTensorStakingPort,
    verifier: StakeStateVerifierPort | None,
) -> list[dict[str, object]]:
    attempts: list[dict[str, object]] = []
    if not execute:
        for request in requests:
            attempts.append(
                {
                    "request": {
                        "netuid": request.netuid,
                        "alpha_amount": request.alpha_amount,
                        "action": request.action.value,
                        "note": request.note,
                    },
                    "result": asdict(
                        AlphaStakeResult(
                            accepted=False,
                            tx_hash=None,
                            status="intent_only",
                            reason="Execution disabled; intent payload generated only",
                        )
                    ),
                    "verification": {
                        "verification_source": "taostats_account_latest",
                        "status": "not_run",
                        "reason": "Verification only runs when execution is requested",
                    },
                }
            )
        return attempts

    if verifier is None:
        raise ValueError("execution requires a Taostats verifier")

    for request in requests:
        before_balances = verifier.fetch_balance_map()
        result = staker.submit_alpha_stake(request)
        after_balances = verifier.fetch_balance_map()
        attempts.append(
            {
                "request": {
                    "netuid": request.netuid,
                    "alpha_amount": request.alpha_amount,
                    "action": request.action.value,
                    "note": request.note,
                },
                "result": asdict(result),
                "verification": build_stake_verification(request, before_balances, after_balances),
            }
        )
    return attempts


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def require_openclaw_db_sync_for_execution(
    execute: bool,
    config: AppConfig,
    *,
    skip_fetch: bool,
    expected_db_date: str | None,
    max_db_staleness_days: int,
    min_db_snapshots: int,
    min_db_reconciliations: int,
) -> dict[str, object] | None:
    if not execute:
        return None

    if not skip_fetch:
        fetch_remote_db(config)

    report = validate_local_db(
        db_path=config.openclaw_handoff.local_db_path,
        expected_date=_parse_iso_date(expected_db_date),
        max_staleness_days=max_db_staleness_days,
        min_snapshots=min_db_snapshots,
        min_reconciliations=min_db_reconciliations,
    )
    if str(report.get("validation", "")) != "ok":
        raise ValueError("OpenClaw DB validation failed")
    return report


def build_output_payload(
    input_path: str,
    report_date: str,
    execute: bool,
    requests: list[AlphaStakeRequest],
    results: list[AlphaStakeResult],
    attempts: list[dict[str, object]] | None = None,
    db_sync_report: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "module": "opentensor_staking_foundation",
        "report_date": report_date,
        "source_input": input_path,
        "execution_mode": "execute" if execute else "intent_only",
        "request_count": len(requests),
        "requests": [
            {
                "netuid": request.netuid,
                "alpha_amount": request.alpha_amount,
                "action": request.action.value,
                "note": request.note,
            }
            for request in requests
        ],
        "results": [asdict(result) for result in results],
        "attempts": attempts or [],
        "db_sync_report": db_sync_report,
    }


def main() -> int:
    load_dotenv(override=True)
    parser = build_parser()
    args = parser.parse_args()

    validate_execution_confirmation(args.execute, args.confirm_execution)

    input_path = Path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    report_date = str(payload.get("report_date") or "unknown")

    requests = build_unstake_requests(payload)
    staker = NoopOpenTensorStaker()
    results = run_staking_requests(requests, execute=args.execute, staker=staker)
    verifier: StakeStateVerifierPort | None = None
    db_sync_report: dict[str, object] | None = None
    if args.execute:
        config = AppConfig.from_env()
        expected_db_date = args.expected_db_date or (report_date if report_date != "unknown" else None)
        db_sync_report = require_openclaw_db_sync_for_execution(
            execute=args.execute,
            config=config,
            skip_fetch=args.skip_db_sync_fetch,
            expected_db_date=expected_db_date,
            max_db_staleness_days=args.max_db_staleness_days,
            min_db_snapshots=args.min_db_snapshots,
            min_db_reconciliations=args.min_db_reconciliations,
        )
        if not config.harvester_address:
            raise ValueError("HARVESTER_WALLET_ADDRESS must be set for execution verification")
        api_key = EnvSecretProvider().get("TAOSTATS_API_KEY")
        verifier = TaostatsStakeStateVerifier(
            wallet_address=config.harvester_address,
            adapter=TaostatsHttpAdapter(base_url=config.taostats_base_url, api_key=api_key),
        )
    attempts = run_staking_requests_with_verification(
        requests=requests,
        execute=args.execute,
        staker=staker,
        verifier=verifier,
    )

    output_path = args.output or f"reports/v2_opentensor_staking_foundation_{report_date}.json"
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_payload = build_output_payload(
        input_path=input_path.as_posix(),
        report_date=report_date,
        execute=args.execute,
        requests=requests,
        results=results,
        attempts=attempts,
        db_sync_report=db_sync_report,
    )
    output_file.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print("opentensor-staking-foundation complete")
    print(f"output_path={output_file.as_posix()}")
    print(f"request_count={len(requests)}")
    print(f"execution_mode={output_payload['execution_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
