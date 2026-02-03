"""
Minimal WebSocket JSON-RPC client for Substrate nodes.

Uses the `websockets` package to call methods like:
- chain_getFinalizedHead
- chain_getHeader
- chain_getBlockHash
- state_getStorage

Note: Read-only operations only.
"""

import asyncio
import json
from typing import Any, List, Optional

import websockets


class WsRpc:
    def __init__(self, url: str):
        self.url = url
        self._id = 1

    async def call_async(self, method: str, params: Optional[List[Any]] = None) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params or [],
        }
        self._id += 1
        async with websockets.connect(self.url, max_size=8 * 1024 * 1024) as ws:
            await ws.send(json.dumps(payload))
            raw = await ws.recv()
            resp = json.loads(raw)
            if "error" in resp:
                raise RuntimeError(f"RPC error: {resp['error']}")
            return resp.get("result")

    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.call_async(method, params))
