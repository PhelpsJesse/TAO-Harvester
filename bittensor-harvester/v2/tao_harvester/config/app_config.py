from __future__ import annotations

from dataclasses import dataclass, field
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
class OpenClawHandoffConfig:
    ssh_host: str = ""
    ssh_port: int = 22
    ssh_user: str = ""
    ssh_key_path: str = ""
    remote_handoff_dir: str = "/opt/harvester/handoff"
    local_handoff_dir: str = "handoff"
    remote_db_path: str = "/opt/harvester/data/harvester_v2.db"
    local_db_path: str = "v2/data/openclaw_latest.db"

    @property
    def configured(self) -> bool:
        return bool(self.ssh_host and self.ssh_user and self.ssh_key_path)


@dataclass(frozen=True)
class AppConfig:
    db_path: str
    taostats_base_url: str
    harvester_address: str
    kraken_deposit_whitelist: tuple[str, ...]
    rules: HarvestRules
    openclaw_handoff: OpenClawHandoffConfig = field(default_factory=OpenClawHandoffConfig)
    opentensor_staker_backend: str = "noop"
    opentensor_network: str = "finney"
    opentensor_wallet_name: str = "default"
    opentensor_wallet_hotkey: str = "default"
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
            openclaw_handoff=OpenClawHandoffConfig(
                ssh_host=os.getenv("OPENCLAW_SSH_HOST", ""),
                ssh_port=int(os.getenv("OPENCLAW_SSH_PORT", "22")),
                ssh_user=os.getenv("OPENCLAW_SSH_USER", ""),
                ssh_key_path=os.getenv("OPENCLAW_SSH_KEY_PATH", ""),
                remote_handoff_dir=os.getenv("OPENCLAW_HANDOFF_REMOTE_DIR", "/opt/harvester/handoff"),
                local_handoff_dir=os.getenv("OPENCLAW_HANDOFF_LOCAL_DIR", "handoff"),
                remote_db_path=os.getenv("OPENCLAW_DB_REMOTE_PATH", "/opt/harvester/data/harvester_v2.db"),
                local_db_path=os.getenv("OPENCLAW_DB_LOCAL_PATH", "v2/data/openclaw_latest.db"),
            ),
            opentensor_staker_backend=os.getenv("OPENTENSOR_STAKER_BACKEND", "noop"),
            opentensor_network=os.getenv("OPENTENSOR_NETWORK", "finney"),
            opentensor_wallet_name=os.getenv("OPENTENSOR_WALLET_NAME", "default"),
            opentensor_wallet_hotkey=os.getenv("OPENTENSOR_WALLET_HOTKEY", "default"),
            default_dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
            catchup_missed_days=os.getenv("CATCHUP_MISSED_DAYS", "true").lower() == "true",
        )


def parse_iso_date(value: str | None) -> date:
    if not value:
        return date.today()
    return date.fromisoformat(value)
