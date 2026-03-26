# TAO Harvester - Complete Process Flow

> **Status: Legacy reference document** — describes the pre-v1.5 single-tier
> architecture. Steps 5–6 (Kraken TAO→USD sale, USD withdrawal) are NOT active
> workflow stages under v1.5. Under the current baseline, exchange trading
> (Tier 2) and withdrawals (Tier 3) are governed by
> `docs/REQUIREMENTS_SPEC_v1.5.md` Section 16. This document is retained for
> historical context only; do not use it as implementation guidance.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 1: DATA COLLECTION & TRACKING                    │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ build_alpha_history  │  1. Query current holdings (Taostats API)
   │      _db.py          │  2. Check last_updated timestamp in DB
   └──────────┬───────────┘  3. Pull daily history since last run
              │              4. Store directly in database (no CSV)
              │
              ▼
   ┌──────────────────────┐
   │   database.py        │  Tables:
   │  (harvest.db)        │  - alpha_balance_history (date, subnet, balance)
   └──────────────────────┘  - run_metadata (last_updated, status)

┌─────────────────────────────────────────────────────────────────────────┐
│              STEP 2: CALCULATE EMISSIONS & HARVEST DECISION              │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │   accounting.py      │  1. Query alpha_balance_history from DB
   └──────────┬───────────┘  2. Calculate day-over-day changes
              │              3. Compute total emissions (alpha earned)
              │              4. Convert alpha→TAO using current rates
              ▼
   ┌──────────────────────┐
   │    harvest.py        │  1. Check if emissions meet threshold
   │ (harvest_decision.py)│  2. Evaluate optimal timing
   └──────────┬───────────┘  3. Decide: harvest now or wait?
              │
              │ if harvest_ready == True
              ▼
   
┌─────────────────────────────────────────────────────────────────────────┐
│           STEP 3: HARVEST ALPHA → TAO (On-Chain Transaction)            │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ alpha_harvester.py   │  1. Query subnet pools for conversion rates
   │ (was executor.py)    │  2. Execute: Swap alpha → TAO on-chain
   └──────────┬───────────┘  3. Log transaction hash & fees
              │              4. Verify TAO received in wallet
              │ uses
              ▼
   ┌──────────────────────┐
   │    chain.py          │  RPC client for on-chain alpha→TAO swap
   │  (bittensor RPC)     │  (only used for this transaction)
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│            STEP 4: TRANSFER TAO TO KRAKEN (On-Chain Transfer)            │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ tao_transfer.py      │  1. Query TAO balance in wallet
   │  (NEW MODULE)        │  2. Send TAO to Kraken deposit address
   └──────────┬───────────┘  3. Log transaction hash & network fees
              │              4. Wait for Kraken confirmation
              │ uses
              ▼
   ┌──────────────────────┐
   │    chain.py          │  RPC client for TAO transfer transaction
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│              STEP 5: SELL TAO → USD (Kraken Exchange)                    │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ tao_harvester.py     │  1. Verify TAO balance in Kraken
   │  (NEW MODULE)        │  2. Execute: Sell TAO for USD
   └──────────┬───────────┘  3. Log trade details (price, fees, USD received)
              │              4. Verify USD balance updated
              │ uses
              ▼
   ┌──────────────────────┐
   │    kraken.py         │  Kraken API client for trading
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│        STEP 6: TRANSFER USD TO CHECKING (Kraken Withdrawal)              │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ usd_transfer.py      │  1. Query USD balance in Kraken
   │  (NEW MODULE)        │  2. Withdraw USD to linked checking account
   └──────────┬───────────┘  3. Log withdrawal details & fees
              │              4. Verify transfer completion
              │ uses
              ▼
   ┌──────────────────────┐
   │    kraken.py         │  Kraken API: withdraw funds
   │                      │  (checking account details from API)
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│           STEP 7: LOGGING & TAX DOCUMENTATION (All Steps)                │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ transaction_log.py   │  Logs every transaction with:
   │  (NEW MODULE)        │  - Timestamps
   └──────────┬───────────┘  - Transaction hashes
              │              - Amounts (alpha, TAO, USD)
              │              - Fees (network + exchange)
              │              - Exchange rates at execution
              ▼
   ┌──────────────────────┐
   │   database.py        │  Tables:
   │                      │  - transaction_log (all transactions)
   └──────────┬───────────┘  - fee_tracker (for tax reporting)
              │
              │ also exports
              ▼
   ┌──────────────────────┐
   │  export.py           │  Generates tax reports (CSV/PDF)
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                STEP 8: SECURITY - ENCRYPTED CONFIG (FUTURE)              │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │ secure_config.py     │  1. User enters decryption key at runtime
   │  (NEW MODULE)        │  2. Decrypt config (wallets, keys, thresholds)
   └──────────┬───────────┘  3. Hold in memory (never save to disk)
              │              4. Clear from memory after use
              │              5. Encrypted file stores:
              │                 - Wallet addresses
              │                 - Private keys/mnemonics
              ▼                 - API keys
   ┌──────────────────────┐  - Harvest thresholds
   │ config.encrypted     │  - Checking account info
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                         SUPPORTING MODULES                               │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │   taostats.py        │  Taostats API client (balance queries)
   └──────────────────────┘

   ┌──────────────────────┐
   │   config.py          │  .env configuration loader (temporary)
   └──────────────────────┘

   ┌──────────────────────┐
   │   wallet_manager.py  │  Wallet address management
   └──────────────────────┘

   ┌──────────────────────┐
   │   database.py        │  SQLite database interface
   └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                            MAIN ORCHESTRATOR                             │
└─────────────────────────────────────────────────────────────────────────┘

   ┌──────────────────────┐
   │     main.py          │  Coordinates full harvest workflow:
   └──────────────────────┘  1. build_alpha_history_db (incremental update)
                             2. accounting (calculate emissions)
                             3. harvest_decision (check threshold)
                             4. alpha_harvester (alpha → TAO)
                             5. tao_transfer (TAO → Kraken)
                             6. tao_harvester (TAO → USD)
                             7. usd_transfer (USD → checking)
                             8. transaction_log (record everything)


═══════════════════════════════════════════════════════════════════════════

COMPLETE END-TO-END WORKFLOW:

┌─────────────┐     ┌──────────┐     ┌────────┐     ┌─────────────┐
│   Alpha     │────▶│   TAO    │────▶│ Kraken │────▶│  Checking   │
│ (On-Chain)  │     │(On-Chain)│     │  (USD) │     │  Account    │
└─────────────┘     └──────────┘     └────────┘     └─────────────┘
      │                   │                │                │
      │ Tx Hash          │ Tx Hash        │ Trade ID       │ Transfer ID
      │ Network Fee      │ Network Fee    │ Kraken Fee     │ Wire Fee
      │                  │                │                │
      └──────────────────┴────────────────┴────────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ transaction_log  │ ← All metadata for tax reporting
                  │    (database)    │
                  └──────────────────┘

═══════════════════════════════════════════════════════════════════════════

MODULE RENAMING & NEW MODULES:

RENAMED:
  executor.py       →  alpha_harvester.py   (alpha → TAO on-chain)
  harvest.py        →  harvest_decision.py  (decision logic only)

NEW MODULES NEEDED:
  tao_transfer.py      (TAO → Kraken wallet)
  tao_harvester.py     (TAO → USD via Kraken)
  usd_transfer.py      (USD → checking account)
  transaction_log.py   (logging & metadata)
  secure_config.py     (encrypted config, future)

EXISTING (unchanged):
  build_alpha_history_db.py  (data collection)
  accounting.py              (emissions calculation)
  chain.py                   (on-chain transactions only)
  kraken.py                  (Kraken API client)
  database.py                (SQLite interface)
  export.py                  (tax reports)
  taostats.py                (balance queries)
  config.py                  (temp .env loader)
  wallet_manager.py          (wallet management)

═══════════════════════════════════════════════════════════════════════════

CURRENT STATE:
✓ Step 1: Data collection (build_alpha_history_db.py running now)
✓ Database schema: alpha_balance_history table
⚠ Step 2: accounting.py needs DB integration
⚠ Step 3: Rename executor.py → alpha_harvester.py
✗ Step 4: Create tao_transfer.py
✗ Step 5: Create tao_harvester.py (Kraken trading)
✗ Step 6: Create usd_transfer.py (Kraken withdrawal)
✗ Step 7: Create transaction_log.py
✗ Step 8: Create secure_config.py (future)

IMMEDIATE NEXT STEPS:
1. ✓ Complete alpha history DB build (in progress)
2. Update accounting.py to use alpha_balance_history table
3. Rename executor.py → alpha_harvester.py
4. Rename harvest.py → harvest_decision.py
5. Create new modules (tao_transfer, tao_harvester, usd_transfer)
6. Implement transaction_log.py
7. Test end-to-end workflow in DRY RUN mode

═══════════════════════════════════════════════════════════════════════════
```
