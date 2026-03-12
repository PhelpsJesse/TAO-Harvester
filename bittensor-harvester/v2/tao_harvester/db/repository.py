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
        self.conn.commit()

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
            INSERT INTO snapshots (snapshot_date, wallet_address, netuid, alpha_balance, source, observed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (snapshot_date, wallet_address, netuid, source)
            DO UPDATE SET alpha_balance = excluded.alpha_balance, observed_at = excluded.observed_at
            """,
            (
                snapshot.snapshot_date.isoformat(),
                snapshot.wallet_address,
                snapshot.netuid,
                snapshot.alpha_balance,
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
                transfer.alpha_amount,
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
                event.alpha_amount,
                event.occurred_at.isoformat(),
                event.source,
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
            FROM stake_history_events
            WHERE snapshot_date = ? AND wallet_address = ?
            GROUP BY netuid
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
                net_transfers_alpha, net_manual_stake_alpha,
                estimated_staking_earned_alpha, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (reconciliation_date, wallet_address, netuid)
            DO UPDATE SET
                previous_alpha = excluded.previous_alpha,
                current_alpha = excluded.current_alpha,
                gross_growth_alpha = excluded.gross_growth_alpha,
                net_transfers_alpha = excluded.net_transfers_alpha,
                net_manual_stake_alpha = excluded.net_manual_stake_alpha,
                estimated_staking_earned_alpha = excluded.estimated_staking_earned_alpha,
                notes = excluded.notes
            """,
            (
                result.reconciliation_date.isoformat(),
                result.wallet_address,
                result.netuid,
                result.previous_alpha,
                result.current_alpha,
                result.gross_growth_alpha,
                result.net_transfers_alpha,
                result.net_manual_stake_alpha,
                result.estimated_staking_earned_alpha,
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
                plan.planned_harvest_alpha,
                plan.estimated_tao_out,
                plan.harvest_fraction,
                plan.min_harvest_alpha,
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
                batch.tao_amount,
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

    def count_negative_raw_earned_anomalies(self, reconciliation_date: date, wallet_address: str) -> int:
        row = self.conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM reconciliations
            WHERE reconciliation_date = ?
              AND wallet_address = ?
              AND (gross_growth_alpha - net_transfers_alpha - net_manual_stake_alpha) < 0
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
