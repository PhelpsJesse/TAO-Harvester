from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from v2.tao_harvester.services.execution_interfaces import (
    AlphaStakeAction,
    AlphaStakeRequest,
    AlphaStakeResult,
    OpenTensorStakingPort,
)


@dataclass(frozen=True)
class OpenTensorSdkConfig:
    network: str
    wallet_name: str
    wallet_hotkey: str


class OpenTensorSdkStaker(OpenTensorStakingPort):
    """Tier 3 OpenTensor staking adapter using local bittensor SDK.

    This adapter is fail-closed by design: if SDK APIs are unavailable,
    wallet unlock fails, or chain submission raises, it returns a rejected result.
    """

    def __init__(self, config: OpenTensorSdkConfig):
        self.config = config

    def submit_alpha_stake(self, request: AlphaStakeRequest) -> AlphaStakeResult:
        if request.action != AlphaStakeAction.UNSTAKE:
            return AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="rejected",
                reason=f"unsupported action for this adapter: {request.action.value}",
            )

        try:
            import bittensor  # type: ignore[import-not-found]
        except Exception as exc:
            return AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="error",
                reason=f"bittensor SDK import failed: {exc}",
            )

        try:
            wallet = bittensor.wallet(name=self.config.wallet_name, hotkey=self.config.wallet_hotkey)
        except Exception as exc:
            return AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="error",
                reason=f"wallet initialization failed: {exc}",
            )

        try:
            unlock = getattr(wallet, "unlock_coldkey", None)
            if callable(unlock):
                unlock()
        except Exception as exc:
            return AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="error",
                reason=f"wallet unlock failed: {exc}",
            )

        try:
            subtensor = bittensor.subtensor(network=self.config.network)
        except Exception as exc:
            return AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="error",
                reason=f"subtensor init failed: {exc}",
            )

        try:
            # Try common SDK method names across bittensor versions.
            if hasattr(subtensor, "unstake"):
                receipt = subtensor.unstake(
                    wallet=wallet,
                    netuid=request.netuid,
                    amount=request.alpha_amount,
                    wait_for_finalization=True,
                    prompt=False,
                )
            elif hasattr(subtensor, "remove_stake"):
                receipt = subtensor.remove_stake(
                    wallet=wallet,
                    netuid=request.netuid,
                    amount=request.alpha_amount,
                    wait_for_finalization=True,
                    prompt=False,
                )
            else:
                return AlphaStakeResult(
                    accepted=False,
                    tx_hash=None,
                    status="error",
                    reason="unsupported bittensor SDK: no unstake/remove_stake method",
                )
        except Exception as exc:
            return AlphaStakeResult(
                accepted=False,
                tx_hash=None,
                status="error",
                reason=f"chain unstake submission failed: {exc}",
            )

        tx_hash = _extract_tx_hash(receipt)
        return AlphaStakeResult(
            accepted=True,
            tx_hash=tx_hash,
            status="submitted",
            reason="unstake submitted via local bittensor SDK",
        )


def _extract_tx_hash(receipt: Any) -> str | None:
    if receipt is None:
        return None
    for key in ("tx_hash", "extrinsic_hash", "hash"):
        if isinstance(receipt, dict) and receipt.get(key):
            return str(receipt.get(key))
        value = getattr(receipt, key, None)
        if value:
            return str(value)
    return None
