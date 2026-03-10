from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChainTransferIntent:
    destination_address: str
    tao_amount: float
    note: str


@dataclass(frozen=True)
class ChainTransferReceipt:
    accepted: bool
    tx_hash: str | None
    reason: str


class ChainClientPort(Protocol):
    def submit_transfer(self, intent: ChainTransferIntent) -> ChainTransferReceipt: ...
