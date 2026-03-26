from enum import Enum


class RunStatus(str, Enum):
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"


class HarvestPlanState(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SKIPPED = "skipped"
    EXECUTED = "executed"
    FAILED = "failed"


class TransferBatchState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    SIGNED = "signed"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class OrderState(str, Enum):
    PLANNED = "planned"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELED = "canceled"
    FAILED = "failed"
