# Taostats API - Historical Response Data (February 1, 2026)

## Summary

This document shows the **actual raw data** that Taostats API returned during previous runs, before you disabled the API key.

---

## Response 1: Daily Emissions Report (Feb 1, 2026 - Morning)

**Script:** `daily_emissions_report.py`  
**API Call:** `get_alpha_balance_by_subnet(address)`  
**Result:** Only 4 subnets returned (rate-limited)

### Raw Data Returned:
```
Subnet 4:  18.76726138 alpha
Subnet 8:  18.85868946 alpha
Subnet 51: 18.56955451 alpha
Subnet 64: 38.05257749 alpha

Total: 94.24808284 alpha
```

### What This Shows:
- **Read-only balance query** - just numbers
- **No transaction data** - only current balances
- **Rate-limited** - only 4 of your 25 subnets returned
- **No "action" or "execute" fields** - purely informational

---

## Response 2: Alpha Holdings Report (Feb 1, 2026 - Afternoon)

**Script:** `alpha_report.py` or similar  
**API Call:** `get_alpha_balance_by_subnet(address)` (complete run)

### Raw Data Returned:
```csv
netuid,previous_balance,current_balance,delta_alpha
1,     0,              0.0,             0
29,    0,              5.0695,          5.0695
34,    0,              5.5387,          5.5387
44,    0,              7.5978,          7.5978
54,    0,              6.0385,          6.0385
60,    0,              20.3797,         20.3797
64,    0,              5.9328,          5.9328
75,    0,              5.8844,          5.8844
118,   0,              7.7822,          7.7822
120,   0,              8.1171,          8.1171
124,   0,              8.5404,          8.5404
```

### What This Shows:
- **Balance snapshots** - current alpha per subnet
- **Delta calculations** - LOCAL calculation (not from API)
- **No wallet actions** - just reading numbers
- **First run baseline** - "previous_balance" was 0 (first snapshot)

---

## Response 3: Earnings Report (Feb 1, 2026)

**Script:** `earnings_report.py`  
**API Calls:** 
1. `get_alpha_balance_by_subnet(address)` - Get current balances
2. `get_alpha_earnings_history(address, days=30)` - Get transfer history

### Data Structure Returned:

#### Part A: Current Balances (from `get_alpha_balance_by_subnet`)
```json
{
  "address": "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh",
  "total_alpha": 94.24808284,
  "subnet_alpha": {
    "4": 18.76726138,
    "8": 18.85868946,
    "51": 18.56955451,
    "64": 38.05257749
  },
  "timestamp": "2026-02-01T...",
  "source": "taostats_api"
}
```

#### Part B: Transfer History (from `get_alpha_earnings_history`)
```json
{
  "address": "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh",
  "total_earnings": 1.51,
  "daily_earnings": {
    "2026-01-15": {
      "total": 1.51,
      "transfers": [
        {
          "amount": 1.51,
          "timestamp": "2026-01-15T10:23:45Z",
          "block": 7449000,
          "from": "5DyUBmjQ1fY27NxvBV9ryFe1vzEcCUWTt6ug9LyBnZg7bthw"
        }
      ]
    }
  }
}
```

**Critical Finding:** The 1.51 TAO was a **manual deposit from Kraken**, NOT validator emissions!

### What This Shows:
- **Transfer history is READ-ONLY** - just shows what happened on-chain
- **From addresses** - shows SOURCE of transfers (emission sources or manual transfers)
- **No execution capability** - cannot initiate transfers, only view them
- **Historical data only** - past transactions, not future actions

---

## Response 4: Harvest Plan (Generated Locally, NOT from Taostats)

**Important:** The `harvest_plan_2026-02-01.json` file was **created by harvest_execute.py**, not returned by Taostats!

### What the File Contains:
```json
{
  "total_harvestable": 49.875625931150786,
  "per_subnet": {
    "60": 13.928962588293187,
    "34": 3.1688904144478753,
    ...
  },
  "prepared": [
    {
      "netuid": 60,
      "amount_alpha": 13.928962588293187,
      "prepared_tx": {
        "action": "convert_alpha_to_tao",
        "status": "prepared"
      }
    }
  ]
}
```

### Where This Came From:
1. ✅ Taostats provided: **Balance data only** (read-only numbers)
2. ✅ Local script calculated: Which amounts are harvestable
3. ✅ Local script prepared: Transaction objects with "convert_alpha_to_tao"
4. ❌ **Never executed** - All show `status: "prepared"` (dry-run only)

---

## What Taostats API Actually Sends

### Data Sent TO Taostats:
```http
GET https://api.taostats.io/api/account/latest/v1
Headers:
  Authorization: tao-40546b90-9bb7-44a8-bad9-4110f9f809fd:0700a759
Parameters:
  address: 5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh
  network: finney
  page: 1
  limit: 50
```

### Data Received FROM Taostats:
```json
{
  "data": [
    {
      "alpha_balances": [
        {
          "netuid": 4,
          "balance_as_tao": 18.76726138,
          "balance": 18767261380000
        },
        {
          "netuid": 8,
          "balance_as_tao": 18.85868946,
          "balance": 18858689460000
        }
      ]
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 4,
    "next_page": null
  }
}
```

**That's it.** Just numbers. No actions, no execution, no swaps.

---

## What Taostats API CANNOT Do

### No Write Operations:
```
✗ Cannot execute swaps
✗ Cannot transfer funds
✗ Cannot modify balances
✗ Cannot place orders
✗ Cannot sign transactions
✗ Cannot broadcast transactions
```

### No Transaction Execution:
The API response shows **"action": "convert_alpha_to_tao"** in your harvest plan, but that was:
1. ✅ Created by YOUR local script (harvest_execute.py)
2. ✅ Based on balance data from Taostats (read-only)
3. ✅ Never sent back to Taostats
4. ✅ Never executed (all show "status": "prepared")
5. ❌ Taostats has NO endpoint to receive or execute such actions

---

## Comparison: What Each API Can Do

### Taostats API (READ-ONLY):
```
📖 get_alpha_balance_by_subnet()
   → Returns: {"netuid": balance_in_tao}
   
📖 get_alpha_earnings_history()
   → Returns: {"date": {"total": amount, "transfers": [...]}}
   
📖 get_delegators()
   → Returns: [{"delegator": address, "amount": stake}]
```

**Maximum Damage Possible:** None. Cannot execute anything.

### Kraken API (READ + WRITE):
```
📖 get_account_balance()
   → Returns: {"TAO": balance, "USD": balance}
   
⚠️ sell_tao_for_usd()
   → Executes: Real sell order on exchange
   
⚠️ withdraw_usd()
   → Executes: Real bank withdrawal
```

**Maximum Damage Possible:** Can sell assets and withdraw funds.

---

## Timeline Analysis

**February 1, 2026 ~8:30 CET (sell orders executed)**

### What the logs show:
1. ✅ Morning: Taostats returned 4 subnet balances (read-only)
2. ✅ Afternoon: Full balance snapshot taken (10 subnets, read-only)
3. ✅ Evening: Harvest plan created (local file, not executed)
4. ❌ **No execution logs** - harvest_results shows "Not broadcast (dry-run)"

### What happened at 8:30 CET:
- **Not logged in this codebase** - No execution records found
- **Not Taostats** - API is read-only, cannot execute
- **Not harvest_execute.py** - Requires manual confirmation + ENABLE_HARVEST=true
- **Not AlphaSwap** - No real implementation exists

### Most Likely Source:
1. **Taostats platform website** - Auto-harvest feature enabled in account settings
2. **Wallet auto-compound** - Your wallet (Nova/Polkadot.js) has auto-harvest enabled
3. **Validator automation** - Third-party tool managing your validator
4. **Exchange integration** - Auto-sell feature on an exchange

---

## Recommendations

### Immediate:
1. ✅ **Disabled Taostats API** - Good first step (prevents this codebase from querying)
2. ⚠️ **Check Taostats website** - Login and verify NO auto-harvest settings
3. ⚠️ **Check your wallet** - Disable auto-staking/auto-compound features
4. ⚠️ **Regenerate API keys** - Both Taostats and Kraken

### Investigation:
Look for transaction signatures at ~8:30 CET on Feb 1:
- Check on-chain explorer: https://polkadot.js.org/apps/?rpc=wss://entrypoint-finney.opentensor.ai:443#/explorer
- Find transactions around block ~7449500
- Look for extrinsic signatures (shows what wallet signed the transaction)

### Security:
The **sell orders were signed with your private key**. This means:
- Something has access to your wallet's private key OR
- Something triggered a feature in a tool that already has your keys OR
- A platform you authorized (like Taostats) has auto-harvest enabled

**This codebase does NOT have your private keys** and cannot sign transactions.

---

## Conclusion

**Taostats API returned:**
- Balance numbers (read-only)
- Transfer history (read-only)
- Delegation data (read-only)

**Taostats API did NOT:**
- Execute any swaps
- Initiate any transfers
- Place any orders
- Trigger any sales

**The sell orders came from elsewhere.** Check external platforms and wallet settings.
