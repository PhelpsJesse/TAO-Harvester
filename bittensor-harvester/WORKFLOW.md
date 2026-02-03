# Bittensor TAO Harvester - Simplified Workflow

## Overview

Track daily alpha emissions → Convert to TAO → Sell for USD → Withdraw to bank

**Data Source**: Taostats API (read-only, no RPC for balances)  
**Execution**: RPC for alpha→TAO swaps (not yet implemented)  
**Database**: SQLite for historical snapshots and tracking

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and fill in:
```bash
# Required
TAOSTATS_API_KEY=tao-your-api-key-here
HARVESTER_WALLET_ADDRESS=5YourWalletAddressHere

# Optional (for Kraken integration)
KRAKEN_API_KEY=your-kraken-api-key
KRAKEN_API_SECRET=your-kraken-secret
KRAKEN_DEPOSIT_ADDRESS=your-kraken-tao-deposit-address

# Safety switches (keep false until tested)
EXECUTION_ENABLED=false
TAOSTATS_ENABLED=true
RPC_ENABLED=false
```

### 3. Daily Workflow

**Step 1: Take Snapshot** (Run once per day)
```bash
python import_snapshot.py --transfers
```
- Fetches current alpha balances per subnet from Taostats
- Optionally pulls last 24h transfer history
- Stores in database (`alpha_snapshots` and `alpha_transfers` tables)
- Takes ~24 seconds (2 API calls with rate limiting)

**Step 2: Calculate Emissions** (View your earnings)
```bash
python calculate_emissions.py
```
- Compares today's snapshot with yesterday's
- Subtracts net transfers
- Shows emissions earned per subnet
- Formula: `emissions = today - yesterday - transfers`

**Step 3: Run Harvest Cycle** (Optional - when ready to harvest)
```bash
# Dry run (safe, no execution)
python -m src.main --dry-run

# Real execution (after testing on testnet)
python -m src.main
```

---

## Architecture

### Database Tables
- **alpha_snapshots** - Daily balance per subnet
- **alpha_transfers** - Transfer history for emission calculations
- **rewards** - Recorded emissions (income events)
- **harvests** - Alpha → TAO conversions
- **kraken_sales** - TAO → USD sales
- **withdrawals** - USD → bank withdrawals

### Key Scripts
- **import_snapshot.py** - Data collection from Taostats
- **calculate_emissions.py** - Emissions report from database
- **src/main.py** - Full harvest orchestrator
- **src/accounting.py** - Emissions calculation logic
- **src/executor.py** - Alpha → TAO swap execution (NOT IMPLEMENTED)
- **src/kraken.py** - Exchange operations
- **src/export.py** - Tax CSV export

### Data Flow
```
Taostats API
    ↓
import_snapshot.py → SQLite (alpha_snapshots)
    ↓
calculate_emissions.py → Delta calculation
    ↓
src/main.py → Check harvest threshold
    ↓
src/executor.py → Alpha → TAO swap (TODO)
    ↓
src/kraken.py → TAO → USD sale
    ↓
src/kraken.py → USD → Bank withdrawal
    ↓
src/export.py → Tax CSVs
```

---

## API Rate Limits

**Taostats Free Tier**: 5 requests/minute
- Built-in delay: 12 seconds between calls
- Daily usage: ~2 API calls (snapshot + transfers)
- Time: ~24 seconds total

---

## Safety Features

1. **EXECUTION_ENABLED** - Master kill switch (default: false)
2. **Dry-run mode** - Test without executing transactions
3. **Allowlist** - Only approved destination addresses
4. **Daily caps** - Limit harvest amounts per day
5. **Database state** - All actions recorded for audit

---

## Implementation Status

✅ **Complete**:
- Database schema with snapshots
- Taostats API integration (simplified, no fallbacks)
- Snapshot import script
- Emissions calculation from database
- Harvest policy enforcement
- Kraken integration (sell TAO, withdraw USD)
- Tax CSV export

⚠️ **TODO** (Critical):
- **Alpha → TAO swap execution** in `src/executor.py`
  - Requires RPC signing and extrinsic submission
  - Must verify extrinsic format on testnet first
  - See executor.py header for detailed requirements

🔒 **Disabled for Safety**:
- RPC execution (RPC_ENABLED=false)
- On-chain transactions (EXECUTION_ENABLED=false)

---

## Scheduling (Optional)

### Windows Task Scheduler
Create task to run daily:
```powershell
# At 9 AM daily
schtasks /create /tn "TAO Snapshot" /tr "python C:\path\to\import_snapshot.py --transfers" /sc daily /st 09:00
```

### Linux/Mac Cron
```bash
# At 9 AM daily
0 9 * * * cd /path/to/project && python import_snapshot.py --transfers
```

### Cloud Options
- AWS Lambda (scheduled)
- GitHub Actions (free for public repos)
- Azure Functions
- Google Cloud Functions

---

## Troubleshooting

**"No subnet balances found"**
- Wait 12 seconds between API calls (rate limit)
- Verify TAOSTATS_API_KEY in .env
- Check that wallet address has alpha holdings

**"No snapshots found for today"**
- Run `python import_snapshot.py` first
- Check database has data: Look for `harvester.db` file

**Rate limit errors (429)**
- Wait 60 seconds and try again
- Reduce frequency of API calls
- Consider upgrading Taostats plan

---

## Files Archived (Old Implementation)

Moved to `archive/` directory:
- `daily_earnings_all_subnets.py`
- `daily_emissions_report.py`
- `earnings_report.py`
- `earnings_summary.py`
- `summary_earnings.py`
- `test_accounting_endpoint.py`
- `subnet_balance_check.py`
- `snapshot_and_report.py`
- `monitor_wallet.py`
- `harvest_execute.py`

**Replacement**: Use `calculate_emissions.py` for all emissions reporting.

---

## Security Notes

1. **Never commit .env file** (contains API keys)
2. **Test on testnet first** before enabling execution
3. **Use hardware wallet** for signing if possible
4. **Start with small amounts** when testing swaps
5. **Monitor logs** for unexpected behavior
6. **Keep EXECUTION_ENABLED=false** until thoroughly tested

---

## Support

See detailed documentation:
- `TAOSTATS_INTEGRATION_SUMMARY.md` - Taostats API details
- `src/executor.py` - RPC implementation requirements
- `src/database.py` - Database schema reference

For questions, check the code comments or open an issue.
