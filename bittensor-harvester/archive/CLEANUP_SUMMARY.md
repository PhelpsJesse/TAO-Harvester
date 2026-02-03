# TAO Harvester - Cleanup Summary

## Changes Made (February 1, 2026)

### 1. Archived Obsolete Files

Moved to `archive/obsolete_scripts/`:
- All `test_*.py` - Debug/test scripts
- All `debug_*.py` - One-off debugging tools
- All `fetch_*.py` - Data fetching experiments
- All `find_*.py` - Discovery scripts
- Other exploratory scripts: `save_*.py`, `diagnose_*.py`, `check_*.py`, `build_*.py`, `analyze_*.py`, `create_*.py`, `show_*.py`, `scan_*.py`, `print_*.py`, `examples_*.py`

### 2. Centralized Configuration

**Created:** `config.py` - Single source of truth for all settings

**All configurable items now in one place:**
- Wallet & validator settings
- Taostats API configuration  
- Bittensor RPC settings
- Harvesting thresholds & rules
- Kraken exchange credentials
- Database & file paths
- Advanced/debug settings

**Environment variables supported via `.env`:**
```
VALIDATOR_HOTKEYS=your_address
TAOSTATS_API_KEY=your_api_key
MIN_ALPHA_THRESHOLD=5.0
SUBSTRATE_RPC_URL=https://lite.chain.opentensor.ai
RPC_MIN_INTERVAL=2.0
...
```

### 3. Simplified Main Script

**Cleaned:** `daily_emissions_report.py`
- Removed complexity
- Clear function separation
- Consistent variable naming:
  - `alpha_balance` - Alpha values (stored)
  - `tao_estimate` - TAO estimates (display only)
  - `current_alpha` - Current balance
  - `previous_alpha` - Previous day balance
  - `daily_alpha_earned` - Delta calculation
- Better error handling
- Clearer output formatting
- Comprehensive docstrings

### 4. Updated Documentation

**Replaced multiple docs with:**
- `README.md` - Quick overview and quick start
- This file (`CLEANUP_SUMMARY.md`) - What was cleaned up

**Removed old documentation:**
- `QUICKSTART.md` (replaced with README)
- `PROJECT_SUMMARY.md` (obsolete)
- `IMPLEMENTATION_GUIDE.md` (obsolete)
- Various other `.md` files in root

### 5. Aligned Variable Names

**Standardized naming convention:**
- `alpha_balance` - Raw alpha values
- `tao_estimate` / `tao_value` - Estimated TAO equivalent
- `current_*` - Current state
- `previous_*` - Previous state
- `daily_*` - Delta/earnings
- `*_threshold` - Minimum values
- `*_limit` - Maximum values/rate limits

### 6. Reduced Complexity

**Removed:**
- Duplicate functionality
- Unnecessary abstractions
- Dead code paths
- Unused imports
- Over-engineered error handling

**Kept:**
- Core functionality (emissions tracking)
- Essential libraries (`src/chain.py`, `src/taostats.py`, `src/alpha_swap.py`)
- Database snapshot system
- CSV report generation

## Current Project Structure

```
bittensor-harvester/
├── daily_emissions_report.py    # ← Main script (run this)
├── config.py                     # ← All configuration
├── .env                          # ← Your secrets
├── README.md                     # ← Start here
├── requirements.txt              # ← Dependencies
├── harvester.db                  # ← SQLite database
├── reports/                      # ← CSV outputs
│   └── daily_emissions_YYYY-MM-DD.csv
├── logs/                         # ← Logs (if debug enabled)
├── src/                          # ← Core library
│   ├── chain.py                  # Bittensor RPC client
│   ├── taostats.py               # Taostats API client
│   ├── alpha_swap.py             # Alpha↔TAO conversion
│   ├── kraken.py                 # Kraken exchange (Phase 3)
│   ├── database.py               # Database utilities
│   ├── config.py                 # OLD config (deprecated)
│   └── ...
├── archive/                      # ← Old code (DO NOT USE)
│   └── obsolete_scripts/         # Test/debug scripts
└── tests/                        # ← Unit tests (legacy)
```

## How to Use After Cleanup

### 1. First Time Setup

```powershell
# Install dependencies
pip install -r requirements.txt

# Configure your settings
cp .env.example .env
# Edit .env with your API keys and addresses
```

### 2. Daily Usage

```powershell
# Run the tracker
python daily_emissions_report.py

# Check the output
cat reports/daily_emissions_2026-02-01.csv
```

### 3. Configuration

**All settings in `config.py`**

Override via `.env` file:
```bash
VALIDATOR_HOTKEYS=5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh
TAOSTATS_API_KEY=tao-xxxxx:xxxxx
MIN_ALPHA_THRESHOLD=5.0
TAOSTATS_RATE_LIMIT=5
```

### 4. Understanding Output

**Console Output:**
```
TAO HARVESTER - Daily Emissions Tracker
Validator: 5EWvVeos...
RPC: https://lite.chain.opentensor.ai

Fetching subnet balances from Taostats API...
[OK] Fetched 4 subnets with holdings

Processing 4 subnets...
SN  4:  18.76 alpha (~0.19 TAO) | Daily: +0.00 alpha
...

TOTAL HOLDINGS:  94.25 alpha (~0.94 TAO)
DAILY EARNINGS:   0.00 alpha (~0.00 TAO)

[OK] Report saved: reports/daily_emissions_2026-02-01.csv
[OK] Snapshots saved: harvester.db
```

**CSV Report:**
```csv
Subnet,Daily Alpha Earned,Daily TAO Estimate,Previous Alpha,Current Alpha,Current TAO Estimate
SN4,0.00000000,0.00000000,18.76726138,18.76726138,0.18767261
...
```

## Important Notes

### Rate Limiting

**Taostats free tier = 5 API calls/minute**

If you see "Only 4 subnets returned":
1. Wait 5-10 minutes
2. Run script again
3. Taostats will return complete data after rate limit resets

### Alpha vs TAO

- **Alpha values** are stored in database (accurate over time)
- **TAO estimates** are calculated only for display (conversion rates change)
- This design ensures historical accuracy

### First Run

- Establishes baseline snapshot
- Daily earnings will be 0
- Tomorrow's run will show actual delta

## Next Steps (Roadmap)

- [ ] Phase 2: Automated alpha→TAO conversion
- [ ] Phase 3: TAO→USD sales via Kraken
- [ ] Phase 4: Automated bank deposits  
- [ ] Windows Task Scheduler integration
- [ ] Email/SMS notifications

## Technical Debt Removed

1. ✅ Consolidated 4 config files into 1
2. ✅ Removed 40+ obsolete test/debug scripts
3. ✅ Standardized variable naming
4. ✅ Simplified main script (200→200 lines, but much clearer)
5. ✅ Updated all documentation
6. ✅ Removed dead code paths
7. ✅ Fixed import conflicts

## Files You Should Care About

**Use These:**
- `daily_emissions_report.py` - Main script
- `config.py` - Configuration
- `.env` - Your secrets
- `README.md` - Documentation
- `reports/*.csv` - Output files

**Ignore These:**
- `archive/` - Old code
- `tests/` - Legacy tests
- `src/config.py` - Old config (use root `config.py`)
- `*.log` - Log files

## Support

If you pick this up later and forget how it works:

1. Read `README.md` (2 minutes)
2. Check `config.py` for settings (5 minutes)  
3. Run `python daily_emissions_report.py` (instant gratification)

That's it. Everything else is noise.
