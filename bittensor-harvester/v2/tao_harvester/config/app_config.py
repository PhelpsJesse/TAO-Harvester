from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os


@dataclass(frozen=True)
class HarvestRules:
    harvest_fraction: float = 0.5
    min_harvest_alpha: float = 1.0
    transfer_batch_threshold_tao: float = 2.0
    max_harvest_tao_per_run: float = 25.0
    max_harvest_tao_per_day: float = 100.0


@dataclass(frozen=True)
class AppConfig:
    db_path: str
    taostats_base_url: str
    harvester_address: str
    kraken_deposit_whitelist: tuple[str, ...]
    rules: HarvestRules
    default_dry_run: bool = True
    catchup_missed_days: bool = True

    @staticmethod
    def from_env() -> "AppConfig":
        whitelist_raw = os.getenv("KRAKEN_DEPOSIT_WHITELIST", "")
        whitelist = tuple(x.strip() for x in whitelist_raw.split(",") if x.strip())
        rules = HarvestRules(
            harvest_fraction=float(os.getenv("HARVEST_FRACTION", "0.5")),
            min_harvest_alpha=float(os.getenv("MIN_HARVEST_ALPHA", "1.0")),
            transfer_batch_threshold_tao=float(os.getenv("TRANSFER_BATCH_THRESHOLD_TAO", "2.0")),
            max_harvest_tao_per_run=float(os.getenv("MAX_HARVEST_TAO_PER_RUN", "25.0")),
            max_harvest_tao_per_day=float(os.getenv("MAX_HARVEST_TAO_PER_DAY", "100.0")),
        )
        return AppConfig(
            db_path=os.getenv("V2_DB_PATH", "v2/data/harvester_v2.db"),
            taostats_base_url=os.getenv("TAOSTATS_BASE_URL", "https://api.taostats.io"),
            harvester_address=os.getenv("HARVESTER_WALLET_ADDRESS", ""),
            kraken_deposit_whitelist=whitelist,
            rules=rules,
            default_dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
            catchup_missed_days=os.getenv("CATCHUP_MISSED_DAYS", "true").lower() == "true",
        )


def parse_iso_date(value: str | None) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)
