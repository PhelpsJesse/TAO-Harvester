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

To run the standalone calculate-harvest module (OpenClaw Tier 1 daily job):

```powershell
python -m v2.tao_harvester.modules.calculate_harvest --dry-run --date 2026-03-19 --source taostats --subnet-tao-threshold 0.005
```

This writes:

`reports/v2_calculate_harvest_YYYY-MM-DD.json`

The output includes:

- full all-subnet estimated TAO totals,
- thresholded harvestable TAO and alpha totals,
- per-subnet execution intents (`netuid`, `alpha_to_harvest`, `estimated_tao_out`) for the next-stage Opentensor swap module.

## Unit Contract (Important)

- Reconciliation and earnings accounting are alpha-only.
- All persisted event amounts used by reconciliation are stored as alpha amounts.
- TAO fields in reports are derived estimates only, using per-subnet `tao_per_alpha` at snapshot time.
- TAO movement happens only after alpha is actually sold/consolidated in later execution tiers.
