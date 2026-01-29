# PROJECT SUMMARY

Bittensor TAO Earnings Harvester — concise project overview.

Status: Prototype with unit tests and documentation. Core modules implemented; chain and exchange integrations stubbed.

Highlights:
- State-based accounting (balance deltas) for alpha rewards
- Harvest policy: configurable fraction, min threshold, per-run and per-day caps
- Local SQLite persistence
- Tax CSV exports (rewards, harvests, sales, withdrawals)
- Dry-run support for safe testing

Next steps: Implement Substrate RPC calls, extrinsic signing, Kraken trading, and secure key storage.
