from __future__ import annotations

import hashlib
from pathlib import Path

import base58


# Bittensor uses SS58 version byte 42 (generic Substrate).
_SS58_VERSION_BYTE = 42
_SS58_ENCODED_LENGTH = 35


def _is_valid_bittensor_ss58(address: str) -> bool:
    """Validate that address is a correctly encoded Bittensor SS58 address.

    Checks:
    - Decodes as base58
    - Correct byte length (35 bytes)
    - Version prefix byte == 42 (Bittensor/generic Substrate)
    - Blake2b-512 checksum over 'SS58PRE' + payload matches last 2 bytes
    """
    if not isinstance(address, str):
        return False
    try:
        raw = base58.b58decode(address)
    except Exception:
        return False
    if len(raw) != _SS58_ENCODED_LENGTH:
        return False
    if raw[0] != _SS58_VERSION_BYTE:
        return False
    payload = raw[:33]
    h = hashlib.new("blake2b", digest_size=64)
    h.update(b"SS58PRE" + payload)
    checksum = h.digest()[:2]
    return raw[33:35] == checksum


class AddressWhitelist:
    def __init__(self, allowed_addresses: set[str]):
        self.allowed_addresses = allowed_addresses

    @classmethod
    def from_yaml(cls, path: str) -> "AddressWhitelist":
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"Whitelist file not found: {path}. "
                "Create config/whitelist.yaml with an allowed_addresses list before enabling execution."
            )

        lines = yaml_path.read_text(encoding="utf-8").splitlines()
        normalized: set[str] = set()
        in_allowed_block = False
        for raw_line in lines:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("allowed_addresses:"):
                in_allowed_block = True
                continue
            if in_allowed_block and line.startswith("-"):
                value = line[1:].strip()
                if value:
                    if not _is_valid_bittensor_ss58(value):
                        raise ValueError(
                            f"Whitelist entry '{value}' is not a valid Bittensor SS58 address "
                            "(must be version byte 42 with correct checksum). "
                            "Refusing to load whitelist with invalid entries."
                        )
                    normalized.add(value)
        return cls(normalized)

    def is_allowed(self, address: str) -> bool:
        return address in self.allowed_addresses

