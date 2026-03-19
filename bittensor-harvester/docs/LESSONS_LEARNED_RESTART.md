# Lessons Learned (Codebase Review for Fresh Restart)

Date: 2026-03-10  
Scope reviewed: `src/`, `tests/`, `docs/`, and top-level project structure.

---

## Executive Summary

The current codebase has a strong **safety-first intention** and useful building blocks (SQLite persistence, policy/cap concepts, CSV export shape), but it has accumulated architectural drift:

- multiple partially overlapping designs (RPC-first vs Taostats-first)
- inconsistent module paths/imports after refactors
- docs that no longer match runtime reality
- execution paths still mostly stubbed

For a clean restart, the best path is:

1. keep only proven primitives (DB patterns, policy ideas, CSV contract),
2. define one canonical architecture around **daily state-based accounting**,
3. rebuild execution modules behind strict interfaces and kill switches,
4. reintroduce chain/exchange integrations only after read-only accounting is stable.

---

## What Worked Well (Keep)

1. **Risk controls as first-class concepts**
   - Per-run/per-day caps exist.
   - Destination allowlist concept exists.
   - Dry-run defaults are present.

2. **State persistence with SQLite**
   - `runs`, rewards/harvest/sales/withdrawal tables are aligned with automation workflows.
   - Local-only DB suits desktop and future Raspberry Pi operation.

3. **Tax export intent is correct**
   - Separate reward/harvest/sales/withdrawal exports map to tax treatment.
   - CSV format is straightforward for CPA tooling.

4. **Daily snapshot accounting direction**
   - The delta model (today - yesterday - transfers) is operationally simpler and robust for once-daily runs.

5. **Unattended resiliency must be a first-class requirement**
   - OpenClaw automation cannot rely on optimistic retry behavior alone.
   - High-fanout backfill paths must have bounded retries, deterministic fail-closed outcomes, and explicit manual-retry offramps.
   - Partial upstream data or rate-limit conditions must never be surfaced as successful harvestable output.

---

## Main Problems Observed (Do Not Carry Forward)

1. **Import/path drift from reorganization**
   - Tests and modules reference old paths (example: `src.config`, `src.chain`, `src.export`) while current modules are under `src.utils`, `src.trading`, etc.
   - Result: hidden breakage and reduced confidence.

2. **Mixed architecture in code and docs**
   - Some files claim Taostats-primary; others claim RPC-primary.
   - “Primary source” changes across docs without one canonical decision record.

3. **Execution module not production-ready**
   - On-chain swap/submit logic is stubbed (`_submit_extrinsic` not implemented).
   - Preflight checks use placeholders/mocks.

4. **Schema sprawl**
   - Database contains many tables from multiple iterations (some overlapping responsibilities).
   - Increases complexity and maintenance burden for a daily-run system.

5. **Config model inconsistency**
   - Environment variables, JSON overrides, and runtime assumptions are mixed.
   - Some defaults (placeholder addresses) can mask misconfiguration.

6. **Test mismatch with current code**
   - Test fixtures instantiate classes with outdated signatures/imports.
   - Tests no longer validate the current system behavior end-to-end.

7. **Rate-limit resilience was under-specified**
   - Retry logic existed conceptually, but unattended runtime behavior under repeated `429` responses was not defined tightly enough.
   - Requirement and checklist language must explicitly require bounded retries, persisted run outcome states, and debug offramps.

---

## Reuse vs Rewrite Matrix

### Safe to Reuse (with small cleanup)

- `src/utils/database.py` patterns (connection handling, upserts, config state helpers)  
  Reuse idea, but prune schema to core MVP tables.
- `src/harvesting/harvest_decision.py` policy shape (threshold + caps + allowlist)  
  Keep concepts, refactor to pure policy module without side effects.
- `src/trading/export.py` CSV separation by taxable category  
  Keep output contracts; normalize column names and UTC timestamps.

### Reuse Carefully (selective extraction only)

- `src/harvesting/accounting.py`  
  Keep delta formulas and ledger logic; rewrite transfer attribution and idempotency.
- `src/trading/kraken.py`  
  Keep client wrapper idea; rewrite around strict “no-op unless enabled” guards and clearer order/withdraw policies.

### Rewrite from Scratch

- `src/utils/chain.py`  
  Too much legacy coupling and mixed responsibilities; replace with small, explicit adapters.
- `src/harvesting/alpha_harvester.py` execution path  
  Keep interface intent only; rebuild with explicit dry-run, signing boundary, and deterministic audit logging.
- Most architectural docs that conflict  
  Replace with one canonical architecture + one operations runbook.

---

## Design Decisions to Lock Early in the New Build

1. **One accounting truth path**
   - Prefer on-chain state snapshots (daily), event-based only where truly available.
   - No hourly polling assumptions.

2. **Single orchestrator contract**
   - Run is idempotent and state-based (cursor + date windows + unique keys).
   - A missed day should backfill naturally from stored state.

3. **Strict separation of concerns**
   - `ingest` (read-only)
   - `accounting` (compute + ledger)
   - `planner` (policy)
   - `executor_chain` (stub then real)
   - `executor_exchange` (stub then real)
   - `export_tax`

4. **Security boundary model**
   - All execution disabled by default.
   - Multiple explicit flags required to perform value-moving actions.
   - Allowlist and hard caps always enforced server-side in code.

5. **MVP schema only**
   - Keep core tables required by your prompt and add others only when a feature is live.

6. **Automation must be debuggable by design**
   - Every unattended run should leave enough persisted state and logs to explain whether it completed, deferred, or requires manual reconciliation.
   - Operator guidance should be explicit, not inferred from stack traces.

---

## Practical Lessons for the Next Prompt

When restarting with a new prompt, include these constraints explicitly:

1. “No legacy imports; all modules must map to one canonical package layout.”
2. “No execution implementation beyond safe stubs in phase 1.”
3. “All actions must be idempotent with unique DB constraints.”
4. “Tax CSV columns fixed from day 1; backward-compatible changes only.”
5. “Docs generated only from current implementation, not aspirational states.”

---

## Suggested Minimal Carry-Over Artifacts

Copy forward only:

- policy constants and thresholds (after manual review)
- CSV header contracts from exporter
- tested DB helper idioms (not full schema)
- security checklists from docs (kill switches, allowlists, caps)

Do **not** copy forward:

- mixed/legacy chain client code
- stale tests with old import paths
- conflicting architecture documents

---

## If You Reuse Pieces Later

Gate each reused module with this checklist:

1. Is it import-path clean in the new package layout?
2. Does it run read-only unless explicitly enabled?
3. Is behavior idempotent across reruns?
4. Does DB schema for it have unique constraints preventing duplicates?
5. Does at least one test verify current behavior (not historical assumptions)?

If any answer is “no,” rewrite that module instead of migrating it.
