"""
Configuration management.

Loads from environment variables (.env file).
All secrets stored in .env (NOT committed to git).

Configuration covers:
- Bittensor RPC endpoint (for alpha balance queries)
- Harvest policy (percentages, thresholds, caps)
- Kraken API credentials (for TAO→USD sales)
- Taostats API key (fallback source, optional)
- Database path (SQLite state persistence)

See .env.template or .env file for all available options.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
import json

# Load .env file
load_dotenv()



@dataclass
class HarvesterConfig:
    """Harvester configuration."""
    # Aggregation window (in days) for earnings report
    aggregation_window_days: int = int(os.getenv("AGGREGATION_WINDOW_DAYS", "1"))

    # Chain - Archive RPC for transactions (queries use Taostats)
    archive_rpc_url: str = os.getenv("ARCHIVE_RPC_URL", "wss://archive.chain.opentensor.ai:443")
    netuid: int = int(os.getenv("NETUID", "1"))

    # Validators: comma-separated list of SS58 hotkeys to monitor
    # Example: VALIDATOR_HOTKEYS=5ABC...,5DEF...
    validator_hotkeys: str = os.getenv("VALIDATOR_HOTKEYS", "")

    # Subnets to monitor (comma-separated list). Defaults to NETUID if not set.
    # Example: SUBNET_LIST=1,5,9
    subnet_list: str = os.getenv("SUBNET_LIST", os.getenv("NETUID", "1"))

    # Harvest policy
    harvest_fraction: float = float(os.getenv("HARVEST_FRACTION", "0.5"))  # 50% of emissions
    min_harvest_threshold_tao: float = float(
        os.getenv("MIN_HARVEST_THRESHOLD_TAO", "0.1")
    )
    max_harvest_per_run_tao: float = float(
        os.getenv("MAX_HARVEST_PER_RUN_TAO", "10.0")
    )
    max_harvest_per_day_tao: float = float(
        os.getenv("MAX_HARVEST_PER_DAY_TAO", "50.0")
    )

    # Harvest destination (allowlist)
    harvest_destination_address: str = os.getenv(
        "HARVEST_DESTINATION_ADDRESS", "5GrwvmD..."  # Placeholder
    )

    # Wallet / Keys
    harvester_wallet_seed: str = os.getenv("HARVESTER_WALLET_SEED", "")
    harvester_wallet_address: str = os.getenv("HARVESTER_WALLET_ADDRESS", "")

    # Kraken (optional)
    kraken_api_key: str = os.getenv("KRAKEN_API_KEY", "")
    kraken_api_secret: str = os.getenv("KRAKEN_API_SECRET", "")
    kraken_deposit_address: str = os.getenv("KRAKEN_DEPOSIT_ADDRESS", "")

    # Taostats API (optional, for earnings statistics)
    taostats_api_key: str = os.getenv("TAOSTATS_API_KEY", "")

    # Withdrawal settings
    min_withdrawal_threshold_usd: float = float(
        os.getenv("MIN_WITHDRAWAL_THRESHOLD_USD", "100.0")
    )
    max_withdrawal_per_week_usd: float = float(
        os.getenv("MAX_WITHDRAWAL_PER_WEEK_USD", "500.0")
    )
    withdrawal_destination_account: str = os.getenv(
        "WITHDRAWAL_DESTINATION_ACCOUNT", ""
    )

    # Database
    db_path: str = os.getenv("DB_PATH", "harvester.db")

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self):
        """Validate critical config values."""
        errors = []

        if not self.harvester_wallet_seed and not self.harvester_wallet_address:
            errors.append("Must provide either HARVESTER_WALLET_SEED or HARVESTER_WALLET_ADDRESS")

        if not self.harvest_destination_address or self.harvest_destination_address.startswith("5Grwv"):
            errors.append("HARVEST_DESTINATION_ADDRESS must be set to a valid allowlisted address")

        if self.harvest_fraction <= 0 or self.harvest_fraction > 1.0:
            errors.append("HARVEST_FRACTION must be between 0 and 1")

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    def get_validator_list(self):
        """Return list of validator hotkeys from config (or single address)."""
        vals = self.validator_hotkeys.strip()
        if not vals:
            # fallback to HARVESTER_WALLET_ADDRESS if set
            if self.harvester_wallet_address:
                return [self.harvester_wallet_address]
            return []
        return [v.strip() for v in vals.split(",") if v.strip()]

    def get_subnet_list(self):
        """Return list of subnet IDs to monitor as ints."""
        raw = self.subnet_list.strip()
        if not raw:
            return [self.netuid]
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        out = []
        for p in parts:
            try:
                out.append(int(p))
            except ValueError:
                continue
        return out

    @classmethod
    def from_env(cls) -> "HarvesterConfig":
        """Load config from environment."""
        # Prefer JSON config file if present
        json_path = os.path.join(os.getcwd(), 'config.json')
        config = cls()
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                # Map known keys from JSON into dataclass fields
                if 'taostats_api_key' in data:
                    config.taostats_api_key = data['taostats_api_key']
                if 'validator_hotkeys' in data:
                    config.validator_hotkeys = ','.join(data.get('validator_hotkeys', []))
                if 'subnet_list' in data:
                    config.subnet_list = ','.join(str(x) for x in data.get('subnet_list', []))
                if 'harvest_fraction' in data:
                    config.harvest_fraction = float(data['harvest_fraction'])
                if 'harvest_destination_address' in data:
                    config.harvest_destination_address = data['harvest_destination_address']
                if 'harvester_wallet_address' in data:
                    config.harvester_wallet_address = data['harvester_wallet_address']
                if 'aggregation_window_days' in data:
                    config.aggregation_window_days = int(data['aggregation_window_days'])
            except Exception:
                # Fall back to environment variables if JSON parsing fails
                config = cls()
        return config


def get_config() -> HarvesterConfig:
    """Get singleton config instance."""
    if not hasattr(get_config, "_instance"):
        get_config._instance = HarvesterConfig.from_env()
    return get_config._instance
