# TAO Harvester

**Automated Bittensor validator emissions tracking and harvesting system**

Track daily alpha earnings from your Bittensor validators and automate the conversion to TAO/USD.

---

## Quick Start

### 1. Install

```powershell
pip install -r requirements.txt
```

### 2. Configure

Copy `.env.example` to `.env`, then fill in your settings:

```bash
cp .env.example .env

VALIDATOR_HOTKEYS=5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh
TAOSTATS_API_KEY=tao-xxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:xxxxxx
```

### 3. Run

```powershell
python daily_emissions_report.py
```

---

## What It Does

**Phase 1 (Current):** Daily Emissions Tracking ✅
- Fetches alpha balances from Taostats API
- Stores daily snapshots in database
- Calculates daily earnings by comparing to previous day
- Generates CSV reports with alpha values and TAO estimates

**Phase 2 (Planned):** Automated Alpha→TAO Conversion  
**Phase 3 (Planned):** TAO→USD Sales via Kraken  
**Phase 4 (Planned):** Automated Bank Deposits  

---

## Key Features

- **Alpha-based tracking:** Stores alpha values (not TAO) for accuracy over time
- **Daily snapshots:** Compares today vs yesterday to calculate earnings
- **Multi-subnet support:** Tracks all 25+ subnets automatically
- **TAO estimates:** Calculates current TAO value for display
- **CSV reports:** Easy to import into Excel/Sheets
- **SQLite database:** Local storage, no external dependencies

---

## Configuration

All settings in `config.py` can be overridden via `.env`:

**Required:**
- `VALIDATOR_HOTKEYS` - Your validator hotkey address
- `TAOSTATS_API_KEY` - Get from https://taostats.io

**Optional:**
- `MIN_ALPHA_THRESHOLD` - Minimum alpha before harvesting (default: 5.0)
- `SUBSTRATE_RPC_URL` - RPC endpoint (default: lite.chain.opentensor.ai)
- `KRAKEN_API_KEY` / `KRAKEN_API_SECRET` - For Phase 3 (automated sales)

See `config.py` for full list of settings.

---

## Output Files

- `reports/daily_emissions_YYYY-MM-DD.csv` - Daily CSV report
- `harvester.db` - SQLite database with snapshot history
- `logs/` - Application logs (if debug enabled)

---

## Important Notes

### Taostats Rate Limiting

Free tier = **5 API calls/minute**. If you see "Only 4 subnets returned":
- Wait 5-10 minutes and run again
- Taostats will return more complete data after rate limit resets

### Alpha vs TAO

- **Alpha values** stored in database (conversion rates change over time)
- **TAO estimates** calculated only for display
- This ensures accurate historical tracking

### First Run

- Establishes baseline snapshot
- Daily earnings will show 0 on first run
- Run again tomorrow to see actual daily delta

---

## Troubleshooting

**"No TAOSTATS_API_KEY configured"**  
→ Add API key to `.env` (get from https://taostats.io)

**"Only X subnets returned (expected ~25)"**  
→ Taostats rate limit - wait 5-10 minutes and retry

**"Could not fetch from Taostats"**  
→ Check API key validity, network connection, rate limits

---

## File Structure

```
bittensor-harvester/
├── daily_emissions_report.py    # Main script
├── config.py                     # All configuration
├── .env                          # Your secrets
├── requirements.txt              # Dependencies
├── harvester.db                  # Database
├── reports/                      # CSV outputs
├── src/                          # Core library
│   ├── chain.py                  # RPC client
│   ├── taostats.py               # Taostats API
│   ├── alpha_swap.py             # Alpha conversion
│   └── ...
└── archive/                      # Obsolete scripts
```

---

## Development Roadmap

- [x] Phase 1: Daily emissions tracking
- [ ] Phase 2: Automated alpha→TAO conversion
- [ ] Phase 3: TAO→USD sales (Kraken integration)
- [ ] Phase 4: Automated bank deposits
- [ ] Phase 5: Windows Task Scheduler integration

---

## Links

- **Bittensor:** https://docs.bittensor.com/
- **Taostats:** https://taostats.io/
- **Kraken API:** https://docs.kraken.com/rest/

---

## License

See LICENSE file.
