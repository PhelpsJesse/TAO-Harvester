from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime, timezone
import json
import logging

from v2.tao_harvester.adapters.taostats.base import TaostatsIngestionPort
from v2.tao_harvester.config.app_config import AppConfig
from v2.tao_harvester.db.repository import SQLiteRepository
from v2.tao_harvester.domain.enums import HarvestPlanState, TransferBatchState
from v2.tao_harvester.domain.models import AuditEvent, HarvestPlan, TransferBatch
from v2.tao_harvester.services.reconciliation import ReconciliationService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyPlannerResult:
    run_id: int
    snapshot_count: int
    reconciliation_count: int
    total_estimated_earned_alpha: float
    planned_harvest_alpha: float
    transfer_batch_created: bool


class DailyPlannerWorkflow:
    WORKFLOW_NAME = "daily_planner"
    TIER = "tier1"

    def __init__(self, repository: SQLiteRepository, ingestion: TaostatsIngestionPort, config: AppConfig):
        self.repository = repository
        self.ingestion = ingestion
        self.config = config
        self.recon_service = ReconciliationService(repository)

    def run(self, run_date: date, dry_run: bool) -> DailyPlannerResult:
        run_id = self.repository.get_or_create_run(
            run_date=run_date,
            workflow_name=self.WORKFLOW_NAME,
            tier=self.TIER,
            dry_run=dry_run,
        )
        self._audit(
            event_type="run_started",
            input_params={"run_id": run_id, "run_date": run_date.isoformat(), "dry_run": dry_run},
            result="started",
        )
        try:
            snapshot_count = self._stage_ingest(run_id, run_date)
            reconciliation_count = self._stage_reconcile(run_id, run_date)
            planned_harvest_alpha = self._stage_plan_harvest(run_id, run_date, dry_run)
            transfer_batch_created = self._stage_plan_transfer_batch(run_id, run_date, dry_run)

            total_estimated = self.repository.sum_estimated_earned_alpha(run_date, self.config.harvester_address)
            self.repository.mark_run_completed(run_id)
            self._audit(
                event_type="run_completed",
                input_params={"run_id": run_id},
                result="completed",
            )
            return DailyPlannerResult(
                run_id=run_id,
                snapshot_count=snapshot_count,
                reconciliation_count=reconciliation_count,
                total_estimated_earned_alpha=total_estimated,
                planned_harvest_alpha=planned_harvest_alpha,
                transfer_batch_created=transfer_batch_created,
            )
        except Exception as exc:
            self.repository.mark_run_failed(run_id, str(exc))
            self._audit(
                event_type="run_failed",
                input_params={"run_id": run_id},
                result="failed",
                error_message=str(exc),
            )
            raise

    def _audit(
        self,
        event_type: str,
        input_params: dict[str, object],
        result: str,
        tx_hash: str | None = None,
        error_message: str | None = None,
    ) -> None:
        event_time = datetime.now(timezone.utc).replace(tzinfo=None)
        payload = json.dumps(input_params, sort_keys=True)
        preview = AuditEvent(
            event_time=event_time,
            actor="system",
            module=self.WORKFLOW_NAME,
            event_type=event_type,
            input_params=payload,
            result=result,
            tx_hash=tx_hash,
            error_message=error_message,
            integrity_hash="",
        )
        event = AuditEvent(
            event_time=event_time,
            actor=preview.actor,
            module=preview.module,
            event_type=preview.event_type,
            input_params=preview.input_params,
            result=preview.result,
            tx_hash=preview.tx_hash,
            error_message=preview.error_message,
            integrity_hash=self.repository.build_audit_integrity_hash(preview),
        )
        self.repository.insert_audit_event(event)

    def _stage_ingest(self, run_id: int, run_date: date) -> int:
        if self.repository.stage_completed(run_id, "ingest"):
            logger.info("Stage ingest already completed for run_id=%s", run_id)
            return len(self.repository.get_snapshot_map(run_date, self.config.harvester_address))

        snapshots = self.ingestion.fetch_snapshots(run_date, self.config.harvester_address)
        transfers = self.ingestion.fetch_transfers(run_date, self.config.harvester_address)
        stake_history = self.ingestion.fetch_stake_history(run_date, self.config.harvester_address)

        for snapshot in snapshots:
            self.repository.upsert_snapshot(snapshot)
        for transfer in transfers:
            self.repository.insert_transfer_event(run_date, transfer)
        for event in stake_history:
            self.repository.insert_stake_history_event(run_date, event)

        self.repository.mark_stage_completed(run_id, "ingest")
        return len(snapshots)

    def _stage_reconcile(self, run_id: int, run_date: date) -> int:
        if self.repository.stage_completed(run_id, "reconcile"):
            logger.info("Stage reconcile already completed for run_id=%s", run_id)
            return self.repository.count_reconciliations(run_date, self.config.harvester_address)
        results = self.recon_service.reconcile_day(run_date, self.config.harvester_address)
        self.repository.mark_stage_completed(run_id, "reconcile")
        return len(results)

    def _stage_plan_harvest(self, run_id: int, run_date: date, dry_run: bool) -> float:
        if self.repository.stage_completed(run_id, "plan_harvest"):
            logger.info("Stage plan_harvest already completed for run_id=%s", run_id)
            return self.repository.get_planned_harvest_alpha(run_date, self.config.harvester_address, dry_run)

        anomaly_count = self.repository.count_negative_raw_earned_anomalies(run_date, self.config.harvester_address)
        total_estimated = self.repository.sum_estimated_earned_alpha(run_date, self.config.harvester_address)
        planned_alpha = total_estimated * self.config.rules.harvest_fraction

        if anomaly_count > 0:
            state = HarvestPlanState.SKIPPED.value
            reason = f"anomaly detected: negative raw earned alpha on {anomaly_count} subnet(s)"
            planned_alpha = 0.0
        elif planned_alpha < self.config.rules.min_harvest_alpha:
            state = HarvestPlanState.SKIPPED.value
            reason = (
                f"below threshold: planned_alpha={planned_alpha:.6f} < min={self.config.rules.min_harvest_alpha:.6f}"
            )
            planned_alpha = 0.0
        else:
            state = HarvestPlanState.DRAFT.value
            reason = "dry-run plan created"

        estimated_tao_out = min(planned_alpha, self.config.rules.max_harvest_tao_per_run)
        plan = HarvestPlan(
            plan_date=run_date,
            wallet_address=self.config.harvester_address,
            planned_harvest_alpha=planned_alpha,
            estimated_tao_out=estimated_tao_out,
            harvest_fraction=self.config.rules.harvest_fraction,
            min_harvest_alpha=self.config.rules.min_harvest_alpha,
            dry_run=dry_run,
            state=state,
            reason=reason,
        )
        self.repository.upsert_harvest_plan(plan)
        self.repository.mark_stage_completed(run_id, "plan_harvest")
        return planned_alpha

    def _stage_plan_transfer_batch(self, run_id: int, run_date: date, dry_run: bool) -> bool:
        if self.repository.stage_completed(run_id, "plan_transfer_batch"):
            logger.info("Stage plan_transfer_batch already completed for run_id=%s", run_id)
            return self.repository.has_transfer_batch(run_date, self.config.harvester_address, dry_run)

        if not self.config.kraken_deposit_whitelist:
            self.repository.mark_stage_completed(run_id, "plan_transfer_batch")
            return False

        total_estimated = self.repository.sum_estimated_earned_alpha(run_date, self.config.harvester_address)
        expected_harvest_tao = total_estimated * self.config.rules.harvest_fraction

        if expected_harvest_tao < self.config.rules.transfer_batch_threshold_tao:
            self.repository.mark_stage_completed(run_id, "plan_transfer_batch")
            return False

        batch = TransferBatch(
            batch_date=run_date,
            wallet_address=self.config.harvester_address,
            destination_address=self.config.kraken_deposit_whitelist[0],
            tao_amount=min(expected_harvest_tao, self.config.rules.max_harvest_tao_per_day),
            state=TransferBatchState.DRAFT.value,
            dry_run=dry_run,
            reason="threshold met; batch planned only",
        )
        self.repository.upsert_transfer_batch(batch)
        self.repository.mark_stage_completed(run_id, "plan_transfer_batch")
        return True
