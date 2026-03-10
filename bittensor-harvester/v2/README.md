# TAO Harvester V2

Modular refactor with risk-tier separation.

## First Deliverable Included

- Project skeleton with clear modules
- SQLite schema and repository
- Taostats ingestion interfaces + adapters
- Reconciliation logic for estimated staking-earned alpha
- CLI command for dry-run daily planner
- Interfaces only for Kraken execution and chain signing

## Run

From project root:

```powershell
python -m v2.tao_harvester.cli daily-planner --dry-run --date 2026-03-10 --source mock
```

This writes run state, snapshots, reconciliations, and harvest/transfer plans into SQLite.

To run a Taostats-backed daily report and compute planned harvest amount:

```powershell
python -m v2.tao_harvester.cli daily-report --dry-run --date 2026-03-10 --source taostats
```

This writes a report JSON file at:

`reports/v2_daily_report_YYYY-MM-DD.json`
