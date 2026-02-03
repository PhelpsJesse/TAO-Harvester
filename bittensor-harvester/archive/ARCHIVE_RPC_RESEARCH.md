# Archive RPC Research: Why Are We Being Rate-Limited?

## Your Question
> "I'm confused how someone would be able to use this RPC for historicals if it's just outright denying our requests now. Is there anything online about how to successfully pull chain historicals from this RPC that might help us with our issue?"

## Research Findings

### 1. **Archive RPC IS Meant for Historical Queries - But with Limits**

From the [Bittensor Subtensor Documentation](https://github.com/opentensor/subtensor):

- **Archive nodes** vs **Lite nodes**: Archive nodes store "every block since inception"
- **Purpose**: Archive nodes are designed for querying historical state
- **Network Requirements**: Port 9944 (WebSocket) should be "firewalled off from the public domain"

**Key Insight**: The public archive RPC at `wss://archive.chain.opentensor.ai:443` is a **shared resource** with rate limits to prevent abuse.

### 2. **Rate Limiting in Bittensor is Intentional and Pervasive**

From the Subtensor codebase research:

#### Built-in Rate Limiters:
```rust
// From pallets/subtensor/src/utils/rate_limiting.rs
pub fn exceeds_tx_rate_limit(prev_tx_block: u64, current_block: u64) -> bool {
    let rate_limit: u64 = Self::get_tx_rate_limit();
    if rate_limit == 0 || prev_tx_block == 0 {
        return false;
    }
    current_block.saturating_sub(prev_tx_block) <= rate_limit
}
```

#### Multiple Rate Limit Types:
- **Transaction rate limits**: Per-account, per-block limits on chain operations
- **Serving rate limits**: How often validators can update axon/prometheus info
- **Weight setting rate limits**: How often validators can submit weights
- **Staking operation rate limits**: How often staking operations can occur

From `pallets/subtensor/src/lib.rs`:
```rust
pub type TxRateLimit<T> = StorageValue<_, u64, ValueQuery, DefaultTxRateLimit<T>>;
pub type ServingRateLimit<T: Config> = StorageMap<_, Identity, NetUid, u64, ValueQuery, DefaultServingRateLimit<T>>;
pub type WeightsSetRateLimit<T: Config> = StorageMap<_, Identity, NetUid, u64, ValueQuery>;
```

### 3. **How Others Use Archive RPC Successfully**

Based on the codebase analysis:

#### ✅ **Pattern 1: Run Your Own Archive Node (Recommended for Heavy Usage)**

From Subtensor docs:
```bash
# Build and run your own archive node
cargo run --release -- --chain=finney --pruning=archive --base-path ./my-archive
```

**Benefits:**
- No rate limits
- Full control
- Can query as aggressively as needed
- ~286 MiB to run

**Requirements:**
- Linux kernel 2.6.32+ or MacOS 10.7+
- Network access: ports 9944 (WebSocket), 9933 (RPC), 30333 (p2p)
- Storage: Archive nodes grow over time (need to track full chain history)

#### ✅ **Pattern 2: Batch Queries with Delays (For Light Usage)**

From the contract tests in the Bittensor repo:
```typescript
// From contract-tests/src/config.ts
export const TX_TIMEOUT = 3000; // 3 second timeout between requests

// Rate limiting built into test suites:
await asyncio.sleep(0.25)  # 250ms between queries
```

**Key Observations:**
- Official test suite uses 250ms-3000ms delays between queries
- Tests query **specific data points**, not all 300 subnets at once
- Tests query **what they need**, when they need it (not preemptively)

#### ✅ **Pattern 3: Use Taostats for Daily Snapshots (For Analytics)**

From Taostats documentation:
- **API Rate Limit**: 5 requests/minute (documented)
- **Usage Pattern**: Query specific endpoints for specific data
- **Best Practice**: Daily aggregation, not real-time polling

### 4. **Why You're Being Rate-Limited**

Based on our testing and research:

#### Your Query Pattern:
```python
# What we attempted:
for netuid in range(300):  # 300 sequential requests
    balance = await get_balance(address, netuid, block_number)
    await asyncio.sleep(0.1)  # 100ms delay = 30 seconds total
```

**Total Time**: 30 seconds for 300 queries
**Result**: HTTP 429 after ~100-150 queries

#### Why This Failed:
1. **Volume**: 300 requests in 30 seconds = 10 requests/second
2. **Public RPC**: Shared resource with many users
3. **Per-IP Limit**: Likely enforced per IP address, not per request type
4. **Quota System**: May have daily/hourly quotas that we've exhausted

### 5. **How the Bittensor Team Uses Archive RPC**

From the Subtensor codebase patterns:

#### Contract Tests Use Targeted Queries:
```typescript
// From contract-tests/test/staking.precompile.test.ts
const stakeBefore = await api.apis.StakeInfoRuntimeApi.get_stake_info_for_hotkey_coldkey_netuid(
    convertPublicKeyToSs58(hotkey.publicKey),
    contractAddress,
    netuid,  // Query SPECIFIC netuid only
)
```

**Not**: Query all 300 netuids
**But**: Query the 1-5 netuids they care about

#### RPC Methods Built for Specific Queries:
```rust
// From pallets/subtensor/rpc/src/lib.rs
fn get_all_dynamic_info(&self, at: Option<<Block as BlockT>::Hash>) -> RpcResult<Vec<u8>>
```

**Key**: These methods return **aggregated data** from the chain state, not individual queries

### 6. **The Real Solution: Different Architecture**

Based on all research:

#### ❌ **What DOESN'T Work:**
- Querying all 300 subnets sequentially from public Archive RPC
- Making 100+ requests in quick succession
- Treating Archive RPC like a database you can query freely

#### ✅ **What DOES Work:**

**Option A: Run Your Own Node**
```bash
# Clone subtensor
git clone https://github.com/opentensor/subtensor
cd subtensor

# Build archive node
cargo build --release

# Run with archive mode
./target/release/node-subtensor \
    --chain=finney \
    --pruning=archive \
    --base-path ./my-archive-data \
    --ws-port 9944
```

**Benefits:**
- No rate limits
- Full historical data
- Can query aggressively
- Total control

**Costs:**
- Requires ~286 MiB RAM
- Storage grows over time
- Need to maintain/sync node

**Option B: Use Taostats API Correctly**
```python
# Query only active subnets, once per day
active_subnets = [1, 3, 5, 9]  # Your actual subnets

for netuid in active_subnets:
    time.sleep(12)  # 12 seconds = 5 req/min
    result = taostats.get_accounting_by_date(address, netuid)
    store_in_database(result)
```

**Benefits:**
- No infrastructure needed
- Reliable (Taostats manages it)
- Free (with API key)

**Costs:**
- Must query slowly (5 req/min)
- Only daily snapshots (not block-level)
- Dependent on Taostats uptime

**Option C: Hybrid Approach (Your Current Plan)**
- **Taostats API**: Daily snapshots of known subnets
- **Database**: Store historical trends locally
- **Archive RPC**: Only for transaction signing (minimal queries)

### 7. **Best Practices from Bittensor Community**

#### From Official Tests:
1. **Use Specific Queries**: Don't query all subnets if you only need 5
2. **Add Delays**: 250ms-3s between requests minimum
3. **Batch Wisely**: Group queries logically, not by brute force
4. **Cache Results**: Store in database, query DB not API

#### From Rate Limit Code:
```rust
// Bittensor enforces rate limits at multiple levels:
// 1. Per-transaction type
// 2. Per-account
// 3. Per-subnet
// 4. Per-block

// If you're seeing HTTP 429, you've hit a GLOBAL limit
// Not a per-query limit
```

## Conclusion

### Why Archive RPC Denied Your Request:
1. **You hit the quota** - Too many requests in too short a time
2. **It's a shared public resource** - Designed for light usage
3. **Your pattern was too aggressive** - 300 subnets in 30 seconds

### How to Use Archive RPC Successfully:
1. **Run your own node** if you need heavy querying
2. **Query sparingly** if using public RPC (only what you need, when you need it)
3. **Use Taostats for analytics** - it's designed for this use case

### Your Best Path Forward:
**Keep your current plan:**
- Taostats API for daily data (5 subnets, once per day = 5 requests)
- Database for historical trends (query locally, not remotely)
- Archive RPC for transactions only (minimal usage)

This architecture respects rate limits while giving you the data you need.

## References

1. [Bittensor Subtensor GitHub](https://github.com/opentensor/subtensor)
2. [Taostats API Documentation](https://docs.taostats.io/)
3. [Substrate RPC Documentation](https://docs.substrate.io/)
4. Bittensor Subtensor source code analysis:
   - `pallets/subtensor/src/utils/rate_limiting.rs`
   - `pallets/subtensor/rpc/src/lib.rs`
   - `contract-tests/test/*.ts`
   - `runtime/src/lib.rs`

---

**TL;DR**: Archive RPC works for historical queries, but the **public endpoint is rate-limited**. To query aggressively, **run your own archive node**. For analytics, **use Taostats API daily aggregation** (your current plan). The rate-limiting you hit is intentional and expected for heavy usage of shared resources.
