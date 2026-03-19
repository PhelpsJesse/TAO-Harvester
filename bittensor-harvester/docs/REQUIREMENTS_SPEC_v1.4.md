# TAO Harvester System Requirements Specification

Version: 1.4  
Status: Architecture Baseline Draft  
Baseline Date: 2026-03-17

## Configuration Control Statement

This document is the active configuration-control baseline for implementation work in this repository.

Rules for forward changes:
- Architecture and implementation MUST conform to this specification unless a requirement change is recorded first.
- Requirement changes MUST be documented before code behavior is changed.
- If implementation and spec conflict, the spec governs until updated.

---

## Source Baseline (User-Provided v1.3, Amended to v1.4)

The following content is adopted as the active baseline specification.

====================================================================  
TAO HARVESTER SYSTEM REQUIREMENTS SPECIFICATION  
Version: 1.4  
Status: Architecture Baseline Draft  
====================================================================


1. PURPOSE

This document defines the normative functional, operational, and security
requirements for the TAO Harvester System.

The system identifies staking-generated alpha earnings within the
Bittensor ecosystem and converts a configurable portion of those
earnings into TAO while ensuring:

• Alpha principal is never harvested
• All actions are auditable
• Financial execution boundaries are enforced
• System behavior is deterministic

This document acts as the baseline specification controlling system
architecture and implementation decisions.



2. NORMATIVE LANGUAGE

The following terms have specific meanings:

MUST
A mandatory requirement.

SHOULD
A recommended requirement.

MAY
An optional capability.



3. SYSTEM OBJECTIVE

The system MUST:

1. Identify alpha earnings generated from subnet staking.
2. Ensure that only staking-generated alpha is harvested.
3. Convert a configurable portion of those earnings into TAO.
4. Maintain a durable and auditable record of balances and actions.
5. Separate low-risk automation from high-risk signing operations.
6. Operate resiliently in unattended Tier 1 automation environments.

The system SHOULD support modular external interfaces to allow future
changes to wallet providers, data sources, or exchanges.



4. EXTERNAL SYSTEMS

The system MAY interact with the following external components.

Taostats API
Primary analytics data source used for wallet balances, transfers,
exchanges, and subnet information.

Taostats HTML
Fallback data source if the API becomes unavailable.

Bittensor Chain RPC
Direct blockchain access used for verifying wallet state and subnet
information.

Nova Wallet
User wallet containing staking balances and signing keys.

Kraken Exchange
Optional exchange integration for future automated trading.

OpenClaw
VPS runtime environment used for low-risk automated tasks.



5. GLOSSARY

Alpha Principal
Alpha originally staked by the user.

Alpha Earnings
Alpha generated through subnet staking emissions.

Harvest
Conversion of alpha earnings into TAO.

TAO Buffer
Accumulated TAO awaiting transfer.

Transfer Batch
A grouped transfer of TAO scheduled for execution.

Execution Event
Any financial action executed by the system.

Reconciliation Window
Time interval used to compute earnings.



6. FUNCTIONAL REQUIREMENTS

FR-001
The system MUST ingest wallet balances for all configured subnets.

FR-002
The system MUST ingest relevant activity events including transfers,
exchanges, and staking events.

FR-003
The system MUST calculate estimated alpha earnings for each subnet.

FR-004
The system MUST ensure that only staking-generated alpha earnings are
eligible for harvesting.

FR-005
The system MUST support configurable harvest percentages.

FR-006
The system MUST persist snapshots, reconciliations, and execution
events in a database.

FR-007
The system MUST support generation of TAO transfer batches.

FR-008
The system MUST support manual chain signing through a local CLI.

FR-009
The system SHOULD support modular exchange integration.

FR-010
All reconciliation and harvesting calculations MUST be performed on
a subnet-by-subnet basis.



7. RECONCILIATION ALGORITHM

Alpha earnings MUST be calculated using the following model.

raw_alpha_delta =
alpha_balance_end − alpha_balance_start

trade_adjustment =
sum(alpha changes caused by user trades)

transfer_adjustment =
sum(alpha changes caused by transfers)

estimated_staking_alpha =
raw_alpha_delta − trade_adjustment − transfer_adjustment

Constraint:

estimated_staking_alpha ≥ 0

If this constraint is violated:

• reconciliation MUST be flagged anomalous
• harvest execution MUST be blocked

Harvestable alpha:

harvestable_alpha =
estimated_staking_alpha × harvest_percentage



8. EDGE CASE HANDLING

The system MUST account for:

• delayed Taostats updates
• manual transfers
• subnet migrations
• partial-day runs
• negative balance deltas
• upstream API rate limits
• partial upstream data availability
• unattended runtime interruptions

If reconciliation confidence falls below threshold,
harvesting MUST be blocked.



9. IDEMPOTENCY REQUIREMENTS

All workflows MUST be idempotent.

Deterministic identifiers MUST be used.

Run ID

hash(wallet_address + run_timestamp)

Snapshot Key

(wallet_address, subnet_id, snapshot_timestamp)

Harvest Plan ID

hash(run_id + subnet_id)

Transfer Batch ID

hash(wallet_address + tao_amount + creation_timestamp)

Execution Event ID

hash(plan_id + execution_timestamp)

Duplicate executions MUST be ignored.



10. TIME SEMANTICS

Canonical timezone:

UTC

Daily boundary:

00:00:00 UTC

All timestamps MUST be stored using ISO-8601 UTC format.



11. PRECISION POLICY

Alpha precision

12 decimal places

TAO precision

9 decimal places

All financial values MUST use fixed-precision decimal types.

Floating-point storage MUST NOT be used.



12. DATA SOURCE PRECEDENCE

If multiple data sources provide conflicting information, the system
MUST prioritize sources as follows:

1. Taostats API
2. Bittensor RPC
3. Taostats HTML

If discrepancies exceed tolerance thresholds, reconciliation MUST be
flagged as anomalous.



13. RUN RECOVERY

Reconciliation window:

previous_run_timestamp → current_run_timestamp

Maximum automated backfill window:

7 days

If exceeded:

Manual reconciliation is required.

Partial runs MUST resume from the last completed workflow stage.

Tier 1 unattended runs MUST either:

• complete successfully
• fail closed with explicit machine-readable reason
• classify the run as requiring manual retry or manual reconciliation

Runs MUST NOT continue indefinitely under repeated upstream rate-limit
conditions.



14. FAIL-CLOSED EXECUTION RULES

Execution MUST be blocked if any of the following occur:

• reconciliation confidence below threshold
• missing snapshot data
• negative earnings detected
• whitelist validation failure
• wallet signing unavailable
• transfer destination not whitelisted
• upstream data required for reconciliation is unavailable or incomplete
• historical backfill exceeds safe automated retry/rate budget

Dry-run mode MAY continue despite these conditions.



15. WHITELIST POLICY

All transfers MUST use an address whitelist.

Source of truth:

config/whitelist.yaml

Example configuration:

allowed_addresses:
  - kraken_tao_deposit_address

Validation rules:

• address prefix validation
• checksum verification

Emergency revoke MUST immediately disable transfer execution.



16. TRUST BOUNDARIES

Tier 1 — Low Risk

Runs on VPS (OpenClaw).

Responsibilities:

• data ingestion
• reconciliation
• harvest planning
• database persistence
• health/status reporting for unattended runs
• emission of retry/defer/manual-intervention outcomes

Tier 2 — Medium Risk

Optional exchange execution.

Responsibilities:

• exchange trading

Tier 3 — High Risk

Runs on trusted local machine.

Responsibilities:

• chain signing
• TAO transfers
• exchange withdrawals
• fiat withdrawals



17. AUDIT LOGGING

Each execution event MUST record:

timestamp
actor
module
input parameters
result
transaction hash
error messages
record integrity hash

Where applicable, run diagnostics SHOULD also record:

retry count
upstream rate-limit status
defer/fail-closed reason
required operator action

Audit records MUST be immutable.



18. DATABASE REQUIREMENTS

The system MUST maintain the following tables:

run_history
subnet_snapshots
subnet_reconciliation
harvest_plans
harvest_executions
transfer_batches

Backups MUST occur daily.

Minimum retention SHOULD be 30 days.



19. STATE MACHINES

Run Status

CREATED
SNAPSHOT_COMPLETE
RECONCILIATION_COMPLETE
HARVEST_PLAN_COMPLETE
TRANSFER_BATCH_CREATED
COMPLETE
FAILED


Harvest Plan Status

PLANNED
SKIPPED
SUBMITTED
FILLED
FAILED


Transfer Batch Status

CREATED
AWAITING_SIGNATURE
SUBMITTED
CONFIRMED
FAILED



20. TEST STRATEGY

Testing MUST occur at four levels.

Unit Tests
Validate individual modules.

Subsystem Tests
Validate reconciliation and harvesting logic.

System Tests
Validate complete workflow.

Dry-Run Validation
Validate behavior using live wallet data without executing transfers.



21. SERVICE LEVEL OBJECTIVES

Maximum daily run time:

≤ 5 minutes

Retry attempts:

≤ 3

Failure conditions MUST trigger alerts.

For unattended Tier 1 runs on OpenClaw:

• retries MUST be bounded
• failure handling MUST be deterministic
• partial plans MUST NOT be emitted as successful outputs
• a debug offramp MUST exist via logs, persisted run state, and explicit rerun/manual-reconcile guidance



22. ACCEPTANCE CRITERIA MATRIX

FR-001
Wallet balances successfully retrieved.

FR-003
Reconciliation results produced for each subnet.

FR-004
Alpha principal is never harvested.

FR-006
Database entries created for each run.

FR-008
Signing requires manual password entry.

Whitelist enforcement verified.



23. VERSIONING RULES

Specification version format:

MAJOR.MINOR

MAJOR change
Requirement modification.

MINOR change
Architecture clarification.



24. CHANGE CONTROL

All proposed modifications MUST be classified as:

Implementation Change
Architecture Change
Requirement Change

Requirement changes MUST update this document prior to
implementation.



25. OPEN QUESTIONS

Nova wallet API capabilities
Optimal reconciliation confidence threshold
RPC endpoint reliability
Exchange integration timeline


END OF DOCUMENT
Version 1.4 Draft