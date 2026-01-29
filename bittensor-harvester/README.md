"""
README for Bittensor TAO Earnings Harvester

## Overview

Autonomous system for tracking Bittensor alpha staking earnings, harvesting to TAO,
and managing tax-compliant fund movements. Designed for small-to-moderate balances
with a focus on safety, auditability, and tax compliance.

## Features

### Core
- **State-based accounting**: Uses on-chain snapshots to compute daily reward deltas
- **Harvest automation**: Plans and executes alpha → TAO conversions with safety caps
- **Tax exports**: Generates CSV files for rewards, harvests, and sales (Kraken)
- **Modular design**: Clear separation between accounting, harvest policy, execution, and export

### Safety
- Allowlist-only harvest destinations
- Per-run and per-day harvest caps
- Minimum execution thresholds (avoid dust)
- Dry-run support for testing
- All state in local SQLite (no external services required)

### Optional
- Kraken integration for TAO → USD sales
- USD withdrawal to checking account
- Withdrawal frequency gating (no daily withdrawals)

## Project Structure

```
bittensor-harvester/
├── src/
│   ├── __init__.py              # Package init
│   ├── main.py                  # Entry point & orchestrator
│   ├── config.py                # Configuration loading (.env)
│   ├── database.py              # SQLite schema & operations
│   ├── chain.py                 # Substrate RPC client (stubs)
│   ├── accounting.py            # Reward tracking & deltas
│   ├── harvest.py               # Harvest policy enforcement
│   ├── executor.py              # On-chain action execution
│   ├── export.py                # Tax CSV exports
│   └── kraken.py                # Kraken API integration
├── tests/
│   ├── test_database.py         # Database tests
│   ├── test_accounting.py       # Accounting tests
│   ├── test_harvest.py          # Harvest policy tests
│   ├── test_integration.py      # Full cycle integration test
│   └── example.py               # Usage examples
├── .env.example                 # Config template (DON'T COMMIT .env)
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Setup

### Prerequisites
- Python 3.12+
- pip

### Installation

1. Clone or download the project:
```bash
cd bittensor-harvester
```

2. Create virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

### Configuration (.env)

Critical settings:
- `SUBSTRATE_RPC_URL`: Node RPC endpoint (e.g., http://localhost:9933)
- `NETUID`: Subnet ID to harvest from
- `HARVESTER_WALLET_ADDRESS`: Wallet receiving rewards
- `HARVEST_DESTINATION_ADDRESS`: Where to send harvested TAO (must be allowlisted!)
- `HARVESTER_WALLET_SEED` or `HARVESTER_WALLET_ADDRESS`: For signing transactions

Optional:
- `KRAKEN_API_KEY`, `KRAKEN_API_SECRET`: For automated sales
- `KRAKEN_DEPOSIT_ADDRESS`: Kraken deposit address for TAO

**Security**: Never commit `.env` or any file with secrets to git!

## Usage

### Run Harvest Cycle (Dry-Run)

Test without making on-chain changes:
```bash
python -m src.main --dry-run
```

### Run Harvest Cycle (Live)

Execute real on-chain transactions (requires keys configured):
```bash
python -m src.main
```

### Run Tests

Unit tests:
```bash
python -m pytest tests/ -v
```

Or directly:
```bash
python tests/test_database.py
python tests/test_accounting.py
```

Integration test (full cycle with mock):
```bash
python tests/test_integration.py
```

Example usage:
```bash
python tests/example.py
```

### Check Database

View current state:
```bash
sqlite3 harvester.db
sqlite> SELECT * FROM rewards;
sqlite> SELECT * FROM harvests;
```

### Export Tax Data

Automatically exported after each run to:
- `rewards.csv` - Income events
- `harvest.csv` - Conversions & transfers
- `sales.csv` - Kraken sales (if enabled)
- `withdrawals.csv` - Bank withdrawals (non-taxable tracking)

Format is compatible with tax software and CPAs.

## Daily Operation

### Desktop Phase

Set up cron job (Linux/Mac) or Task Scheduler (Windows) to run once daily:

**Linux/Mac Cron**:
```bash
# Run at 2 AM UTC daily
0 2 * * * /path/to/venv/bin/python /path/to/bittensor-harvester/src/main.py >> /path/to/logs/harvest.log 2>&1
```

**Windows Task Scheduler**:
1. Create task: `bittensor-harvester-daily`
2. Trigger: Daily at 2 AM
3. Action: Run `python.exe` with args: `C:\path\to\bittensor-harvester\src\main.py`

### Raspberry Pi Phase

Once desktop is stable:
1. Install Python 3.12+ on Pi
2. Set up venv and install dependencies
3. Copy `.env` (with secrets in environment variables)
4. Configure cron as above

## Architecture

### Accounting (State-Based)

1. Query on-chain alpha balance for wallet
2. Compare to last known balance (from DB)
3. Delta = earned rewards for the period
4. Record in ledger

Benefits:
- No dependency on specific reward events
- Works even if emissions are applied as state mutations
- Robust to network disruptions

### Harvest Policy

Applied in order:
1. Check destination is allowlisted
2. Check accumulated balance > min threshold
3. Apply max-per-run cap
4. Apply max-per-day cap (rolling)
5. Queue harvest action

### Execution

1. Pre-flight checks (balance, address validity)
2. Build extrinsic (Substrate transaction)
3. Sign with harvester key
4. Submit to chain (or dry-run)
5. Record TX hash in database
6. Poll for finalization

### CSV Export

Each export includes:
- **Date** (UTC ISO 8601)
- **Asset** (ALPHA, TAO, USD)
- **Quantity** (with full precision)
- **Supporting info** (netuid, conversion rate, destination, tx hash)
- **Status** (pending, completed)

Suitable for:
- Tax software import
- CPA review
- Audit trail

## Error Handling

The system is designed to be idempotent and recoverable:

- **Partial harvest**: If TX fails, marked "pending" in DB; can retry
- **Config reload**: Picks up new .env values on next run (no restart)
- **Chain downtime**: Skips if RPC unreachable; retries next day
- **Log files**: Detailed logs in `harvester.log`

## Security Considerations

### Current (Desktop)

- Secrets in `.env` (never committed)
- Optional encryption of wallet seed (TODO: implement)
- Outbound firewall rules (only allow RPC + Kraken IP)

### Future (Autonomous)

- Environment variable injection at startup
- Hardware security module (HSM) for key storage
- Rate limiting on withdrawals
- Slack/email alerts for unusual activity

## TODO / Future Work

### Chain Integration
- [ ] Real Substrate RPC calls (currently mocked)
- [ ] Implement extrinsic signing & submission
- [ ] Handle network retries & exponential backoff
- [ ] Monitor finalization blocks

### Kraken Integration
- [ ] Implement real Kraken API (currently mocked)
- [ ] Handle order fills vs. partial fills
- [ ] Implement order cancellation & retry

### Security
- [ ] Wallet seed encryption/unlock
- [ ] HSM support for autonomous phase
- [ ] Rate limiting on withdrawals
- [ ] Alerting (Slack, email)

### Operations
- [ ] Web dashboard for monitoring
- [ ] Telegram bot for alerts
- [ ] Historical analytics (yield, fees)
- [ ] Multi-subnet support (currently hardcoded to netuid=1)

## Troubleshooting

### "Destination not in allowlist"
**Fix**: Add address to `HARVEST_DESTINATION_ADDRESS` in `.env`

### "Below min threshold"
**Fix**: Accumulate more rewards or lower `MIN_HARVEST_THRESHOLD_TAO`

### "No Kraken API key configured"
**Fix**: Leave Kraken settings empty for now; sales disabled

### Database locked
**Fix**: Ensure only one instance runs at a time. Check `harvester.log` for details.

### RPC connection refused
**Fix**: Verify `SUBSTRATE_RPC_URL` is reachable. Try local node or public endpoint.

## Contributing

This is a personal tool, but improvements welcome:
- Bug reports: Open an issue
- Features: Submit PR with tests
- Security: Email privately (do not open public issues for vulns)

## License

MIT (See LICENSE file if present)

## Disclaimer

**This software is provided as-is without warranty.** Test thoroughly on small amounts
before running with large balances. Always keep a backup of your database and keys.
The author is not responsible for lost funds or other damages.

---

**Questions?** Check `tests/example.py` or `tests/test_integration.py` for examples.
"""

__version__ = "0.1.0"
