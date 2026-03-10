from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UnlockRequest:
    key_alias: str


class WalletAdapterPort(Protocol):
    def unlock(self, request: UnlockRequest, password: str) -> bool: ...
