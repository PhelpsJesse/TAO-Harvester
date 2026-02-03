# Historical Data Export Solutions

This repository uses proven Taostats API solutions for historical wallet data export.

## Community Resources

**Official Examples:** https://github.com/taostat/awesome-taostats-api-examples
- Contains Jupyter notebooks and Python scripts from the Bittensor community
- Proven solutions for accounting, balance tracking, emissions history, etc.

## Proven API Endpoints for Historical Data

### 1. Daily Balance History
**Endpoint:** `/api/account/history/v1`  
**Use case:** Daily snapshots of wallet balance (free, staked, total)  
**Example:** `src/export_balance_history.py`

```python
url = f"https://api.taostats.io/api/account/history/v1?address={wallet}&timestamp_start={start}&timestamp_end={end}&limit=200&page=1&order=timestamp_asc"
```

**Returns:** Daily records with:
- `balance_free` - Free TAO balance
- `balance_staked` - Total staked (root + alpha)
- `balance_staked_alpha_as_tao` - Alpha converted to TAO
- `balance_total` - Total wallet value
- `alpha_balances` - Per-subnet alpha breakdown

### 2. Per-Subnet Alpha History
**Endpoint:** `/api/dtao/stake_balance/history/v1`  
**Use case:** Track alpha balance changes on specific subnets over time

```python
url = f"https://api.taostats.io/api/dtao/stake_balance/history/v1?hotkey={hotkey}&coldkey={coldkey}&netuid={netuid}&limit=200"
```

### 3. Delegation Events
**Endpoint:** `/api/delegation/v1`  
**Use case:** All stake/unstake transactions with timestamps and amounts

```python
url = f"https://api.taostats.io/api/delegation/v1?nominator={coldkey}&timestamp_start={start}&timestamp_end={end}&limit=200"
```

### 4. Transfer History
**Endpoint:** `/api/transfer/v1`  
**Use case:** All TAO transfers in/out of wallet

### 5. Emission History
**Endpoint:** `/api/dtao/hotkey_emission/v1`  
**Use case:** Historical validator/miner earnings per epoch

```python
url = f"https://api.taostats.io/api/dtao/hotkey_emission/v1?hotkey={hotkey}&netuid={netuid}&block_start={start}&block_end={end}"
```

## Taostats WebSocket RPC (Advanced)

For granular per-block queries, Taostats provides **hosted RPC WebSocket** access:

```python
# Archive node (historical state queries)
taostats_archive = f'wss://api.taostats.io/api/v1/rpc/ws/finney_archive?authorization={api_key}'

# Lite node (current state only, faster)
taostats_lite = f'wss://api.taostats.io/api/v1/rpc/ws/finney_lite?authorization={api_key}'

# Use with bittensor library
import bittensor as bt
with bt.Subtensor(network=taostats_archive) as subtensor:
    balance = subtensor.get_balance(wallet_address)
```

**Note:** Archive RPC has rate limits. For bulk historical queries, use the REST API endpoints above.

## Why Not Direct RPC?

**Problem:** OpenTensor's public archive RPC (`wss://archive.chain.opentensor.ai:443`) has:
- Severe rate limiting (HTTP 429 after a few requests)
- No batch query support
- Requires manual storage key construction
- Historical state pruning (very old blocks may not be available)

**Solution:** Taostats indexes the entire chain and provides:
- Paginated REST API (200 records per page)
- Daily/hourly aggregations
- Pre-calculated conversions (alpha ↔ TAO)
- No rate limiting with API key
- CSV-ready data format

## Recommended Approach

1. **For daily/weekly analysis:** Use `/api/account/history/v1` (this repo)
2. **For tax/accounting:** Use community `accounting-v2.ipynb` script
3. **For per-subnet tracking:** Use `/api/dtao/stake_balance/history/v1`
4. **For real-time monitoring:** Use Taostats Lite WebSocket RPC

## Files in This Repo

- `src/export_balance_history.py` - Daily balance snapshots (proven working)
- `src/snapshot_holdings.py` - Current subnet holdings (working)
- `src/taostats.py` - Taostats API client (legacy, needs update with community endpoints)
- `src/ws_rpc.py` - Custom WebSocket RPC (not needed if using Taostats WebSocket)
- `src/block_holdings_export.py` - Per-block exporter (deprecated, use daily snapshots instead)

## Next Steps

To export subnet-level alpha balance history:
```python
# Get all subnets you're staked on
subnets_response = requests.get(
    f"https://api.taostats.io/api/dtao/stake_balance/latest/v1?coldkey={wallet}",
    headers={"Authorization": api_key}
)

# For each subnet, get historical balance
for subnet in subnets_response['data']:
    history = requests.get(
        f"https://api.taostats.io/api/dtao/stake_balance/history/v1?hotkey={subnet['hotkey']}&coldkey={wallet}&netuid={subnet['netuid']}&limit=200"
    )
    # Process history...
```
