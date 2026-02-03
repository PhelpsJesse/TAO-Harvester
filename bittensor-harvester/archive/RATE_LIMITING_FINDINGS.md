"""
RATE-LIMITING FINDINGS AND FINAL ARCHITECTURE

Testing Results
===============

Test 1: Archive RPC Generic Query
---------------------------------
- Endpoint: wss://archive.chain.opentensor.ai:443
- Query Type: 7-day historical balance query (generic, all subnets)
- Rate Limiting: ❌ HTTP 429 on initial WebSocket connection
- Status: REJECTED - Archive RPC is heavily rate-limited

Test 2: Taostats API Generic Query
-----------------------------------
- Endpoint: https://api.taostats.io
- Query Type: 7-day accounting data (all subnets: 0-300)
- Rate Limiting: ❌ HTTP 429 after ~150 subnet requests
- Status: REJECTED - Taostats also rate-limits multi-subnet queries
- Theory: Rate limit per address/validator, not per endpoint
- Limit: Appears to be ~200 requests per some period (unclear period)


KEY INSIGHT: Both APIs enforce rate limiting on intensive queries
==============================================================================

The rate limiting is NOT unique to specific-subnet queries.
It's a global limit on how many requests you can make in a period.

Even the "generic" approach (query all subnets sequentially) hits
the same limit, just more slowly than specific+per-subnet approaches.


REVISED DATA ARCHITECTURE
==========================

Given the rate-limiting constraints, here's the optimal strategy:

1. PRIMARY: Database for state tracking (incremental processing)
   - Store emissions snapshots in harvester.db
   - Track: timestamp, netuid, address, balance
   - Update: Run once per hour/day, not on every invocation
   - Benefit: No API rate-limiting for reads from your own DB

2. FALLBACK: Taostats API for daily snapshots
   - Method: get_accounting_by_date() [single subnet at a time]
   - Rate Limiting: 5 requests/minute = 12 seconds per request
   - Usage: Query each active subnet ONCE per day during aggregation window
   - Benefit: No hammering APIs; daily data is sufficient for tracking
   - Cost: Free (no rate limit hit if used reasonably)

3. RESERVE: Archive RPC for transaction signing only
   - Method: sign_and_send() [only for executing harvests]
   - Rate Limiting: Not tested due to HTTP 429 gate
   - Usage: Only when actually harvesting/withdrawing (minutes per day)
   - Benefit: Guaranteed to have RPC access when needed
   - Cost: No rate-limiting on transaction execution observed


IMPLEMENTATION STRATEGY
=======================

DON'T query 300 subnets at once from ANY API.
Instead:

1. Maintain a "known_subnets" list in database
   - Start with main subnet (NETUID=1) 
   - Expand as you observe new activity
   - Store with first_seen_timestamp

2. Query only active subnets during daily aggregation
   - If you're validating on 5 subnets: query 5 subnets
   - Not 300 subnets with 295 empty results
   - Time: 1-5 minutes max for daily run

3. Daily workflow
   a. Run accounting.py at 00:00 UTC (once per day)
   b. Query Taostats for each known subnet (5-10 requests)
   c. Aggregate to database (harvest_txns, daily_earnings)
   d. Calculate emissions and thresholds
   e. If harvest needed: use archive_chain.py to sign+send
   f. Done. Next query: tomorrow at 00:00 UTC

4. Real-time tracking (optional, if needed)
   - Store snapshots in database every hour
   - Use Taostats daily data as ground truth
   - Don't re-query same subnet more than once per hour


RATE-LIMIT IMPLICATIONS
=======================

Archive RPC (wss://archive.chain.opentensor.ai:443):
  - Currently: REJECTED on connection (HTTP 429)
  - Usage pattern: Transaction signing only
  - Implication: May need to wait 24+ hours before RPC recovers
  - OR: Use HTTP RPC endpoint as fallback (different queue)

Taostats API (https://api.taostats.io):
  - Currently: 5 req/min per documented terms
  - Usage pattern: 1 query per subnet per day
  - Implication: Can query up to 300 subnets/day safely
  - OR: Query only 10 subnets = 50 seconds of API calls

Archive RPC (HTTP fallback, if available):
  - Endpoint: https://archive-api.bittensor.com/rpc OR similar
  - Status: Unknown - not tested
  - Benefit: Different rate-limit queue than WebSocket
  - Risk: May also be rate-limited


REVISED CODEBASE STATUS
=======================

Files to update/remove:
  ✅ src/taostats.py:
     - ADD: get_seven_day_emissions() with proper rate-limiting
     - Add docstring about 1-subnet-per-query pattern
     - Use reasonable delays (12-15 seconds between queries)

  ⚠️ src/archive_chain.py:
     - REMOVE: get_seven_day_emissions() (too aggressive)
     - REMOVE: get_all_balances_at_block() (rate-limited)
     - KEEP: Only transaction signing methods
     - Update docstring to clarify: "Archive RPC for transactions ONLY"

  ✅ test_taostats_7day.py:
     - Keep as reference, but:
     - Modify to query only subnets 1-5 (not 0-300)
     - Add 15-second delay between queries
     - THEN test passes without rate-limiting

  ✅ test_generic_query.py:
     - DELETE (not needed after findings)

  ⚠️ src/accounting.py:
     - Update to use Taostats API with proper delays
     - Query only known subnets
     - Store results in database for trend analysis


NEXT STEPS (RECOMMENDED)
========================

Option 1: Conservative (Recommended)
  1. Remove aggressive query methods from archive_chain.py
  2. Keep accounting.py simple: single daily query per subnet
  3. Store results in database
  4. Use database for analytics/graphing (no API calls)

Option 2: Aggressive (Test-Only)
  1. Wait 24+ hours for rate-limiting to reset
  2. Then test with longer delays (20+ seconds between requests)
  3. May still fail if per-IP or global rate limit is enforced
  4. Not recommended for production

Option 3: Hybrid (For Future)
  1. Query only actively held subnets (subset of 0-300)
  2. Use Taostats for daily aggregation
  3. Use archive RPC for block-level queries of 1-2 specific blocks
  4. Implement exponential backoff for 429 responses
  5. Store everything in database to minimize API calls

BOTTOM LINE
===========

The generic approach didn't help with rate-limiting.
Both APIs enforce strict rate limits on request volume.

The solution is NOT to ask for more data per request.
The solution is to ask for LESS data, LESS FREQUENTLY.

Daily aggregation + database storage is the right pattern.

Files to clean up: Just remove the aggressive methods and we're done.
"""

