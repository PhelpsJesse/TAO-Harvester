from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ChainTransferRequest:
    destination_address: str
    tao_amount: float
    note: str


@dataclass(frozen=True)
class ChainTransferResult:
    accepted: bool
    tx_hash: str | None
    status: str
    reason: str


@dataclass(frozen=True)
class KrakenOrderRequest:
    pair: str
    side: str
    order_type: str
    base_amount: float


@dataclass(frozen=True)
class KrakenOrderResult:
    accepted: bool
    external_order_id: str | None
    status: str
    reason: str


class ChainSignerPort(ABC):
    @abstractmethod
    def submit_transfer(self, request: ChainTransferRequest) -> ChainTransferResult:
        raise NotImplementedError


class KrakenTradingPort(ABC):
    @abstractmethod
    def place_order(self, request: KrakenOrderRequest) -> KrakenOrderResult:
        raise NotImplementedError


class NoopChainSigner(ChainSignerPort):
    def submit_transfer(self, request: ChainTransferRequest) -> ChainTransferResult:
        return ChainTransferResult(
            accepted=False,
            tx_hash=None,
            status="not_implemented",
            reason="Tier 3 signer intentionally not implemented in first deliverable",
        )


class NoopKrakenTrader(KrakenTradingPort):
    def place_order(self, request: KrakenOrderRequest) -> KrakenOrderResult:
        return KrakenOrderResult(
            accepted=False,
            external_order_id=None,
            status="not_implemented",
            reason="Tier 2 Kraken executor intentionally not implemented in first deliverable",
        )
