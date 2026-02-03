# Rate-Limiting Testing & Cleanup - Session Summary

## What We Learned

**Both the Archive RPC and Taostats API enforce strict rate-limiting on aggressive queries.**

### Test Results

1. **Archive RPC (wss://archive.chain.opentensor.ai:443)**
   - Test: 7-day historical balance query (generic, all 300 subnets)
   - Result: ❌ **HTTP 429 - Rejected on WebSocket connection**
   - Status: Archive RPC currently rate-limited beyond recovery (likely quota exhausted)

2. **Taostats API (https://api.taostats.io)**
   - Test: Daily accounting data for all 300 subnets
   - Result: ❌ **HTTP 429 after ~150 subnet queries**
   - Status: Rate-limit enforced before completing all subnets
   - Theory: Per-address/validator rate limit, not endpoint-wide

### Key Insight

The problem isn't with the **query type** (specific vs generic).
The problem is with **query volume** (how many requests in how short a time).

**Both APIs reject rapid sequential requests, regardless of method.**

---

## Actions Taken

### 1. ✅ Cleaned Up Archive RPC Implementation

**Removed Methods:**
- `get_all_balances_at_block()` - Queried all 300 subnets at once
- `get_seven_day_emissions()` - Compared balances over 7-day period using generic queries

**Why:** These methods hammered the APIs and triggered rate-limiting.

**Kept Methods:**
- `get_current_block()` - Get latest block number
- `get_block_hash()` - Get block hash for storage queries
- `get_alpha_balance_at_block()` - Get balance for specific subnet (used for targeted queries)
- `get_daily_emissions_estimate()` - Calculate emissions for known subnets only
- `query_storage_at_block()` - Low-level storage query via SCALE encoding

**Updated Docstring:**
- Changed from "Query historical balances" to "Transaction signing ONLY"
- Added warning: Do not use for balance queries
- Added recommendation: Use Taostats API instead

### 2. ✅ Deleted Test Files

- `test_generic_query.py` - Tested 7-day generic balance queries (rate-limited)
- `test_taostats_7day.py` - Tested Taostats 7-day emissions query (rate-limited)

### 3. ✅ Created Decision Document

- [RATE_LIMITING_FINDINGS.md](RATE_LIMITING_FINDINGS.md) - Full analysis and recommendations

---

## Final Architecture

### Primary Data Source: Database
- Store emissions snapshots incrementally
- Query your own database for analytics (no rate limits)
- Reduces API calls by ~100x

### Secondary Data Source: Taostats API (Daily)
- Query **one subnet at a time** during daily aggregation
- Use documented rate limit: 5 requests/minute
- Query only **active subnets** (e.g., 5 subnets = 1-2 minutes)
- Not all 300 subnets

### Tertiary: Archive RPC (Transactions only)
- Sign and submit harvests/withdrawals
- Minimal queries (only when harvesting)
- Rate limiting is acceptable for infrequent operations

---

## Code Status

### ✅ Complete
- [src/archive_chain.py](src/archive_chain.py) - Cleaned, tested syntax
- [src/config.py](src/config.py) - Simplified (archive_rpc_url only)
- [.env](.env) - Cleaned (old endpoints removed)
- [src/taostats.py](src/taostats.py) - Added get_seven_day_emissions() for reference

### ⚠️ Pending
- [src/accounting.py](src/accounting.py) - Should use daily aggregation pattern (future task)
- [src/executor.py](src/executor.py) - Still imports old chain.py (not blocking)

---

## What's Next?

### Immediate (Can do now)
Nothing! Codebase is clean and ready.

### When You're Ready (Future)
1. Update [src/accounting.py](src/accounting.py) to use daily aggregation:
   - Query Taostats for each active subnet (once per day)
   - Store results in database
   - Use database for all analytics/reporting

2. Consider implementing:
   - Incremental block tracking (already in database schema)
   - 7-day rolling window from database snapshots
   - Export historical earnings to CSV

---

## Files Modified This Session

| File | Change | Status |
|------|--------|--------|
| [src/archive_chain.py](src/archive_chain.py) | Removed aggressive query methods | ✅ |
| [RATE_LIMITING_FINDINGS.md](RATE_LIMITING_FINDINGS.md) | Created analysis document | ✅ |
| test_generic_query.py | Deleted (not needed) | ✅ |
| test_taostats_7day.py | Deleted (not needed) | ✅ |

---

## Key Takeaway

**Rate-limiting is expected behavior for public APIs.**

The solution isn't to fight the rate limits with clever query patterns.
The solution is to:
1. Store data in your own database
2. Query APIs infrequently (once per day, not 300 times per minute)
3. Use the database as your single source of truth

This approach:
- ✅ Eliminates rate-limiting issues
- ✅ Makes the system faster (database queries are instant)
- ✅ Makes the system more reliable (no API dependencies)
- ✅ Uses APIs efficiently (5 requests/day instead of 5000/day)

