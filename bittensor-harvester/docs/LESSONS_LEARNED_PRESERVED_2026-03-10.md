# Lessons Learned to Preserve Before Rewrite

Date: 2026-03-10  
Scope: Existing `src/` + `docs/` behavior and operational findings preserved for restart.

## Why This Exists

This file captures concrete lessons from the current codebase so we keep validated operational knowledge while replacing architecture and implementation.

## Keep (Validated and High-Value)

- Safety-first defaults are the right baseline:
  - Dry-run by default.
  - Explicit execution gating (kill switches) is essential.
- Daily snapshot + reconciliation model is the right operational shape:
  - Simpler than high-frequency polling.
  - Better for single-developer maintainability.
- Local SQLite persistence fits the project:
  - Deterministic state tracking.
  - Supports idempotent daily workflows and backfill behavior.
- Separation by risk tier is correct:
  - VPS for ingestion/planning.
  - Trusted local execution for signing and transfers.

## Preserve as Hard Requirements During Rewrite

- Never move value without explicit non-dry-run intent and whitelist validation.
- Preserve manual-signing boundary (no unattended mnemonic exposure).
- Keep durable run/reconciliation/audit records for every run attempt.
- Keep subnet-by-subnet accounting (no aggregate-only shortcuts).

## Proven Operational Lessons

### 1) Data-source reliability and rate limits

- Taostats API proved practical for daily balance ingestion.
- Archive RPC can be unsuitable for bulk polling depending on endpoint throttling.
- Design implication:
  - Use API-driven daily ingestion for Tier 1.
  - Reserve chain RPC for verification/signing-critical steps.
  - Keep retry/backoff and anomaly flagging first-class.

### 2) Safety incident response patterns

From existing security docs:
- External automations can trigger unintended activity outside this codebase.
- Triple-gating and explicit runtime controls are necessary even when code is read-only oriented.
- Design implication:
  - Treat execution as opt-in and reversible (emergency revoke path).
  - Keep audit records immutable and easy to inspect.

### 3) Idempotency and stage-based runs

- Stage checkpointing is effective for resume/retry behavior.
- Duplicate execution risk is highest when IDs include run-time timestamps.
- Design implication:
  - Use deterministic business keys for run artifacts.
  - Use DB unique constraints to enforce idempotency physically.

### 4) Time handling consistency

- Existing code heavily used UTC, which is correct.
- Naive UTC generation patterns (`utcnow`) caused modernization/deprecation issues.
- Design implication:
  - Use explicit UTC everywhere.
  - Normalize day boundaries to `00:00:00 UTC`.
  - Keep timestamp policy consistent across ingest, compute, and storage.

### 5) Schema and module drift costs

Observed pain points:
- Import-path drift across refactors.
- Partially overlapping architectures and stale docs.
- Placeholder execution logic living beside production-oriented orchestration.
- Design implication:
  - Keep one canonical package layout.
  - Keep one canonical requirements baseline.
  - Gate unfinished execution modules behind explicit non-production interfaces.

## Avoid Carrying Forward (Known Debt)

- Mixed legacy import paths and stale test assumptions.
- Placeholder execution logic presented as production-ready behavior.
- Per-subnet transfer attribution shortcuts that treat transfers as global deltas.
- Floating-point monetary storage for financial accounting.

## Migration Guidance for New Build

- Reuse concepts, not implementations, where behavior was incomplete.
- Reuse only patterns that are both:
  - test-validated, and
  - aligned with the v1.3 requirements baseline.

## Minimum “Done Right” Checklist for New Modules

A module is accepted into the new baseline only if it:

- has deterministic identifiers and unique DB constraints,
- is safe under dry-run and fail-closed conditions,
- writes auditable records for decision and result,
- enforces whitelist and trust-boundary constraints where applicable,
- has at least one focused test proving current behavior.

## Source References Used

- `docs/LESSONS_LEARNED_RESTART.md`
- `docs/SECURITY_AUDIT.md`
- `docs/SAFETY_AND_RPC_IMPLEMENTATION.md`
- `src/main.py`
- `src/harvesting/accounting.py`
- `src/harvesting/harvest_decision.py`
