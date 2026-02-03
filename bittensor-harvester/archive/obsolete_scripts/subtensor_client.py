"""
Wrapper around the official Bittensor Subtensor client.

Provides safe, read-only helpers for:
- Connecting to archive network
- Getting current block number
- Querying alpha balances via on-chain storage (TotalHotkeyAlpha)
- Fetching subnets and stake info (read-only)

Safeguards:
- No transaction submission functions are exposed
- All methods are defensive and return defaults on errors
"""

from typing import Dict, Optional, List, Tuple


def _get_subtensor(archive_url: Optional[str] = None):
    """Create a Subtensor client. Uses 'archive' network by default."""
    try:
        import bittensor as bt
        if archive_url:
            # Try common constructor arg names for endpoint
            for kwargs in (
                {"chain_endpoint": archive_url},
                {"subtensor_address": archive_url},
                {"endpoint": archive_url},
            ):
                try:
                    return bt.Subtensor(**kwargs)
                except Exception:
                    continue
        # Fallback to known network; prefer finney/mainnet
        try:
            return bt.Subtensor(network="finney")
        except Exception:
            return bt.Subtensor()
    except Exception:
        return None


def get_current_block(archive_url: Optional[str] = None) -> Optional[int]:
    st = _get_subtensor(archive_url)
    if not st:
        return None
    try:
        # Preferred: direct block number
        try:
            return st.substrate.get_block_number()
        except Exception:
            # Fallback: parse header
            head = st.substrate.get_block_header()
            num = head.get("number")
            if isinstance(num, str) and num.startswith("0x"):
                return int(num, 16)
            return int(num) if num is not None else None
    except Exception:
        return None


def get_all_subnets(archive_url: Optional[str] = None) -> List[int]:
    st = _get_subtensor(archive_url)
    if not st:
        return []
    try:
        # netuids are available via runtime API or storage; fallback to query_map
        result = st.substrate.query_map(module="SubtensorModule", storage_function="Networks")
        return sorted([int(k.value) for k, _ in result])
    except Exception:
        return []


def get_block_hash(block_number: int, archive_url: Optional[str] = None) -> Optional[str]:
    st = _get_subtensor(archive_url)
    if not st:
        return None
    try:
        return st.substrate.get_block_hash(block_number)
    except Exception:
        return None


def get_alpha_balance(hotkey_ss58: str, netuid: int, archive_url: Optional[str] = None,
                      block_hash: Optional[str] = None) -> Optional[float]:
    """Query on-chain TotalHotkeyAlpha[hotkey, netuid] and return alpha as float."""
    st = _get_subtensor(archive_url)
    if not st:
        return None
    try:
        # Storage double map: (hotkey AccountId32, netuid u16)
        kwargs = {"module": "SubtensorModule", "storage_function": "TotalHotkeyAlpha", "params": [hotkey_ss58, netuid]}
        if block_hash:
            kwargs["block_hash"] = block_hash
        res = st.substrate.query(
            **kwargs
        )
        # Value may be rao; convert to TAO units if needed
        val = res.value if hasattr(res, "value") else res
        if val is None:
            return 0.0
        # If numeric large int, assume rao and divide by 1e9
        try:
            v = float(val)
        except Exception:
            # Some substrates return dict {"value": n}
            v = float(val.get("value", 0)) if isinstance(val, dict) else 0.0
        return v / 1e9 if v > 1e6 else v
    except Exception:
        return None


def get_stake_for_cold_hot(coldkey: str, hotkey: str, netuid: int, archive_url: Optional[str] = None) -> Optional[float]:
    """Fetch stake amount (read-only)."""
    st = _get_subtensor(archive_url)
    if not st:
        return None
    try:
        res = st.substrate.query(
            module="SubtensorModule",
            storage_function="Stake",
            params=[netuid, [coldkey, hotkey]],
        )
        val = res.value if hasattr(res, "value") else res
        if val is None:
            return 0.0
        try:
            v = float(val)
        except Exception:
            v = float(val.get("value", 0)) if isinstance(val, dict) else 0.0
        return v / 1e9 if v > 1e6 else v
    except Exception:
        return None


def get_alpha_balance_at_block(hotkey_ss58: str, netuid: int, block_number: int,
                               archive_url: Optional[str] = None) -> Optional[float]:
    """Helper to query alpha balance at a specific block number."""
    bh = get_block_hash(block_number, archive_url)
    if not bh:
        return None
    return get_alpha_balance(hotkey_ss58, netuid, archive_url=archive_url, block_hash=bh)
