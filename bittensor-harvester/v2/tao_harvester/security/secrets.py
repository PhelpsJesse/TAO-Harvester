from __future__ import annotations

from abc import ABC, abstractmethod
import os


class SecretProvider(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None:
        raise NotImplementedError


class EnvSecretProvider(SecretProvider):
    def get(self, key: str) -> str | None:
        return os.getenv(key)


class EncryptedSecretProvider(SecretProvider):
    def __init__(self, encrypted_path: str):
        self.encrypted_path = encrypted_path

    def unlock(self, password: str) -> None:
        raise NotImplementedError("TODO: Implement local in-memory decrypt for Tier 3 signer")

    def get(self, key: str) -> str | None:
        raise NotImplementedError("TODO: Implement local in-memory secret retrieval")
