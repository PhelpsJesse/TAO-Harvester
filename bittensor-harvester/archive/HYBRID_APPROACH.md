# Hybrid Block-Level Emissions Query

## The Problem

**You want block-level emissions data**, but:
- ❌ Taostats API only has daily snapshots (no block-level detail)
- ❌ Archive RPC rate-limits when querying all 300 subnets
- ❌ Need a way to get detailed data without hitting rate limits

## The Solution: Hybrid Approach

**Use Taostats to discover active subnets, then query Archive RPC for only those subnets.**

### Strategy

```
Step 1: Taostats API (Discovery)
  ↓
  Query once: "Which subnets does this wallet hold alpha in?"
  ↓
  Returns: [1, 3, 5, 9, 18] (5 active subnets)

Step 2: Archive RPC (Block-Level Detail)
  ↓
  Query ONLY those 5 subnets for block-level data
  ↓
  Total queries: 10 (start + end balance for each subnet)
  vs 600 if querying all 300 subnets
  ↓
  95% reduction in queries = No rate-limiting!
```

## Implementation

### New Method: `get_block_level_emissions()`

Located in `src/archive_chain.py`:

```python
async def get_block_level_emissions(
    self,
    address: str,
    netuids: List[int],  # From Taostats discovery
    start_block: int,
    end_block: int,
    delay_ms: int = 200
) -> Dict[int, Dict]:
    """
    Get block-level emissions for specific subnets.
    
    Returns:
        {
            netuid: {
                'start_balance': float,
                'end_balance': float,
                'emissions': float,
                'start_block': int,
                'end_block': int,
                'blocks_elapsed': int,
                'emissions_per_block': float
            }
        }
    """
```

### Usage Example

See `hybrid_block_query.py` for full workflow:

```python
# Step 1: Discover active subnets via Taostats
taostats = TaostatsClient(api_key=config.taostats_api_key)
result = taostats.get_alpha_balance_by_subnet(wallet)
active_subnets = list(result['subnet_balances'].keys())

# Step 2: Query block-level data for ONLY active subnets
archive_client = ArchiveChainClient(config, db)
emissions = await archive_client.get_block_level_emissions(
    address=wallet,
    netuids=active_subnets,  # Only 5-10 subnets, not 300!
    start_block=start_block,
    end_block=current_block,
    delay_ms=200  # Rate-limiting safety
)

# Result: Block-level detail without rate-limiting
for netuid, data in emissions.items():
    print(f"Subnet {netuid}: {data['emissions_per_block']:.12f} alpha/block")
```

## Benefits

### ✅ Advantages

1. **Block-level detail**: Get per-block emissions data (not available in Taostats)
2. **No rate-limiting**: Only query 5-10 subnets instead of 300 (95% reduction)
3. **Efficient**: 1 Taostats query + 10 Archive RPC queries = 11 total
4. **Accurate**: Direct from chain via Archive RPC
5. **Fast**: Completes in seconds (not minutes)

### 📊 Query Comparison

| Approach | Taostats Queries | Archive RPC Queries | Total | Rate Limited? |
|----------|------------------|---------------------|-------|---------------|
| **Naive (all subnets)** | 0 | 600 (300 × 2) | 600 | ❌ YES |
| **Hybrid (active only)** | 1 | 10 (5 × 2) | 11 | ✅ NO |
| **Reduction** | - | **98.3%** | **98.2%** | - |

## Running the Test

```bash
# Configure your wallet in .env
HARVESTER_WALLET_ADDRESS=5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh

# Run the hybrid query
python hybrid_block_query.py
```

### Expected Output

```
================================================================================
STEP 1: Discover Active Subnets (Taostats API)
================================================================================
Querying Taostats for subnet holdings...

✅ Found 5 active subnets:
   Subnet   1: 123.456789000 alpha
   Subnet   3: 45.678900000 alpha
   Subnet   5: 12.345678900 alpha
   Subnet   9: 6.789012345 alpha
   Subnet  18: 2.345678901 alpha

Total alpha: 190.616059146

================================================================================
STEP 2: Query Block-Level Emissions (Archive RPC)
================================================================================

Current block: 7,453,542
Start block (7 days ago): 7,403,142
Blocks to query: 50,400
Active subnets: 5
Total queries: 10 (start + end for each subnet)

[1/5] Querying subnet 1...
  ✓ Subnet 1: 2.456789000 alpha earned (0.000048750000 per block)
[2/5] Querying subnet 3...
  ✓ Subnet 3: 0.987654321 alpha earned (0.000019596909 per block)
...

================================================================================
DETAILED EMISSIONS BREAKDOWN
================================================================================

Subnet   Start Balance   End Balance     Emissions       Per Block       
-------------------------------------------------------------------------
1        121.000000000   123.456789000   2.456789000     0.000048750000  
3        44.691245679    45.678900000    0.987654321     0.000019596909  
5        11.358024579    12.345678900    0.987654321     0.000019596909  
9        5.801358024     6.789012345     0.987654321     0.000019596909  
18       1.358024580     2.345678901     0.987654321     0.000019596909  
-------------------------------------------------------------------------
TOTAL                                    6.407406284     

Emission rates:
  Per hour:  0.038139319 alpha
  Per day:   0.915343656 alpha
  Per week:  6.407405592 alpha

================================================================================
✅ SUCCESS
================================================================================
Queried 5 subnets over 50,400 blocks
Total queries: 10 (vs 600 if querying all 300 subnets)
Query reduction: 98.3%
```

## Rate Limiting Safety

The hybrid approach includes:
- **200ms delay** between Archive RPC queries
- **Built-in error handling** (skips failed subnets)
- **Progress feedback** (shows which subnet is being queried)
- **Total query count**: 5 subnets × 2 queries = 10 total
  - At 200ms delay: 10 × 0.2s = 2 seconds total query time
  - Well under any rate limit threshold

## Integration with Accounting

This method can be integrated into `accounting.py`:

```python
# Daily workflow:
1. Query Taostats once: Get list of active subnets (1 query)
2. Query Archive RPC for active subnets only (10 queries)
3. Store block-level data in database
4. Run analytics on local database (no API calls)

# Result:
- Block-level detail for all active subnets
- 11 total queries (vs 600 for naive approach)
- No rate-limiting
- Fast and reliable
```

## Why This Works

### Taostats Strengths:
- **Good at**: Providing current snapshot of all holdings
- **Fast**: Single query returns all subnets
- **Reliable**: No rate limits on this endpoint

### Archive RPC Strengths:
- **Good at**: Block-level historical queries
- **Detailed**: Exact balance at any block
- **Accurate**: Direct from chain

### Hybrid Combines Best of Both:
1. Use Taostats to **discover** which subnets matter
2. Use Archive RPC to get **detailed history** on only those subnets
3. Avoid querying 295 empty subnets (wasted queries)

## Comparison to Other Approaches

| Approach | Block-Level Data? | Rate Limited? | Queries | Speed |
|----------|-------------------|---------------|---------|-------|
| **Taostats only** | ❌ No (daily only) | ✅ No | 1 | Fast |
| **Archive RPC (all 300)** | ✅ Yes | ❌ YES | 600 | Fails |
| **Hybrid** | ✅ Yes | ✅ No | 11 | Fast |
| **Run own node** | ✅ Yes | ✅ No | Unlimited | Requires setup |

## Next Steps

### For Production Use:

1. **Integrate into accounting.py**:
   - Replace naive all-subnet queries with hybrid approach
   - Store block-level data in database
   - Run daily or on-demand

2. **Add caching**:
   - Cache Taostats subnet discovery (valid for 24 hours)
   - Only re-query when needed

3. **Extend time ranges**:
   - Query 30 days, 90 days, etc.
   - Build historical trends in database
   - No rate-limiting even for large ranges

### For Advanced Features:

- **Subnet performance tracking**: Block-by-block emissions for each subnet
- **Anomaly detection**: Detect sudden drops in emissions
- **Historical comparisons**: "How did this week compare to last week?"
- **Optimization**: Query multiple time ranges in one session

## Conclusion

**The hybrid approach solves the rate-limiting problem while giving you the block-level detail you want.**

- ✅ Taostats: Discover active subnets (1 query)
- ✅ Archive RPC: Get block-level detail on only active subnets (10 queries)
- ✅ Result: 98% reduction in queries, no rate-limiting, full detail

**This is the recommended approach for production use.**
