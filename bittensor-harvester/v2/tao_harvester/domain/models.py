from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class AlphaSnapshot:
    snapshot_date: date
    wallet_address: str
    netuid: int
    alpha_balance: float
    source: str
    observed_at: datetime


@dataclass(frozen=True)
class TransferRecord:
    transfer_id: str
    wallet_address: str
    netuid: int
    direction: str
    alpha_amount: float
    occurred_at: datetime
    source: str


@dataclass(frozen=True)
class StakeHistoryRecord:
    event_id: str
    wallet_address: str
    netuid: int
    action: str
    alpha_amount: float
    occurred_at: datetime
    source: str


@dataclass(frozen=True)
class ReconciliationResult:
    reconciliation_date: date
    wallet_address: str
    netuid: int
    previous_alpha: float
    current_alpha: float
    gross_growth_alpha: float
    net_transfers_alpha: float
    net_manual_stake_alpha: float
    estimated_staking_earned_alpha: float
    notes: str


@dataclass(frozen=True)
class HarvestPlan:
    plan_date: date
    wallet_address: str
    planned_harvest_alpha: float
    estimated_tao_out: float
    harvest_fraction: float
    min_harvest_alpha: float
    dry_run: bool
    state: str
    reason: str


@dataclass(frozen=True)
class TransferBatch:
    batch_date: date
    wallet_address: str
    destination_address: str
    tao_amount: float
    state: str
    dry_run: bool
    reason: str


@dataclass(frozen=True)
class AuditEvent:
    event_time: datetime
    actor: str
    module: str
    event_type: str
    input_params: str
    result: str
    tx_hash: str | None
    error_message: str | None
    integrity_hash: str
