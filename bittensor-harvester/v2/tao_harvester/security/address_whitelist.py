from __future__ import annotations

from pathlib import Path


class AddressWhitelist:
    def __init__(self, allowed_addresses: set[str]):
        self.allowed_addresses = allowed_addresses

    @classmethod
    def from_yaml(cls, path: str) -> "AddressWhitelist":
        yaml_path = Path(path)
        if not yaml_path.exists():
            return cls(set())

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
                    normalized.add(value)
        return cls(normalized)

    def is_allowed(self, address: str) -> bool:
        return address in self.allowed_addresses
