from __future__ import annotations

import argparse
import json
import logging
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
    report.add_argument("--date", default=None, help="Run date YYYY-MM-DD (default=today)")
    report.add_argument("--dry-run", action="store_true", help="Dry-run planner mode")
    report.add_argument("--source", choices=["mock", "taostats"], default="taostats")
    report.add_argument("--output", default=None, help="Optional output JSON path")
    report.add_argument("--log-level", default="INFO")
    return parser


def main() -> int:
    load_dotenv(override=True)
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    config = AppConfig.from_env()
    run_date = parse_iso_date(args.date)
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
            earnings_by_subnet = repository.get_daily_earnings_by_subnet(run_date, config.harvester_address)
            report = {
                "report_date": run_date.isoformat(),
                "source": args.source,
                "dry_run": dry_run,
                "wallet_address": config.harvester_address,
                "run_id": result.run_id,
                "snapshot_count": result.snapshot_count,
                "reconciliation_count": result.reconciliation_count,
                "estimated_earned_alpha": result.total_estimated_earned_alpha,
                "earnings_by_subnet": earnings_by_subnet,
                "planned_harvest_alpha": result.planned_harvest_alpha,
                "transfer_batch_created": result.transfer_batch_created,
            }

            output_path = args.output or f"reports/v2_daily_report_{run_date.isoformat()}.json"
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

            print("daily-report complete")
            print(f"report_path={output_file.as_posix()}")
            print(f"estimated_earned_alpha={result.total_estimated_earned_alpha:.6f}")
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
