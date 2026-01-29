# Implementation Guide: Bittensor TAO Harvester

## Overview

This guide helps you move from the current prototype (with mocked APIs) to a production system with real Substrate chain interactions and Kraken trading.

## Current State

✅ **Completed:**
- SQLite schema for persistent state
- Harvest policy enforcement (50% fraction, thresholds, caps)
- CSV export for tax reporting
- Modular architecture (accounting, executor, export, etc.)
- Comprehensive test suite
- Dry-run support for safe testing

🔲 **Stubbed (TODO):**
- Substrate RPC chain integration
- Extrinsic signing & submission
- Kraken API integration
- Wallet key management

---

## Step 1: Substrate Chain Integration

### Current Stubs in `src/chain.py`

Implement real RPC calls or use the `substrate-interface` library. Use state snapshots to compute deltas by querying historical storage at block hashes.

### Step 2: Extrinsic Signing & Submission

Use `substrate-interface` Keypair to sign and submit extrinsics. Prefer secure key storage (keyring/HSM) and always test with `dry_run=True`.

### Step 3: Kraken Integration

Implement Kraken or `ccxt` client in `src/kraken.py`. Gate trading and withdrawals behind config flags and weekly/threshold limits.

### Step 4: Wallet Key Management

Desktop: use `keyring` or `.env` with strict file permissions. Autonomous: prefer environment-injected secrets or HSM.

### Step 5: Testing the Real Implementation

Develop unit tests for each new function and a dry-run integration to validate behavior before enabling live actions.

### Step 6: Deployment

Use cron / Task Scheduler for daily runs. On Raspberry Pi, inject secrets via environment and ensure limited network access.

---

More detail and example code snippets are available in the main project README and `src` docstrings. Keep security first: never commit `.env` or keys.
