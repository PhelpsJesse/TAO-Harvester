# Implementation Checklist (v1.3 Controlled)

Date: 2026-03-10  
Baseline: `docs/REQUIREMENTS_SPEC_v1.3.md`  
Lessons Source: `docs/LESSONS_LEARNED_PRESERVED_2026-03-10.md`

## How to Use This Checklist

- This checklist is execution guidance under the v1.3 requirement baseline.
- Do not implement items that conflict with v1.3 without a documented requirement update first.
- Each phase has entry/exit gates. Do not advance phases early.

---

## Global Safety Gates (Apply to All Phases)

- [ ] Default mode is dry-run.
- [ ] No unattended signing logic in Tier 1.
- [ ] Whitelist enforcement implemented before any transfer execution path.
- [ ] All workflow stages are idempotent with DB uniqueness constraints.
- [ ] All timestamps use UTC and ISO-8601 format.
- [ ] Audit record written for all decision/execution events.

Traceability: FR-004, FR-006, FR-007, FR-008, NFR-001, NFR-004, NFR-005.

---

## Phase 1 — Tier 1 Read-Only Core (Build First)

Goal: Implement reliable ingestion, reconciliation, planning, and persistence with no value-moving execution.

### 1. Architecture and Package Foundation
- [ ] Freeze canonical module layout under `v2/tao_harvester`.
- [ ] Define interfaces for ingestion, repository, and workflows.
- [ ] Remove or quarantine legacy execution paths from active runtime.

Traceability: FR-001, FR-002, FR-006.

### 2. Database Core (Deterministic + Auditable)
- [ ] Finalize schema for: runs, run_stages, snapshots, transfer_events, stake_history_events, reconciliations, harvest_plans, transfer_batches.
- [ ] Add unique constraints supporting idempotent reruns.
- [ ] Add immutable audit table with integrity hash field.
- [ ] Add daily backup task definition.

Traceability: FR-006, NFR-001, NFR-002, Section 18.

### 3. Ingestion (Taostats Primary)
- [ ] Implement Taostats API adapter with retry/backoff and pagination.
- [ ] Normalize source fields into domain models.
- [ ] Mark incomplete/failed pulls as anomalous run conditions.

Traceability: FR-001, FR-002, Section 12.

### 4. Reconciliation Engine
- [ ] Implement per-subnet formula from Section 7.
- [ ] Enforce non-negative earned alpha constraint and anomaly flagging.
- [ ] Persist reconciliation outputs by subnet/date.

Traceability: FR-003, FR-004, FR-010, Section 7/8.

### 5. Harvest Planning (No Execution)
- [ ] Implement configurable harvest percentages/thresholds.
- [ ] Create draft/skip harvest plans only (no signing or submit).
- [ ] Implement transfer-batch planning threshold logic (draft only).

Traceability: FR-005, FR-007.

### 6. Workflow Orchestration
- [ ] Implement stage-based daily planner with resumable checkpoints.
- [ ] Add max 3 retry policy with fail-closed behavior.
- [ ] Add 7-day backfill window and manual-reconciliation guard.

Traceability: Section 13, Section 14, Section 21.

### 7. Tests (Mandatory Before Phase Exit)
- [ ] Unit tests for reconciliation formula and policy decisions.
- [ ] Subsystem tests for ingest→reconcile→plan flow.
- [ ] Idempotency rerun tests (same day, same inputs, no duplicates).
- [ ] Dry-run live validation path with no execution side effects.

Traceability: Section 20, Section 22.

### Phase 1 Exit Criteria
- [ ] Daily planner succeeds in dry-run and persists all required records.
- [ ] No transfer/signing code path can move value.
- [ ] Acceptance criteria for FR-001, FR-003, FR-004, FR-006 are test-evidenced.

---

## Phase 2 — Tier 2 Optional Exchange Integration (Still Controlled)

Goal: Introduce modular exchange integration without breaking Tier 1 guarantees.

### 1. Interface-First Exchange Module
- [ ] Keep exchange adapter behind explicit feature flags.
- [ ] Preserve dry-run behavior by default.
- [ ] Record all exchange intents/results as execution events.

Traceability: FR-009, NFR-004, NFR-005.

### 2. Risk Controls for Exchange Actions
- [ ] Enforce per-run and per-day caps at policy layer.
- [ ] Block execution on anomalies from reconciliation confidence.
- [ ] Require explicit operator enablement at runtime.

Traceability: Section 14, Section 17.

### 3. Tests and Validation
- [ ] Subsystem tests for no-op behavior when disabled.
- [ ] System tests for deterministic planning + exchange intent records.

### Phase 2 Exit Criteria
- [ ] Tier 2 features remain optional and disabled by default.
- [ ] No regression in Tier 1 dry-run and idempotency behavior.

---

## Phase 3 — Tier 3 Local Signing + Transfer Execution

Goal: Enable manual, password-gated, local-only value movement.

### 1. Trusted Local Signer CLI
- [ ] Implement manual password prompt and encrypted key unlock flow.
- [ ] Do not store mnemonic in unattended services.
- [ ] Enforce local-machine-only execution guard.

Traceability: FR-008, Section 6, Section 16.

### 2. Transfer Execution Controls
- [ ] Require whitelist validation against `config/whitelist.yaml`.
- [ ] Support emergency revoke that blocks execution immediately.
- [ ] Persist tx hash + full execution audit details.

Traceability: FR-007, FR-008, Section 15, Section 17.

### 3. End-to-End Validation
- [ ] Dry-run proves full workflow with zero value movement.
- [ ] Manual-sign test verifies password-gated transfer path.
- [ ] Whitelist negative tests verify fail-closed behavior.

### Phase 3 Exit Criteria
- [ ] Signing requires manual password entry every execution session.
- [ ] Transfers only execute to whitelisted destinations.
- [ ] All execution events are auditable and immutable.

---

## Deferred Clarification Queue (Implement After Core Stabilizes)

These are known open requirements to finalize after initial implementation signal:

- [ ] Deterministic ID definitions that avoid timestamp-driven duplication.
- [ ] Reconciliation confidence scoring formula and threshold.
- [ ] Rounding mode + decimal storage enforcement details.
- [ ] Data-source conflict tolerance thresholds.
- [ ] Retention vs immutability archival strategy.

Reference: Section 25 + pending v1.4 clarifications.

---

## Immediate Next 5 Build Tasks (Actionable)

- [ ] Add/verify schema migration path for current `v2` tables.
- [ ] Add idempotency test: rerun same date and confirm no duplicate stage side effects.
- [ ] Add anomaly-block test for negative estimated staking alpha.
- [ ] Add audit event model/table and wire planner stage events.
- [ ] Add whitelist config loader + validator (no execution yet, validation only).
