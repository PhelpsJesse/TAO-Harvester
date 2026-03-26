from __future__ import annotations

import sqlite3
import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

from v2.tao_harvester.domain.enums import RunStatus
from v2.tao_harvester.domain.models import (
    AlphaSnapshot,
    AuditEvent,
    HarvestPlan,
    ReconciliationResult,
    StakeHistoryRecord,
    TradeEventRecord,
    TransferBatch,
    TransferRecord,
)


class SQLiteRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def init_schema(self, schema_path: str) -> None:
        with open(schema_path, "r", encoding="utf-8") as file:
            script = file.read()
        self.conn.executescript(script)
        self._ensure_schema_compatibility()
        self.conn.commit()

    def _ensure_schema_compatibility(self) -> None:
        self._migrate_real_to_text_if_needed()

    def _migrate_real_to_text_if_needed(self) -> None:
        """Migrate financial REAL columns to TEXT for spec Section 11 compliance.

        Uses rename-recreate-copy-drop pattern because SQLite does not support
        ALTER COLUMN. Existing data is preserved; REAL values are cast to TEXT
        via CAST(col AS TEXT) which produces the same decimal representation
        SQLite stored. Migration is idempotent: skipped if column type is already TEXT.
        """
        _MIGRATIONS = [
            (
                "snapshots",
                "alpha_balance",
                """CREATE TABLE snapshots_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    netuid INTEGER NOT NULL,
                    alpha_balance TEXT NOT NULL,
                    tao_per_alpha TEXT,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (snapshot_date, wallet_address, netuid, source)
                )""",
                """INSERT INTO snapshots_new
                   SELECT id, snapshot_date, wallet_address, netuid,
                          CAST(alpha_balance AS TEXT),
                          CASE WHEN tao_per_alpha IS NULL THEN NULL ELSE CAST(tao_per_alpha AS TEXT) END,
                          source, observed_at, created_at
                   FROM snapshots""",
            ),
            (
                "transfer_events",
                "alpha_amount",
                """CREATE TABLE transfer_events_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    transfer_id TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    netuid INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    alpha_amount TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    UNIQUE (transfer_id, source)
                )""",
                """INSERT INTO transfer_events_new
                   SELECT id, snapshot_date, transfer_id, wallet_address, netuid,
                          direction, CAST(alpha_amount AS TEXT), occurred_at, source
                   FROM transfer_events""",
            ),
            (
                "stake_history_events",
                "alpha_amount",
                """CREATE TABLE stake_history_events_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    netuid INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    alpha_amount TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    UNIQUE (event_id, source)
                )""",
                """INSERT INTO stake_history_events_new
                   SELECT id, snapshot_date, event_id, wallet_address, netuid,
                          action, CAST(alpha_amount AS TEXT), occurred_at, source
                   FROM stake_history_events""",
            ),
            (
                "trade_events",
                "alpha_amount",
                """CREATE TABLE trade_events_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    trade_id TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    netuid INTEGER NOT NULL,
                    direction TEXT NOT NULL,
                    alpha_amount TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    UNIQUE (trade_id, source)
                )""",
                """INSERT INTO trade_events_new
                   SELECT id, snapshot_date, trade_id, wallet_address, netuid,
                          direction, CAST(alpha_amount AS TEXT), occurred_at, source
                   FROM trade_events""",
            ),
            (
                "reconciliations",
                "previous_alpha",
                """CREATE TABLE reconciliations_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reconciliation_date TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    netuid INTEGER NOT NULL,
                    previous_alpha TEXT NOT NULL,
                    current_alpha TEXT NOT NULL,
                    gross_growth_alpha TEXT NOT NULL,
                    net_trade_adjustment_alpha TEXT NOT NULL,
                    net_transfers_alpha TEXT NOT NULL,
                    net_manual_stake_alpha TEXT NOT NULL,
                    estimated_staking_earned_alpha TEXT NOT NULL,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (reconciliation_date, wallet_address, netuid)
                )""",
                """INSERT INTO reconciliations_new
                   SELECT id, reconciliation_date, wallet_address, netuid,
                          CAST(previous_alpha AS TEXT), CAST(current_alpha AS TEXT),
                          CAST(gross_growth_alpha AS TEXT), CAST(net_trade_adjustment_alpha AS TEXT),
                          CAST(net_transfers_alpha AS TEXT), CAST(net_manual_stake_alpha AS TEXT),
                          CAST(estimated_staking_earned_alpha AS TEXT), notes, created_at
                   FROM reconciliations""",
            ),
            (
                "harvest_plans",
                "planned_harvest_alpha",
                """CREATE TABLE harvest_plans_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_date TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    planned_harvest_alpha TEXT NOT NULL,
                    estimated_tao_out TEXT NOT NULL,
                    harvest_fraction TEXT NOT NULL,
                    min_harvest_alpha TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT,
                    dry_run INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (plan_date, wallet_address, dry_run)
                )""",
                """INSERT INTO harvest_plans_new
                   SELECT id, plan_date, wallet_address,
                          CAST(planned_harvest_alpha AS TEXT), CAST(estimated_tao_out AS TEXT),
                          CAST(harvest_fraction AS TEXT), CAST(min_harvest_alpha AS TEXT),
                          state, reason, dry_run, created_at
                   FROM harvest_plans""",
            ),
            (
                "transfer_batches",
                "tao_amount",
                """CREATE TABLE transfer_batches_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_date TEXT NOT NULL,
                    wallet_address TEXT NOT NULL,
                    destination_address TEXT NOT NULL,
                    tao_amount TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT,
                    dry_run INTEGER NOT NULL,
                    tx_hash TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (batch_date, wallet_address, destination_address, dry_run)
                )""",
                """INSERT INTO transfer_batches_new
                   SELECT id, batch_date, wallet_address, destination_address,
                          CAST(tao_amount AS TEXT), state, reason, dry_run, tx_hash, created_at
                   FROM transfer_batches""",
            ),
        ]

        for table, sentinel_col, create_sql, copy_sql in _MIGRATIONS:
            col_info = {
                str(row["name"]): str(row["type"])
                for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if col_info.get(sentinel_col, "").upper() != "REAL":
                # Already migrated or table doesn't exist yet
                continue
            new_table = f"{table}_new"
            self.conn.execute(f"DROP TABLE IF EXISTS {new_table}")
            self.conn.execute(create_sql)
            self.conn.execute(copy_sql)
            self.conn.execute(f"DROP TABLE {table}")
            self.conn.execute(f"ALTER TABLE {new_table} RENAME TO {table}")

    def get_or_create_run(self, run_date: date, workflow_name: str, tier: str, dry_run: bool) -> int:
        row = self.conn.execute(
            """
            SELECT id FROM runs
            WHERE run_date = ? AND workflow_name = ? AND tier = ? AND dry_run = ?
            """,
            (run_date.isoformat(), workflow_name, tier, int(dry_run)),
        ).fetchone()
        if row:
            return int(row["id"])

        now = self._utc_now().isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO runs (run_date, workflow_name, tier, dry_run, status, started_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_date.isoformat(), workflow_name, tier, int(dry_run), RunStatus.STARTED.value, now),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def mark_run_completed(self, run_id: int) -> None:
        self.conn.execute(
            """
            UPDATE runs
            SET status = ?, completed_at = ?, error_message = NULL
            WHERE id = ?
            """,
            (RunStatus.COMPLETED.value, self._utc_now().isoformat(), run_id),
        )
        self.conn.commit()

    def mark_run_failed(self, run_id: int, error_message: str) -> None:
        self.conn.execute(
            """
            UPDATE runs
            SET status = ?, completed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (RunStatus.FAILED.value, self._utc_now().isoformat(), error_message, run_id),
        )
        self.conn.commit()

    def mark_run_manual_intervention_required(self, run_id: int, error_message: str) -> None:
        self.conn.execute(
            """
            UPDATE runs
            SET status = ?, completed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (RunStatus.MANUAL_INTERVENTION_REQUIRED.value, self._utc_now().isoformat(), error_message, run_id),
        )
        self.conn.commit()

    def stage_completed(self, run_id: int, stage_name: str, stage_key: str = "default") -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM run_stages WHERE run_id = ? AND stage_name = ? AND stage_key = ?
            """,
            (run_id, stage_name, stage_key),
        ).fetchone()
        return bool(row)

    def mark_stage_completed(self, run_id: int, stage_name: str, stage_key: str = "default") -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO run_stages (run_id, stage_name, stage_key, completed_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, stage_name, stage_key, self._utc_now().isoformat()),
        )
        self.conn.commit()

    def upsert_snapshot(self, snapshot: AlphaSnapshot) -> None:
        self.conn.execute(
            """
            INSERT INTO snapshots (snapshot_date, wallet_address, netuid, alpha_balance, tao_per_alpha, source, observed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_date, wallet_address, netuid, source)
            DO UPDATE SET
                alpha_balance = excluded.alpha_balance,
                tao_per_alpha = excluded.tao_per_alpha,
                observed_at = excluded.observed_at
            """,
            (
                snapshot.snapshot_date.isoformat(),
                snapshot.wallet_address,
                snapshot.netuid,
                str(snapshot.alpha_balance),
                str(snapshot.tao_per_alpha) if snapshot.tao_per_alpha is not None else None,
                snapshot.source,
                snapshot.observed_at.isoformat(),
                self._utc_now().isoformat(),
            ),
        )
        self.conn.commit()

    def insert_transfer_event(self, snapshot_date: date, transfer: TransferRecord) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO transfer_events
            (snapshot_date, transfer_id, wallet_address, netuid, direction, alpha_amount, occurred_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_date.isoformat(),
                transfer.transfer_id,
                transfer.wallet_address,
                transfer.netuid,
                transfer.direction,
                str(transfer.alpha_amount),
                transfer.occurred_at.isoformat(),
                transfer.source,
            ),
        )
        self.conn.commit()

    def insert_stake_history_event(self, snapshot_date: date, event: StakeHistoryRecord) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO stake_history_events
            (snapshot_date, event_id, wallet_address, netuid, action, alpha_amount, occurred_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_date.isoformat(),
                event.event_id,
                event.wallet_address,
                event.netuid,
                event.action,
                str(event.alpha_amount),
                event.occurred_at.isoformat(),
                event.source,
            ),
        )
        self.conn.commit()

    def insert_trade_event(self, snapshot_date: date, trade: TradeEventRecord) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO trade_events
            (snapshot_date, trade_id, wallet_address, netuid, direction, alpha_amount, occurred_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_date.isoformat(),
                trade.trade_id,
                trade.wallet_address,
                trade.netuid,
                trade.direction,
                str(trade.alpha_amount),
                trade.occurred_at.isoformat(),
                trade.source,
            ),
        )
        self.conn.commit()

    def get_snapshot_map(self, snapshot_date: date, wallet_address: str) -> dict[int, float]:
        rows = self.conn.execute(
            """
            SELECT netuid, alpha_balance
            FROM snapshots
            WHERE snapshot_date = ? AND wallet_address = ?
            """,
            (snapshot_date.isoformat(), wallet_address),
        ).fetchall()
        return {int(row["netuid"]): float(row["alpha_balance"]) for row in rows}

    def has_snapshot_missing_tao_rates(self, snapshot_date: date, wallet_address: str) -> bool:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM snapshots
            WHERE snapshot_date = ?
              AND wallet_address = ?
              AND (tao_per_alpha IS NULL OR tao_per_alpha <= 0)
            """,
            (snapshot_date.isoformat(), wallet_address),
        ).fetchone()
        return int(row["total"] or 0) > 0

    def get_latest_snapshot_date_before(self, snapshot_date: date, wallet_address: str) -> date | None:
        row = self.conn.execute(
            """
            SELECT MAX(snapshot_date) AS max_date
            FROM snapshots
            WHERE wallet_address = ? AND snapshot_date < ?
            """,
            (wallet_address, snapshot_date.isoformat()),
        ).fetchone()
        raw = row["max_date"] if row else None
        if not raw:
            return None
        return date.fromisoformat(str(raw))

    def get_snapshot_observed_at(self, snapshot_date: date, wallet_address: str) -> datetime | None:
        row = self.conn.execute(
            """
            SELECT MAX(observed_at) AS observed_at
            FROM snapshots
            WHERE snapshot_date = ? AND wallet_address = ?
            """,
            (snapshot_date.isoformat(), wallet_address),
        ).fetchone()
        raw = row["observed_at"] if row else None
        if not raw:
            return None
        return datetime.fromisoformat(str(raw))

    def get_transfer_net_by_netuid(self, snapshot_date: date, wallet_address: str) -> dict[int, float]:
        rows = self.conn.execute(
            """
            SELECT netuid,
                   SUM(CASE WHEN direction = 'in' THEN alpha_amount ELSE -alpha_amount END) AS net_amount
            FROM transfer_events
            WHERE snapshot_date = ? AND wallet_address = ?
            GROUP BY netuid
            """,
            (snapshot_date.isoformat(), wallet_address),
        ).fetchall()
        return {int(row["netuid"]): float(row["net_amount"] or 0.0) for row in rows}

    def get_manual_stake_net_by_netuid(self, snapshot_date: date, wallet_address: str) -> dict[int, float]:
        rows = self.conn.execute(
            """
            SELECT netuid,
                   SUM(CASE
                       WHEN action = 'manual_stake' THEN alpha_amount
                       WHEN action = 'manual_unstake' THEN -alpha_amount
                       ELSE 0
                   END) AS net_amount
            FROM stake_history_events she
            WHERE she.snapshot_date = ?
              AND she.wallet_address = ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM trade_events te
                  WHERE te.snapshot_date = she.snapshot_date
                    AND te.wallet_address = she.wallet_address
                    AND te.netuid = she.netuid
                    AND te.trade_id LIKE she.event_id || '-%'
              )
            GROUP BY netuid
            """,
            (snapshot_date.isoformat(), wallet_address),
        ).fetchall()
        return {int(row["netuid"]): float(row["net_amount"] or 0.0) for row in rows}

    def get_trade_net_by_netuid(self, snapshot_date: date, wallet_address: str) -> dict[int, float]:
        rows = self.conn.execute(
            """
            SELECT te.netuid,
                   SUM(CASE
                       WHEN te.direction = 'buy_alpha' THEN COALESCE(she.alpha_amount, te.alpha_amount)
                       WHEN te.direction = 'sell_alpha' THEN -COALESCE(she.alpha_amount, te.alpha_amount)
                       ELSE 0
                   END) AS net_amount
            FROM trade_events te
            LEFT JOIN stake_history_events she
              ON she.snapshot_date = te.snapshot_date
             AND she.wallet_address = te.wallet_address
             AND she.netuid = te.netuid
             AND te.trade_id LIKE she.event_id || '-%'
            WHERE te.snapshot_date = ? AND te.wallet_address = ?
            GROUP BY te.netuid
            """,
            (snapshot_date.isoformat(), wallet_address),
        ).fetchall()
        return {int(row["netuid"]): float(row["net_amount"] or 0.0) for row in rows}

    def upsert_reconciliation(self, result: ReconciliationResult) -> None:
        self.conn.execute(
            """
            INSERT INTO reconciliations (
                reconciliation_date, wallet_address, netuid,
                previous_alpha, current_alpha, gross_growth_alpha,
                net_trade_adjustment_alpha,
                net_transfers_alpha, net_manual_stake_alpha,
                estimated_staking_earned_alpha, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (reconciliation_date, wallet_address, netuid)
            DO UPDATE SET
                previous_alpha = excluded.previous_alpha,
                current_alpha = excluded.current_alpha,
                gross_growth_alpha = excluded.gross_growth_alpha,
                net_trade_adjustment_alpha = excluded.net_trade_adjustment_alpha,
                net_transfers_alpha = excluded.net_transfers_alpha,
                net_manual_stake_alpha = excluded.net_manual_stake_alpha,
                estimated_staking_earned_alpha = excluded.estimated_staking_earned_alpha,
                notes = excluded.notes
            """,
            (
                result.reconciliation_date.isoformat(),
                result.wallet_address,
                result.netuid,
                str(result.previous_alpha),
                str(result.current_alpha),
                str(result.gross_growth_alpha),
                str(result.net_trade_adjustment_alpha),
                str(result.net_transfers_alpha),
                str(result.net_manual_stake_alpha),
                str(result.estimated_staking_earned_alpha),
                result.notes,
                self._utc_now().isoformat(),
            ),
        )
        self.conn.commit()

    def upsert_harvest_plan(self, plan: HarvestPlan) -> None:
        self.conn.execute(
            """
            INSERT INTO harvest_plans
            (plan_date, wallet_address, planned_harvest_alpha, estimated_tao_out,
             harvest_fraction, min_harvest_alpha, state, reason, dry_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (plan_date, wallet_address, dry_run)
            DO UPDATE SET
                planned_harvest_alpha = excluded.planned_harvest_alpha,
                estimated_tao_out = excluded.estimated_tao_out,
                state = excluded.state,
                reason = excluded.reason
            """,
            (
                plan.plan_date.isoformat(),
                plan.wallet_address,
                str(plan.planned_harvest_alpha),
                str(plan.estimated_tao_out),
                str(plan.harvest_fraction),
                str(plan.min_harvest_alpha),
                plan.state,
                plan.reason,
                int(plan.dry_run),
                self._utc_now().isoformat(),
            ),
        )
        self.conn.commit()

    def upsert_transfer_batch(self, batch: TransferBatch) -> None:
        self.conn.execute(
            """
            INSERT INTO transfer_batches
            (batch_date, wallet_address, destination_address, tao_amount, state, reason, dry_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (batch_date, wallet_address, destination_address, dry_run)
            DO UPDATE SET tao_amount = excluded.tao_amount, state = excluded.state, reason = excluded.reason
            """,
            (
                batch.batch_date.isoformat(),
                batch.wallet_address,
                batch.destination_address,
                str(batch.tao_amount),
                batch.state,
                batch.reason,
                int(batch.dry_run),
                self._utc_now().isoformat(),
            ),
        )
        self.conn.commit()

    def sum_estimated_earned_alpha(self, reconciliation_date: date, wallet_address: str) -> float:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(estimated_staking_earned_alpha), 0.0) AS total
            FROM reconciliations
            WHERE reconciliation_date = ? AND wallet_address = ?
            """,
            (reconciliation_date.isoformat(), wallet_address),
        ).fetchone()
        return float(row["total"] or 0.0)

    def sum_estimated_earned_alpha_between(self, start_date: date, end_date: date, wallet_address: str) -> float:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(estimated_staking_earned_alpha), 0.0) AS total
            FROM reconciliations
            WHERE reconciliation_date >= ? AND reconciliation_date <= ? AND wallet_address = ?
            """,
            (start_date.isoformat(), end_date.isoformat(), wallet_address),
        ).fetchone()
        return float(row["total"] or 0.0)

    def sum_estimated_earned_tao_between(self, start_date: date, end_date: date, wallet_address: str) -> float:
        rows = self.conn.execute(
            """
            SELECT r.estimated_staking_earned_alpha AS est_alpha,
                   COALESCE((
                       SELECT MAX(s.tao_per_alpha)
                       FROM snapshots s
                       WHERE s.snapshot_date = r.reconciliation_date
                         AND s.wallet_address = r.wallet_address
                         AND s.netuid = r.netuid
                   ), 0.0) AS tao_per_alpha
            FROM reconciliations r
            WHERE r.reconciliation_date >= ? AND r.reconciliation_date <= ? AND r.wallet_address = ?
            """,
            (start_date.isoformat(), end_date.isoformat(), wallet_address),
        ).fetchall()
        return float(sum(float(row["est_alpha"] or 0.0) * float(row["tao_per_alpha"] or 0.0) for row in rows))

    def get_latest_reconciliation_date(self, wallet_address: str) -> date | None:
        row = self.conn.execute(
            """
            SELECT MAX(reconciliation_date) AS max_date
            FROM reconciliations
            WHERE wallet_address = ?
            """,
            (wallet_address,),
        ).fetchone()
        raw = row["max_date"] if row else None
        if not raw:
            return None
        return date.fromisoformat(str(raw))

    def count_reconciliations(self, reconciliation_date: date, wallet_address: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM reconciliations
            WHERE reconciliation_date = ? AND wallet_address = ?
            """,
            (reconciliation_date.isoformat(), wallet_address),
        ).fetchone()
        return int(row["total"] or 0)

    def get_planned_harvest_alpha(self, plan_date: date, wallet_address: str, dry_run: bool) -> float:
        row = self.conn.execute(
            """
            SELECT planned_harvest_alpha
            FROM harvest_plans
            WHERE plan_date = ? AND wallet_address = ? AND dry_run = ?
            """,
            (plan_date.isoformat(), wallet_address, int(dry_run)),
        ).fetchone()
        if not row:
            return 0.0
        return float(row["planned_harvest_alpha"] or 0.0)

    def has_transfer_batch(self, batch_date: date, wallet_address: str, dry_run: bool) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM transfer_batches
            WHERE batch_date = ? AND wallet_address = ? AND dry_run = ?
            """,
            (batch_date.isoformat(), wallet_address, int(dry_run)),
        ).fetchone()
        return bool(row)

    def get_daily_earnings_by_subnet(self, reconciliation_date: date, wallet_address: str) -> list[dict[str, float | int]]:
        rows = self.conn.execute(
            """
            SELECT netuid, estimated_staking_earned_alpha
            FROM reconciliations
            WHERE reconciliation_date = ? AND wallet_address = ?
            ORDER BY netuid ASC
            """,
            (reconciliation_date.isoformat(), wallet_address),
        ).fetchall()
        return [
            {
                "netuid": int(row["netuid"]),
                "estimated_earned_alpha": float(row["estimated_staking_earned_alpha"] or 0.0),
            }
            for row in rows
        ]

    def get_daily_earnings_by_subnet_with_tao(
        self,
        reconciliation_date: date,
        wallet_address: str,
        harvest_fraction: float,
    ) -> list[dict[str, float | int]]:
        rows = self.conn.execute(
            """
            SELECT r.netuid,
                   r.estimated_staking_earned_alpha AS estimated_earned_alpha,
                   COALESCE((
                       SELECT MAX(s.tao_per_alpha)
                       FROM snapshots s
                       WHERE s.snapshot_date = r.reconciliation_date
                         AND s.wallet_address = r.wallet_address
                         AND s.netuid = r.netuid
                   ), 0.0) AS tao_per_alpha
            FROM reconciliations r
            WHERE r.reconciliation_date = ? AND r.wallet_address = ?
            ORDER BY r.netuid ASC
            """,
            (reconciliation_date.isoformat(), wallet_address),
        ).fetchall()
        output: list[dict[str, float | int]] = []
        for row in rows:
            est_alpha = float(row["estimated_earned_alpha"] or 0.0)
            tao_per_alpha = float(row["tao_per_alpha"] or 0.0)
            est_tao = est_alpha * tao_per_alpha
            output.append(
                {
                    "netuid": int(row["netuid"]),
                    "estimated_earned_alpha": est_alpha,
                    "tao_per_alpha": tao_per_alpha,
                    "estimated_earned_tao": est_tao,
                    "harvestable_tao": est_tao * harvest_fraction,
                }
            )
        return output

    def count_negative_raw_earned_anomalies(self, reconciliation_date: date, wallet_address: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM reconciliations
            WHERE reconciliation_date = ?
              AND wallet_address = ?
                            AND (gross_growth_alpha - net_trade_adjustment_alpha - net_transfers_alpha) < 0
            """,
            (reconciliation_date.isoformat(), wallet_address),
        ).fetchone()
        return int(row["total"] or 0)

    @staticmethod
    def build_audit_integrity_hash(event: AuditEvent) -> str:
        payload = "|".join(
            [
                event.event_time.isoformat(),
                event.actor,
                event.module,
                event.event_type,
                event.input_params,
                event.result,
                event.tx_hash or "",
                event.error_message or "",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def insert_audit_event(self, event: AuditEvent) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO audit_events
            (event_time, actor, module, event_type, input_params, result, tx_hash, error_message, integrity_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_time.isoformat(),
                event.actor,
                event.module,
                event.event_type,
                event.input_params,
                event.result,
                event.tx_hash,
                event.error_message,
                event.integrity_hash,
                self._utc_now().isoformat(),
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)
