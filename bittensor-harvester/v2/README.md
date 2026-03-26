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

To prepare OpenTensor staking transaction intents (fail-closed foundation module):

```powershell
python -m v2.tao_harvester.modules.opentensor_staking_foundation --input reports/v2_calculate_harvest_YYYY-MM-DD.json
```

This writes:

`reports/v2_opentensor_staking_foundation_YYYY-MM-DD.json`

Behavior:

- default mode is `intent_only` (no transaction execution),
- `--execute` requires explicit confirmation token and still routes through fail-closed no-op staking adapter,
- when `--execute` is used, the module performs Taostats pre/post stake snapshots around each OTF request attempt and records any observed stake delta for development verification,
- output is auditable request/result payload for the next implementation step.

When `--execute` is requested, the module now fail-closes unless OpenClaw DB sync validation passes in the same run.

Execution-only DB sync gate options:

- `--skip-db-sync-fetch` (validate existing local OpenClaw DB copy only)
- `--expected-db-date YYYY-MM-DD` (defaults to report date from input JSON)
- `--max-db-staleness-days` (default `1`)
- `--min-db-snapshots` (default `1`)
- `--min-db-reconciliations` (default `1`)

The output payload includes `db_sync_report` for audit traceability.

### Tier 3 Unstake Backend

Execution backend is controlled by `OPENTENSOR_STAKER_BACKEND`:

- `noop` (default, fail-closed)
- `local_sdk` (uses local bittensor SDK wallet + subtensor submission)

When using `local_sdk`, configure:

- `OPENTENSOR_NETWORK` (default `finney`)
- `OPENTENSOR_WALLET_NAME`
- `OPENTENSOR_WALLET_HOTKEY`

`--execute` still requires explicit confirmation token and DB sync validation gate.

## OpenClaw Handoff Config (Local Tier 3)

Use local `.env` values to pull handoff files from your OpenClaw VPS over SSH:

- `OPENCLAW_SSH_HOST`
- `OPENCLAW_SSH_PORT` (default `22`)
- `OPENCLAW_SSH_USER`
- `OPENCLAW_SSH_KEY_PATH`
- `OPENCLAW_HANDOFF_REMOTE_DIR` (default `/opt/harvester/handoff`)
- `OPENCLAW_HANDOFF_LOCAL_DIR` (default `handoff`)

Keep secrets and key paths only in local `.env`. Never commit real credentials.

To pull the latest OpenClaw SQLite database and validate freshness/health locally (Tier 3):

```powershell
python -m v2.tao_harvester.modules.sync_openclaw_db --expected-date 2026-03-26 --max-staleness-days 1
```

This command:

- fetches the remote DB over SCP using the `OPENCLAW_*` SSH config,
- validates required tables are present,
- checks latest reconciliation date freshness against `--expected-date`,
- checks snapshot/reconciliation row counts for the latest date,
- verifies latest `daily_planner` run status is healthy (`completed` or `manual_intervention_required`),
- reports negative-anomaly count for operator review before execution.

To validate an already-downloaded local DB without fetching:

```powershell
python -m v2.tao_harvester.modules.sync_openclaw_db --skip-fetch --expected-date 2026-03-26
```

## Unit Contract (Important)

- Reconciliation and earnings accounting are alpha-only.
- All persisted event amounts used by reconciliation are stored as alpha amounts.
- TAO fields in reports are derived estimates only, using per-subnet `tao_per_alpha` at snapshot time.
- TAO movement happens only after alpha is actually sold/consolidated in later execution tiers.
