"""
OpenTensor/Substrate RPC service.

Separated service for JSON-RPC calls to the chain.
Provides read-only methods and standard RPC access patterns.
"""

import time
import requests
from typing import Any, List, Optional

try:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    import config as app_config
except Exception:
    app_config = None


class OpenTensorRpcService:
    """Thin RPC client for Substrate/OpenTensor JSON-RPC."""

    def __init__(self, rpc_url: str, min_interval: float = 2.0, verify_ssl: bool = False):
        self.rpc_url = rpc_url
        self.min_interval = float(min_interval)
        self.verify_ssl = verify_ssl
        self._request_id = 1
        self._last_request_time = 0.0

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """Perform a JSON-RPC 2.0 call with rate limiting and retries."""
        if app_config is not None and not app_config.config.RPC_ENABLED:
            raise RuntimeError("RPC is disabled (RPC_ENABLED=false)")

        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": self._request_id,
        }
        self._request_id += 1

        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                self._last_request_time = time.time()
                response = requests.post(self.rpc_url, json=payload, timeout=30, verify=self.verify_ssl)
                response.raise_for_status()
                result = response.json()

                if "error" in result:
                    raise RuntimeError(f"RPC error: {result['error']}")

                return result.get("result", {})

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                raise RuntimeError(f"RPC connection failed ({self.rpc_url}): {e}")
            except Exception as e:
                raise RuntimeError(f"RPC connection failed ({self.rpc_url}): {e}")

    def get_block_number(self) -> int:
        """Get current block number (Substrate or EVM-style)."""
        try:
            result = self.call("system_blockNumber", [])
            return int(result, 16) if isinstance(result, str) else int(result)
        except Exception:
            try:
                # Substrate: get finalized head hash, then header
                head_hash = self.call("chain_getFinalizedHead", [])
                header = self.call("chain_getHeader", [head_hash])
                num = header.get("number") if isinstance(header, dict) else None
                if isinstance(num, str) and num.startswith("0x"):
                    return int(num, 16)
                if num is not None:
                    return int(num)
            except Exception:
                # EVM style
                result = self.call("eth_blockNumber", [])
                if isinstance(result, str) and result.startswith("0x"):
                    return int(result, 16)
                return int(result)
