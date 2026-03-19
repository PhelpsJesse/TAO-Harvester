from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from v2.tao_harvester.adapters.taostats.http import TaostatsHttpAdapter
from v2.tao_harvester.adapters.taostats.mock import MockTaostatsAdapter
from v2.tao_harvester.config.app_config import AppConfig, parse_iso_date
from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.security.secrets import EnvSecretProvider
from v2.tao_harvester.workflows.daily_planner import DailyPlannerWorkflow


@dataclass(frozen=True)
class HarvestCalculationSummary:
    threshold_tao: float
    eligible_subnet_count: int
    estimated_earned_tao_all_subnets: float
    harvestable_tao: float
    alpha_to_harvest: float


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate harvest intents for next-stage execution")
    parser.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default=today)")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode")
    parser.add_argument("--source", choices=["mock", "taostats"], default="taostats")
    parser.add_argument(
        "--subnet-tao-threshold",
        type=float,
        default=0.0,
        help="Minimum per-subnet estimated_earned_tao included for execution handoff",
    )
    parser.add_argument("--output", default=None, help="Optional output JSON path")
    parser.add_argument("--log-level", default="INFO")
    return parser


def summarize_harvest(
    earnings_by_subnet: list[dict[str, float | int]],
    subnet_tao_threshold: float,
    harvest_fraction: float,
) -> HarvestCalculationSummary:
    est_all = 0.0
    harvestable_tao = 0.0
    eligible_alpha = 0.0
    eligible_subnet_count = 0
    for row in earnings_by_subnet:
        est_tao = float(row.get("estimated_earned_tao", 0.0) or 0.0)
        est_alpha = float(row.get("estimated_earned_alpha", 0.0) or 0.0)
        est_all += est_tao
        if est_tao >= subnet_tao_threshold:
            harvestable_tao += est_tao
            eligible_alpha += est_alpha
            eligible_subnet_count += 1
    return HarvestCalculationSummary(
        threshold_tao=subnet_tao_threshold,
        eligible_subnet_count=eligible_subnet_count,
        estimated_earned_tao_all_subnets=est_all,
        harvestable_tao=harvestable_tao,
        alpha_to_harvest=eligible_alpha * harvest_fraction,
    )


def build_execution_handoff_subnets(
    earnings_by_subnet: list[dict[str, float | int]],
    subnet_tao_threshold: float,
    harvest_fraction: float,
) -> list[dict[str, float | int]]:
    handoff_rows: list[dict[str, float | int]] = []
    for row in earnings_by_subnet:
        estimated_tao = float(row.get("estimated_earned_tao", 0.0) or 0.0)
        if estimated_tao < subnet_tao_threshold:
            continue
        estimated_alpha = float(row.get("estimated_earned_alpha", 0.0) or 0.0)
        alpha_to_harvest = estimated_alpha * harvest_fraction
        handoff_rows.append(
            {
                "netuid": int(row.get("netuid", 0) or 0),
                "alpha_to_harvest": alpha_to_harvest,
                "estimated_tao_out": estimated_tao,
                "tao_per_alpha": float(row.get("tao_per_alpha", 0.0) or 0.0),
            }
        )
    handoff_rows.sort(key=lambda item: float(item["estimated_tao_out"]), reverse=True)
    return handoff_rows


def build_handoff_payload(
    run_date: date,
    wallet_address: str,
    dry_run: bool,
    run_id: int,
    snapshot_count: int,
    reconciliation_count: int,
    estimated_earned_alpha: float,
    summary: HarvestCalculationSummary,
    execution_subnets: list[dict[str, float | int]],
) -> dict[str, object]:
    return {
        "module": "calculate_harvest",
        "report_date": run_date.isoformat(),
        "wallet_address": wallet_address,
        "dry_run": dry_run,
        "run_id": run_id,
        "snapshot_count": snapshot_count,
        "reconciliation_count": reconciliation_count,
        "units": {
            "accounting_base": "alpha",
            "tao_values": "estimates_only",
            "threshold_basis": "per_subnet_estimated_earned_tao",
        },
        "totals": {
            "estimated_earned_alpha": estimated_earned_alpha,
            "estimated_earned_tao_all_subnets": summary.estimated_earned_tao_all_subnets,
            "harvestable_tao_threshold_applied": summary.harvestable_tao,
            "alpha_to_harvest_threshold_applied": summary.alpha_to_harvest,
            "threshold_tao": summary.threshold_tao,
            "eligible_subnet_count": summary.eligible_subnet_count,
        },
        "execution_handoff": {
            "target": "opentensor_swap_alpha_to_tao",
            "status": "intent_only",
            "subnets": execution_subnets,
        },
    }


def main() -> int:
    load_dotenv(override=True)
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    if args.subnet_tao_threshold < 0:
        raise ValueError("--subnet-tao-threshold must be >= 0")

    config = AppConfig.from_env()
    run_date = parse_iso_date(args.date)
    dry_run = True if args.dry_run else config.default_dry_run

    if not config.harvester_address:
        raise ValueError("HARVESTER_WALLET_ADDRESS must be set")

    repository = SQLiteRepository(config.db_path)
    try:
        schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
        repository.init_schema(str(schema_path))

        if args.source == "mock":
            ingestion = MockTaostatsAdapter()
        else:
            secret_provider = EnvSecretProvider()
            api_key = secret_provider.get("TAOSTATS_API_KEY")
            ingestion = TaostatsHttpAdapter(base_url=config.taostats_base_url, api_key=api_key)

        workflow = DailyPlannerWorkflow(repository=repository, ingestion=ingestion, config=config)
        result = workflow.run(run_date=run_date, dry_run=dry_run)

        earnings_by_subnet = repository.get_daily_earnings_by_subnet_with_tao(
            run_date,
            config.harvester_address,
            config.rules.harvest_fraction,
        )
        summary = summarize_harvest(
            earnings_by_subnet=earnings_by_subnet,
            subnet_tao_threshold=args.subnet_tao_threshold,
            harvest_fraction=config.rules.harvest_fraction,
        )
        execution_subnets = build_execution_handoff_subnets(
            earnings_by_subnet=earnings_by_subnet,
            subnet_tao_threshold=args.subnet_tao_threshold,
            harvest_fraction=config.rules.harvest_fraction,
        )
        payload = build_handoff_payload(
            run_date=run_date,
            wallet_address=config.harvester_address,
            dry_run=dry_run,
            run_id=result.run_id,
            snapshot_count=result.snapshot_count,
            reconciliation_count=result.reconciliation_count,
            estimated_earned_alpha=result.total_estimated_earned_alpha,
            summary=summary,
            execution_subnets=execution_subnets,
        )

        output_path = args.output or f"reports/v2_calculate_harvest_{run_date.isoformat()}.json"
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        print("calculate-harvest complete")
        print(f"report_path={output_file.as_posix()}")
        print(f"estimated_earned_tao_all_subnets={summary.estimated_earned_tao_all_subnets:.9f}")
        print(f"harvestable_tao={summary.harvestable_tao:.9f}")
        print(f"alpha_to_harvest={summary.alpha_to_harvest:.6f}")
        print(f"eligible_subnet_count={summary.eligible_subnet_count}")
        return 0
    finally:
        repository.close()


if __name__ == "__main__":
    raise SystemExit(main())