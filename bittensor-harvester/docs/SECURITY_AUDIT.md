# Security Audit - February 2, 2026

## Incident Report

**Event:** Unintended sell order execution at ~8:30 CET on Feb 1/2, 2026  
**Impact:** All holdings except 4 subnets were sold  
**Root Cause:** **NOT THIS CODEBASE** - External system triggered the transactions

## Investigation Findings

### ✅ This Codebase CANNOT Execute Transactions

1. **No Signing Credentials**
   - No private keys stored
   - No mnemonics stored  
   - No wallet seeds in code or `.env`
   - Cannot sign transactions

2. **Execution Safeguards in Place**
   - `harvest_execute.py` requires `ENABLE_HARVEST=true` (was NOT set)
   - `AlphaSwap.execute_swap()` has no real implementation
   - All execution returns "Not broadcast (dry-run)"
   - No code path exists to broadcast real transactions

3. **Taostats API is READ-ONLY**
   - Cannot execute swaps, sells, or transfers
   - Only provides data queries
   - No transaction execution endpoints

4. **No Scheduled Automation**
   - Windows Task Scheduler: No harvest/tao tasks found
   - No cron jobs
   - No automated execution scripts

### ⚠️ Likely External Causes

The sell orders came from **outside this codebase**. Check:

1. **Taostats Platform Settings**
   - Login to https://taostats.io
   - Check "Auto-harvest" or "Auto-compound" settings
   - Disable any automation features

2. **Wallet Auto-Features**
   - Check your wallet (Nova, Polkadot.js, etc.)
   - Look for auto-staking, auto-harvest, or auto-compound
   - Disable automated features

3. **Validator Management Tools**
   - Other validator automation running on your server
   - Third-party monitoring/management tools
   - Staking pool auto-compound features

4. **Exchange Integrations**
   - Auto-withdrawal from exchanges
   - Auto-convert/auto-sell features
   - Scheduled transfers

## Safety Measures Implemented (Feb 2, 2026)

### 1. Triple Kill Switch System

**config.py:**
```python
# ALL THREE must be true for ANY execution
EXECUTION_ENABLED = false  # Master kill switch (NEW)
TAOSTATS_ENABLED = false   # Taostats API disabled (NEW)
ENABLE_HARVEST = false     # Harvest execution disabled
```

### 2. Taostats API Disabled

- API key removed from `.env`
- `TAOSTATS_ENABLED=false` prevents usage even if key present
- Client now checks config before allowing requests

### 3. Execution Validation

`src/harvester.py` now requires:
- `dry_run=False` AND
- `ENABLE_HARVEST=true` AND  
- `EXECUTION_ENABLED=true` (NEW)

All three must be explicitly set for any broadcast.

### 4. .env Safety Defaults

```bash
# CRITICAL: Keep these FALSE
EXECUTION_ENABLED=false
TAOSTATS_ENABLED=false
ENABLE_HARVEST=false
```

## Current Safety Status

✅ **All execution BLOCKED**
✅ **Taostats API DISABLED**  
✅ **No private keys in codebase**
✅ **No scheduled tasks running**
✅ **All transactions return dry-run only**

## Recommended Actions

### Immediate (Do Now)

1. **Check Taostats Platform**
   ```
   - Go to https://taostats.io
   - Login with your account
   - Check Settings → Automation
   - Disable ALL auto-harvest/auto-compound features
   ```

2. **Check Your Wallet**
   ```
   - Open wallet (Nova/Polkadot.js/etc)
   - Settings → Advanced
   - Disable auto-staking, auto-harvest, auto-compound
   - Review recent transaction history for source
   ```

3. **Review Server/Validator**
   ```
   - Check what other scripts are running
   - Look for validator management tools
   - Check systemd services, cron jobs
   - Review recent command history
   ```

4. **Secure API Keys**
   ```
   - Regenerate Taostats API key
   - Regenerate Kraken API keys  
   - Update .env with new keys
   - Keep TAOSTATS_ENABLED=false until you identify the cause
   ```

### Short Term (This Week)

1. **Monitor Transaction History**
   - Check https://taostats.io daily for unexpected transactions
   - Review on-chain history via explorer
   - Set up alerts for large transfers

2. **Audit All Integrations**
   - List every tool/service with access to your validator
   - Revoke unnecessary API keys
   - Document what each integration does

3. **Enable 2FA Everywhere**
   - Taostats account
   - Exchanges (Kraken, etc.)
   - Any validator management platforms

### Long Term (Next Month)

1. **Implement Transaction Logging**
   - Log all API calls with timestamps
   - Track who/what accessed your accounts
   - Set up alerting for suspicious activity

2. **Separate Concerns**
   - Read-only monitoring (this codebase) ← Safe
   - Transaction execution (separate secure system) ← Requires explicit approval

3. **Regular Security Audits**
   - Monthly review of all integrations
   - Quarterly password/API key rotation
   - Annual security assessment

## How to Safely Use This Codebase

### Read-Only Mode (SAFE - Current State)
```bash
EXECUTION_ENABLED=false
TAOSTATS_ENABLED=false
ENABLE_HARVEST=false

# Run reports safely
python daily_emissions_report.py  # Uses RPC only, no Taostats
python earnings_report.py         # BLOCKED - Taostats disabled
```

### Monitoring Only (When Root Cause Found)
```bash
EXECUTION_ENABLED=false           # Still blocked
TAOSTATS_ENABLED=true             # Re-enable after regenerating key
ENABLE_HARVEST=false              # Still blocked

# View data only, no execution
python earnings_report.py         # Works - read-only
```

### Execution Mode (ONLY When Ready)
```bash
# ⚠️  DO NOT ENABLE UNTIL:
# 1. Root cause of unauthorized sells identified
# 2. All external automation disabled  
# 3. API keys regenerated
# 4. You understand exactly what will execute

EXECUTION_ENABLED=true
TAOSTATS_ENABLED=true
ENABLE_HARVEST=true

# Now harvest_execute.py can broadcast (if you confirm)
python harvest_execute.py
> Proceed to execute? (y/N): y  # Still requires manual confirmation
```

## Red Flags to Watch

🚨 **Stop immediately if you see:**
- Transactions you didn't initiate
- API rate limit errors when you're not running scripts
- Login attempts from unknown IPs
- API keys accessed from unfamiliar locations
- Balance changes at unexpected times (like 8:30 CET)

## Emergency Response

**If unauthorized transactions occur:**

1. **Immediately:**
   - Change all passwords
   - Regenerate ALL API keys
   - Disable all automation everywhere
   - Move funds to cold storage if possible

2. **Within 24h:**
   - Review all transaction history
   - Contact Taostats support
   - Check validator logs
   - Document everything for investigation

3. **Within 1 week:**
   - Forensic analysis of server/validator
   - Security audit of all integrations
   - Implement transaction alerts
   - Consider professional security review

## Contact & Support

- **Taostats:** https://taostats.io/support  
- **Bittensor Discord:** https://discord.gg/bittensor
- **This Codebase:** File issue at repository (if you find a security flaw)

---

**Last Updated:** February 2, 2026  
**Status:** All execution BLOCKED, investigation ongoing  
**Next Review:** After root cause identified
