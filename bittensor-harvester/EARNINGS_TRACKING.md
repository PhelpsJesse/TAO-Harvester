# Daily Alpha Earnings Tracking System

**Purpose**: Track daily alpha earnings (dividends) from Bittensor subnets and calculate harvestable amounts based on a configurable harvest fraction.

## Architecture Overview

### Key Components

1. **Taostats API Integration** (`src/taostats.py`)
   - Primary data source: `/api/transfer/v1` endpoint
   - Fetches inbound alpha transfers to your hotkey
   - Data includes: timestamp, amount (rao), block number, source address

2. **Wallet Manager** (`src/wallet_manager.py`)
   - **Generic & dynamic**: Checks current wallet holdings on each run
   - Uses `get_alpha_balance_by_subnet()` from TaostatsClient
   - Returns dict: `{subnet_id: alpha_balance}`
   - Not hardcoded—works with any wallet, any subnets

3. **Emissions Mapping** (`emissions_config.json`)
   - **Configurable mapping**: Source address → list of subnet IDs
   - Users can update this as they discover which subnet each source belongs to
   - Allows for multiple emission sources (dTAO, special rewards, etc.)

4. **Earnings Report** (`earnings_report.py`)
   - Generates daily earnings breakdown by subnet
   - Splits earnings across subnets if source emits to multiple subnets
   - Calculates harvestable amounts (earnings × harvest_fraction)
   - Outputs CSV: `reports/earnings_report_<YYYYMMDD>.csv`

## How It Works

### Daily Workflow

```
1. earnings_report.py runs
2. Wallet manager queries Taostats for current holdings
3. For each owned subnet:
   - Query transfer history (30 days default)
   - Group transfers by date and source address
   - Look up source address in emissions_config.json
   - Split earnings equally across mapped subnets
   - Calculate harvestable amount (× harvest_fraction)
4. Write CSV report with daily breakdown
```

### Key Data Flow

```
Taostats API
   ↓
Transfer History (inbound transfers to hotkey)
   ↓
Daily Aggregation (group by date and source)
   ↓
Emissions Mapping (source address → subnets)
   ↓
Per-Subnet Assignment (split if source emits to multiple subnets)
   ↓
Harvestable Calculation (amount × config.harvest_fraction)
   ↓
CSV Report
```

## Configuration

### .env File
```
TAOSTATS_API_KEY=tao-<uuid>:<key>
HARVESTER_WALLET_ADDRESS=5E...
HARVEST_FRACTION=0.5  # Harvest 50% of daily earnings
```

### emissions_config.json
```json
{
  "emissions_mapping": {
    "sources": {
      "5FqqXKb9...": {
        "description": "Primary emission source",
        "subnets": [1, 29, 34, 44, ...],
        "confidence": "estimated"
      },
      "5CiEiYCp...": {
        "description": "Secondary emission source",
        "subnets": [29],
        "confidence": "low"
      }
    }
  }
}
```

**To update the mapping:**
1. Discover which subnet each source address belongs to (on-chain query, Taostats, or manual research)
2. Update the `subnets` list for that source
3. Remove a subnet from list if you no longer own it
4. System automatically picks up changes on next run

## Output: earnings_report_YYYYMMDD.csv

```
date,address,netuid,daily_earnings,harvestable_alpha,block,source_address,transfer_count
2026-02-01,5EWv...,29,0.137,0.0686,7449459,5Fqq...,1
2026-02-01,5EWv...,34,0.137,0.0686,7449459,5Fqq...,1
2026-02-01,5EWv...,44,0.137,0.0686,7449459,5Fqq...,1
```

**Columns:**
- `date`: When earnings were recorded
- `address`: Your validator hotkey
- `netuid`: Subnet that emitted this alpha (numeric ID)
- `daily_earnings`: Alpha earned on this date from this subnet (TAO)
- `harvestable_alpha`: Amount available to harvest (earnings × 50%)
- `block`: Approximate block number
- `source_address`: Which validator emitted the alpha
- `transfer_count`: Number of transfers from this source on this date

## Known Limitations & TODOs

### Current Limitation: Equal Split Across Subnets
If a source address emits to multiple subnets, we split the earnings equally.

```
Example: If source address "5Fqq..." emits 1 TAO and maps to subnets [29, 34, 44]:
- SN29 gets 1/3 TAO = 0.333
- SN34 gets 1/3 TAO = 0.333
- SN44 gets 1/3 TAO = 0.333
```

**Why this is conservative**: In reality, we don't know the actual per-subnet breakdown without on-chain data.

### Future Improvements
1. **Per-subnet emissions data**: If Taostats or on-chain data becomes available showing actual emissions per subnet, update the split logic to use real amounts instead of equal split
2. **Validator registration lookup**: Query Substrate chain for subnet validator registrations to auto-populate the emissions_config.json
3. **Unknown source handling**: When a new source address appears, automatically alert user and ask them to map it

## For Other Users

To use this system with your own wallet:

1. Set up `.env` with your Taostats API key and wallet address
2. Run `earnings_report.py`
3. Check CSV output in `reports/`
4. Update `emissions_config.json` with your known emissions sources
5. (Optional) If you know which subnets each source represents, update the mapping
6. Run again—system will automatically pick up new subnets if you purchase them

The system is **generic and will work with any subnet combination** as long as you have a Taostats API key.

## Technical Notes

### Why Taostats Transfers Instead of On-Chain Data?
- **Transfer API** provides historical daily breakdown with exact timestamps
- **On-chain queries** would require archive node with state_getStorage support (not all RPC nodes support this)
- **Taostats is indexed** and queryable—much faster for historical analysis

### Why Dynamic Holdings Check?
- Users may purchase or sell subnets over time
- Hardcoding subnet list would require code changes
- Querying Taostats ensures we report only on subnets user actually owns
- Allows for generic reusability across different wallets

### Authentication
- Taostats API requires `Authorization: <api_key>` header (no "Bearer" prefix)
- Rate limit: 5 requests/minute (implement delays in calling code)
- API key is passed via environment variable, never hardcoded

## Integration with Harvester

Once you have the daily earnings breakdown:

1. **Read earnings_report.csv** daily
2. **Check harvestable_alpha column**
3. **For each subnet**: If `harvestable_alpha > your_threshold`, harvest that subnet
4. **Execute harvest** via `executor.py` with the calculated amount

The earnings report provides the exact daily breakdown needed to implement smart harvesting logic per subnet.
