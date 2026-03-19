from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from v2.tao_harvester.adapters.taostats.http import TaostatsHttpAdapter
from v2.tao_harvester.adapters.taostats.mock import MockTaostatsAdapter
from v2.tao_harvester.config.app_config import AppConfig, parse_iso_date
from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.security.secrets import EnvSecretProvider
from v2.tao_harvester.workflows.daily_planner import DailyPlannerWorkflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TAO Harvester V2 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    planner = subparsers.add_parser("daily-planner", help="Run Tier 1 daily planner")
    planner.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default=today)")
    planner.add_argument("--dry-run", action="store_true", help="Dry-run planner mode")
    planner.add_argument("--source", choices=["mock", "taostats"], default="mock")
    planner.add_argument("--log-level", default="INFO")

    report = subparsers.add_parser("daily-report", help="Run daily earnings report and compute harvest amount")
    report.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default=yesterday UTC)")
    report.add_argument("--dry-run", action="store_true", help="Dry-run planner mode")
    report.add_argument("--source", choices=["mock", "taostats"], default="taostats")
    report.add_argument("--output", default=None, help="Optional output JSON path")
    report.add_argument(
        "--subnet-tao-threshold",
        type=float,
        default=0.0,
        help="Minimum per-subnet estimated_earned_tao included in harvestable totals",
    )
    report.add_argument("--log-level", default="INFO")
    return parser


def summarize_tao_harvest_steps(
    earnings_by_subnet: list[dict[str, float | int]],
    subnet_tao_threshold: float,
    harvest_fraction: float,
) -> dict[str, float | int]:
    estimated_earned_tao_all_subnets = 0.0
    harvestable_tao = 0.0
    eligible_estimated_alpha = 0.0
    eligible_subnet_count = 0

    for row in earnings_by_subnet:
        estimated_tao = float(row.get("estimated_earned_tao", 0.0) or 0.0)
        estimated_alpha = float(row.get("estimated_earned_alpha", 0.0) or 0.0)
        estimated_earned_tao_all_subnets += estimated_tao
        if estimated_tao >= subnet_tao_threshold:
            harvestable_tao += estimated_tao
            eligible_estimated_alpha += estimated_alpha
            eligible_subnet_count += 1

    alpha_to_harvest = eligible_estimated_alpha * harvest_fraction
    return {
        "threshold_tao": subnet_tao_threshold,
        "eligible_subnet_count": eligible_subnet_count,
        "estimated_earned_tao_all_subnets": estimated_earned_tao_all_subnets,
        "harvestable_tao": harvestable_tao,
        "alpha_to_harvest": alpha_to_harvest,
    }


def apply_subnet_threshold_fields(
    earnings_by_subnet: list[dict[str, float | int]],
    subnet_tao_threshold: float,
    harvest_fraction: float,
) -> list[dict[str, float | int | bool]]:
    output: list[dict[str, float | int | bool]] = []
    for row in earnings_by_subnet:
        est_tao = float(row.get("estimated_earned_tao", 0.0) or 0.0)
        est_alpha = float(row.get("estimated_earned_alpha", 0.0) or 0.0)
        meets_threshold = est_tao >= subnet_tao_threshold
        enriched = dict(row)
        enriched["meets_threshold"] = meets_threshold
        enriched["threshold_harvestable_tao"] = est_tao if meets_threshold else 0.0
        enriched["threshold_alpha_to_harvest"] = (est_alpha * harvest_fraction) if meets_threshold else 0.0
        output.append(enriched)
    return output


def resolve_run_date(command: str, date_arg: str | None, now_utc: datetime | None = None) -> date:
    if date_arg:
        return parse_iso_date(date_arg)
    if command == "daily-report":
        current_utc = now_utc or datetime.now(timezone.utc)
        return (current_utc.date() - timedelta(days=1))
    return parse_iso_date(None)


def validate_daily_report_date(run_date: date, now_utc: datetime | None = None) -> None:
    """
    Validate that daily-report is only run for recent dates (same-day UTC or yesterday UTC).
    
    Historical backfill (dates >2 days old) requires per-subnet API calls which violate the
    5 req/min rate limit. Reports should be run daily as part of automation, not manually
    for old dates.
    
    Args:
        run_date: The date being reported on
        now_utc: Current UTC time (for testing)
        
    Raises:
        ValueError: If run_date is more than 1 day in the past
    """
    current_utc = now_utc or datetime.now(timezone.utc)
    current_date = current_utc.date()
    days_old = (current_date - run_date).days
    
    if days_old > 1:
        raise ValueError(
            f"daily-report can only run for recent dates (same-day or yesterday UTC). "
            f"Requested date {run_date.isoformat()} is {days_old} days old. "
            f"Historical backfill requires per-subnet API calls that exceed the 5 req/min rate limit. "
            f"Run daily-report as part of daily automation instead."
        )


def main() -> int:
    load_dotenv(override=True)
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    config = AppConfig.from_env()
    run_date = resolve_run_date(args.command, args.date)

    if args.command == "daily-report" and args.subnet_tao_threshold < 0:
        raise ValueError("--subnet-tao-threshold must be >= 0")
    
    if args.command == "daily-report":
        validate_daily_report_date(run_date)
    
    dry_run = True if args.dry_run else config.default_dry_run

    if not config.harvester_address:
        raise ValueError("HARVESTER_WALLET_ADDRESS must be set")

    repository = SQLiteRepository(config.db_path)
    try:
        schema_path = Path(__file__).resolve().parent / "db" / "schema.sql"
        repository.init_schema(str(schema_path))

        if args.source == "mock":
            ingestion = MockTaostatsAdapter()
        else:
            secret_provider = EnvSecretProvider()
            api_key = secret_provider.get("TAOSTATS_API_KEY")
            ingestion = TaostatsHttpAdapter(base_url=config.taostats_base_url, api_key=api_key)

        workflow = DailyPlannerWorkflow(repository=repository, ingestion=ingestion, config=config)
        result = workflow.run(run_date=run_date, dry_run=dry_run)

        if args.command == "daily-report":
            base_earnings_by_subnet = repository.get_daily_earnings_by_subnet_with_tao(
                run_date,
                config.harvester_address,
                config.rules.harvest_fraction,
            )
            summary = summarize_tao_harvest_steps(
                earnings_by_subnet=base_earnings_by_subnet,
                subnet_tao_threshold=args.subnet_tao_threshold,
                harvest_fraction=config.rules.harvest_fraction,
            )
            earnings_by_subnet = apply_subnet_threshold_fields(
                earnings_by_subnet=base_earnings_by_subnet,
                subnet_tao_threshold=args.subnet_tao_threshold,
                harvest_fraction=config.rules.harvest_fraction,
            )
            estimated_earned_tao = float(summary["estimated_earned_tao_all_subnets"])
            harvestable_tao = float(summary["harvestable_tao"])
            alpha_to_harvest = float(summary["alpha_to_harvest"])
            report = {
                "report_date": run_date.isoformat(),
                "source": args.source,
                "dry_run": dry_run,
                "wallet_address": config.harvester_address,
                "units": {
                    "accounting_base": "alpha",
                    "reconciliation": "alpha_only",
                    "tao_values": "estimates_only",
                    "conversion_note": "TAO values are derived from per-subnet tao_per_alpha and used for planning/preview only.",
                },
                "run_id": result.run_id,
                "snapshot_count": result.snapshot_count,
                "reconciliation_count": result.reconciliation_count,
                "estimated_earned_alpha": result.total_estimated_earned_alpha,
                "estimated_earned_tao": estimated_earned_tao,
                "harvestable_tao": harvestable_tao,
                "alpha_to_harvest": alpha_to_harvest,
                "threshold_tao": float(summary["threshold_tao"]),
                "eligible_subnet_count": int(summary["eligible_subnet_count"]),
                "earnings_by_subnet": earnings_by_subnet,
                "planned_harvest_alpha": result.planned_harvest_alpha,
                "planned_harvest_tao": min(
                    harvestable_tao * config.rules.harvest_fraction,
                    config.rules.max_harvest_tao_per_run,
                ),
                "transfer_batch_created": result.transfer_batch_created,
            }

            output_path = args.output or f"reports/v2_daily_report_{run_date.isoformat()}.json"
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

            print("daily-report complete")
            print(f"report_path={output_file.as_posix()}")
            print(f"estimated_earned_alpha={result.total_estimated_earned_alpha:.6f}")
            print(f"estimated_earned_tao={estimated_earned_tao:.9f}")
            print(f"planned_harvest_alpha={result.planned_harvest_alpha:.6f}")
            return 0

        print("daily-planner complete")
        print(f"run_id={result.run_id}")
        print(f"snapshot_count={result.snapshot_count}")
        print(f"reconciliation_count={result.reconciliation_count}")
        print(f"total_estimated_earned_alpha={result.total_estimated_earned_alpha:.6f}")
        print(f"planned_harvest_alpha={result.planned_harvest_alpha:.6f}")
        print(f"transfer_batch_created={result.transfer_batch_created}")
        return 0
    finally:
        repository.close()


if __name__ == "__main__":
    raise SystemExit(main())
