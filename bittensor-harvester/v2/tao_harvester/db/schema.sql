PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    workflow_name TEXT NOT NULL,
    tier TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_message TEXT,
    UNIQUE (run_date, workflow_name, tier, dry_run)
);

CREATE TABLE IF NOT EXISTS run_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    stage_name TEXT NOT NULL,
    stage_key TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    UNIQUE (run_id, stage_name, stage_key),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    netuid INTEGER NOT NULL,
    alpha_balance REAL NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (snapshot_date, wallet_address, netuid, source)
);

CREATE TABLE IF NOT EXISTS transfer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    transfer_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    netuid INTEGER NOT NULL,
    direction TEXT NOT NULL,
    alpha_amount REAL NOT NULL,
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (transfer_id, source)
);

CREATE TABLE IF NOT EXISTS stake_history_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL,
    event_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    netuid INTEGER NOT NULL,
    action TEXT NOT NULL,
    alpha_amount REAL NOT NULL,
    occurred_at TEXT NOT NULL,
    source TEXT NOT NULL,
    UNIQUE (event_id, source)
);

CREATE TABLE IF NOT EXISTS reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reconciliation_date TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    netuid INTEGER NOT NULL,
    previous_alpha REAL NOT NULL,
    current_alpha REAL NOT NULL,
    gross_growth_alpha REAL NOT NULL,
    net_transfers_alpha REAL NOT NULL,
    net_manual_stake_alpha REAL NOT NULL,
    estimated_staking_earned_alpha REAL NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (reconciliation_date, wallet_address, netuid)
);

CREATE TABLE IF NOT EXISTS harvest_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_date TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    planned_harvest_alpha REAL NOT NULL,
    estimated_tao_out REAL NOT NULL,
    harvest_fraction REAL NOT NULL,
    min_harvest_alpha REAL NOT NULL,
    state TEXT NOT NULL,
    reason TEXT,
    dry_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (plan_date, wallet_address, dry_run)
);

CREATE TABLE IF NOT EXISTS transfer_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_date TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    destination_address TEXT NOT NULL,
    tao_amount REAL NOT NULL,
    state TEXT NOT NULL,
    reason TEXT,
    dry_run INTEGER NOT NULL,
    tx_hash TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (batch_date, wallet_address, destination_address, dry_run)
);

CREATE TABLE IF NOT EXISTS kraken_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_date TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    pair TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    requested_base_amount REAL NOT NULL,
    filled_base_amount REAL NOT NULL DEFAULT 0,
    avg_price REAL,
    fee_quote REAL,
    state TEXT NOT NULL,
    external_order_id TEXT,
    dry_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    actor TEXT NOT NULL,
    module TEXT NOT NULL,
    event_type TEXT NOT NULL,
    input_params TEXT NOT NULL,
    result TEXT NOT NULL,
    tx_hash TEXT,
    error_message TEXT,
    integrity_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
