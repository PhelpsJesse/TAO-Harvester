"""
Configuration management.

Loads from environment variables and config files.
Secrets from .env (not committed).
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class HarvesterConfig:
    """Harvester configuration."""

    # Chain
    substrate_rpc_url: str = os.getenv("SUBSTRATE_RPC_URL", "http://localhost:9933")
    netuid: int = int(os.getenv("NETUID", "1"))

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

    @classmethod
    def from_env(cls) -> "HarvesterConfig":
        """Load config from environment."""
        config = cls()
        # validate() can be called separately; don't force it here
        return config


def get_config() -> HarvesterConfig:
    """Get singleton config instance."""
    if not hasattr(get_config, "_instance"):
        get_config._instance = HarvesterConfig.from_env()
    return get_config._instance
