from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from v2.tao_harvester.config.app_config import AppConfig, parse_iso_date

REQUIRED_TABLES = {
    "runs",
    "run_stages",
    "snapshots",
    "transfer_events",
    "stake_history_events",
    "trade_events",
    "reconciliations",
    "harvest_plans",
    "transfer_batches",
    "audit_events",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pull and validate latest OpenClaw SQLite DB")
    parser.add_argument("--skip-fetch", action="store_true", help="Validate existing local DB only")
    parser.add_argument("--expected-date", default=None, help="Require reconciliation data for YYYY-MM-DD")
    parser.add_argument(
        "--max-staleness-days",
        type=int,
        default=1,
        help="Maximum allowed lag in days between expected date and latest reconciliation date",
    )
    parser.add_argument(
        "--min-snapshots",
        type=int,
        default=1,
        help="Minimum snapshots required on latest reconciliation date",
    )
    parser.add_argument(
        "--min-reconciliations",
        type=int,
        default=1,
        help="Minimum reconciliations required on latest reconciliation date",
    )
    return parser


def build_scp_command(config: AppConfig) -> list[str]:
    handoff = config.openclaw_handoff
    return [
        "scp",
        "-i",
        handoff.ssh_key_path,
        "-P",
        str(handoff.ssh_port),
        f"{handoff.ssh_user}@{handoff.ssh_host}:{handoff.remote_db_path}",
        handoff.local_db_path,
    ]


def fetch_remote_db(config: AppConfig) -> None:
    handoff = config.openclaw_handoff
    if not handoff.configured:
        raise ValueError(
            "OpenClaw SSH settings are incomplete. Set OPENCLAW_SSH_HOST, OPENCLAW_SSH_USER, and OPENCLAW_SSH_KEY_PATH."
        )

    if shutil.which("scp") is None:
        raise RuntimeError("scp command not found on local machine")

    target = Path(handoff.local_db_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    command = build_scp_command(config)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "failed to fetch OpenClaw DB via scp: "
            f"code={result.returncode}, stderr={result.stderr.strip()}"
        )


def _query_int(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if not row:
        return 0
    value = row[0]
    return int(value or 0)


def validate_local_db(
    db_path: str,
    expected_date: date | None,
    max_staleness_days: int,
    min_snapshots: int,
    min_reconciliations: int,
) -> dict[str, object]:
    db_file = Path(db_path)
    if not db_file.exists():
        raise ValueError(f"local OpenClaw DB not found: {db_path}")

    conn = sqlite3.connect(str(db_file))
    try:
        table_rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {str(row[0]) for row in table_rows}
        missing_tables = sorted(REQUIRED_TABLES - table_names)
        if missing_tables:
            raise ValueError(f"database missing required tables: {missing_tables}")

        raw_latest = conn.execute("SELECT MAX(reconciliation_date) FROM reconciliations").fetchone()[0]
        if not raw_latest:
            raise ValueError("database has no reconciliation rows")

        latest_recon_date = date.fromisoformat(str(raw_latest))
        target_date = expected_date or datetime.now(timezone.utc).date()
        lag_days = (target_date - latest_recon_date).days
        if lag_days < 0:
            lag_days = 0

        if lag_days > max_staleness_days:
            raise ValueError(
                f"database is stale: latest_reconciliation_date={latest_recon_date.isoformat()}, "
                f"expected_date={target_date.isoformat()}, lag_days={lag_days}, allowed={max_staleness_days}"
            )

        snapshot_count = _query_int(
            conn,
            "SELECT COUNT(*) FROM snapshots WHERE snapshot_date = ?",
            (latest_recon_date.isoformat(),),
        )
        recon_count = _query_int(
            conn,
            "SELECT COUNT(*) FROM reconciliations WHERE reconciliation_date = ?",
            (latest_recon_date.isoformat(),),
        )
        if snapshot_count < min_snapshots:
            raise ValueError(
                f"insufficient snapshots for latest date {latest_recon_date.isoformat()}: "
                f"found={snapshot_count}, required={min_snapshots}"
            )
        if recon_count < min_reconciliations:
            raise ValueError(
                f"insufficient reconciliations for latest date {latest_recon_date.isoformat()}: "
                f"found={recon_count}, required={min_reconciliations}"
            )

        negative_anomalies = _query_int(
            conn,
            """
            SELECT COUNT(*)
            FROM reconciliations
            WHERE reconciliation_date = ?
              AND (gross_growth_alpha - net_trade_adjustment_alpha - net_transfers_alpha) < 0
            """,
            (latest_recon_date.isoformat(),),
        )

        last_run = conn.execute(
            """
            SELECT run_date, status, completed_at, error_message
            FROM runs
            WHERE workflow_name = 'daily_planner'
            ORDER BY run_date DESC, started_at DESC
            LIMIT 1
            """
        ).fetchone()
        if not last_run:
            raise ValueError("database has no daily_planner run rows")

        run_status = str(last_run[1] or "")
        if run_status not in {"completed", "manual_intervention_required"}:
            raise ValueError(f"latest daily_planner run is not healthy: status={run_status}")

        return {
            "db_path": str(db_file),
            "latest_reconciliation_date": latest_recon_date.isoformat(),
            "expected_date": target_date.isoformat(),
            "lag_days": lag_days,
            "snapshot_count": snapshot_count,
            "reconciliation_count": recon_count,
            "negative_anomaly_count": negative_anomalies,
            "latest_run_status": run_status,
            "latest_run_date": str(last_run[0]),
            "latest_run_completed_at": str(last_run[2] or ""),
            "latest_run_error": str(last_run[3] or ""),
            "validation": "ok",
        }
    finally:
        conn.close()


def main() -> int:
    load_dotenv(override=True)
    args = build_parser().parse_args()
    config = AppConfig.from_env()

    if not args.skip_fetch:
        fetch_remote_db(config)

    expected = parse_iso_date(args.expected_date) if args.expected_date else None
    report = validate_local_db(
        db_path=config.openclaw_handoff.local_db_path,
        expected_date=expected,
        max_staleness_days=args.max_staleness_days,
        min_snapshots=args.min_snapshots,
        min_reconciliations=args.min_reconciliations,
    )

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
