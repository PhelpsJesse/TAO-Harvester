"""
Helpers to construct Substrate storage keys for Subtensor pallet.

Implements key for:
- SubtensorModule::TotalHotkeyAlpha (DoubleMap: AccountId32 (Blake2_128Concat), NetUid (Identity))
"""

import hashlib
import base58


def blake2_128(data: bytes) -> bytes:
    return hashlib.blake2b(data, digest_size=16).digest()


def ss58_to_account_bytes(ss58_address: str) -> bytes:
    decoded = base58.b58decode(ss58_address)
    if decoded[0] < 64:
        account_id = decoded[1:33]
    else:
        account_id = decoded[2:34]
    return account_id[:32]


def total_hotkey_alpha_key(hotkey_ss58: str, netuid: int) -> str:
    # module/storage prefixes (twox 128 of names). Using precomputed constants improves speed.
    # For SubtensorModule / TotalHotkeyAlpha:
    pallet_prefix = bytes.fromhex("baa58e1ec06d8a3b8cef6b2099eb69aa")
    storage_prefix = bytes.fromhex("68dc8e4fde0c56f0cf48deec0f65aaba")

    account = ss58_to_account_bytes(hotkey_ss58)
    account_hash = blake2_128(account)
    netuid_bytes = netuid.to_bytes(2, byteorder="little")

    key = b"".join([pallet_prefix, storage_prefix, account_hash, account, netuid_bytes])
    return "0x" + key.hex()
