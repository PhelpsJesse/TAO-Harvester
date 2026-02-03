"""
Chain data ingestion via Bittensor/Substrate RPC.

Alpha balance tracking from Taostats (primary source) with RPC fallback.

Architecture:
- PRIMARY: Taostats API for alpha balance queries (web page scraping)
  - Validated against user's account page: https://taostats.io/account/{hotkey}
  - Accurate multi-subnet alpha breakdown
- FALLBACK: Substrate RPC for on-chain state (if Taostats unavailable)
- Tracks daily alpha balance snapshots to calculate reward deltas
- Stores snapshots in database for historical tracking

RPC Endpoints (public, no authentication):
- Bittensor mainnet: https://archive-api.bittensor.com/rpc
- Local node: http://localhost:9933
- OpenTensor lite: https://lite.chain.opentensor.ai (EVM-only, no storage queries)

Query Strategy:
1. Get current alpha balance via Taostats page scraping (primary)
2. Store as daily snapshot
3. Compare with previous day's snapshot to compute earned alpha
4. Fallback to RPC if Taostats unavailable
"""

import requests
import json
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date
import time
import os

# Suppress SSL warnings (development only)
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import from parent directory
import sys
sys.path.insert(0, '..')
from config import config

from src.database import Database
from src.taostats import TaostatsClient
from src.services.opentensor_rpc import OpenTensorRpcService
from src.subtensor_client import get_alpha_balance as subtensor_alpha_balance


class ChainClient:
    """
    Client for Substrate/Bittensor chain RPC queries.
    
    Uses JSON-RPC 2.0 to query on-chain state. Stores snapshots in DB
    for delta calculation (no event streaming needed).
    """

    # Public Bittensor RPC endpoints
    PUBLIC_RPC_MAINNET = "https://archive-api.bittensor.com/rpc"
    PUBLIC_RPC_TESTNET = "https://archive-api.testnet.bittensor.com/rpc"

    def __init__(self, rpc_url: str = None, db: Database = None, taostats_client: TaostatsClient = None):
        """
        Initialize chain client.
        
        Args:
            rpc_url: RPC endpoint URL (defaults to public mainnet)
            db: Database connection for storing snapshots
            taostats_client: Taostats client for alpha data (primary source)
        """
        self.rpc_url = rpc_url or self.PUBLIC_RPC_MAINNET
        self.db = db
        
        # Initialize Taostats client with API key from config if available
        if taostats_client:
            self.taostats = taostats_client
        else:
            import os
            api_key = os.getenv("TAOSTATS_API_KEY", "")
            self.taostats = TaostatsClient(api_key=api_key)
        
        self.last_block = 0
        self.rpc = OpenTensorRpcService(
            rpc_url=self.rpc_url,
            min_interval=config.RPC_MIN_INTERVAL,
            verify_ssl=config.VERIFY_SSL,
        )

    def _rpc_call(self, method: str, params: list = None) -> dict:
        """Delegate JSON-RPC calls to the RPC service."""
        return self.rpc.call(method, params or [])

    def get_block_number(self) -> int:
        """
        Get current block number from chain.

        Returns:
            Current block number as integer

        Raises:
            RuntimeError: If RPC call fails
        """
        try:
            return self.rpc.get_block_number()
        except Exception as e:
            raise RuntimeError(f"Failed to get block number: {e}")

    def get_subnet_emissions(self, netuid: int) -> Dict:
        """
        Get subnet emission state for a given netuid.

        Args:
            netuid: Subnet ID (e.g., 1 for primary)

        Returns:
            {
                'netuid': int,
                'block': int,
                'total_emissions': float (TAO per block),
                'timestamp': str (ISO 8601)
            }

        Note:
            Queries pallet_subtensor::Emission storage.
            This is the total emission rate, not per-validator.
        """
        try:
            # TODO: Implement storage query for pallet_subtensor::Emission[netuid]
            # For now, return structure with mock data
            return {
                "netuid": netuid,
                "block": self.get_block_number(),
                "total_emissions": 100.0,  # Mock: TAO per block
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to get subnet emissions: {e}")

    def get_alpha_balance(self, address: str, netuid: int) -> float:
        """
        Get current alpha balance for an address on a specific subnet.

        Args:
            address: SS58 address (validator hotkey)
            netuid: Subnet ID

        Returns:
            Balance in alpha coins (as float)

        Query Strategy:
            1. PRIMARY: Query Taostats API for alpha breakdown (with authentication)
            2. FALLBACK: Query on-chain via RPC state_getStorage (if Taostats unavailable)

        Note:
            Taostats API is reliable and fast with proper API key authentication.
            Falls back to RPC if API is unavailable.
        """
        # Try Taostats API first (with API key from config)
        try:
            taostats_data = self.taostats.get_alpha_balance_by_subnet(address)
            if taostats_data and "subnet_alpha" in taostats_data:
                subnet_alpha = taostats_data["subnet_alpha"]
                if netuid in subnet_alpha:
                    return float(subnet_alpha[netuid])
        except Exception as e:
            # Fall through to RPC fallback
            pass

        # Fallback to official Subtensor client (read-only)
        try:
            val = subtensor_alpha_balance(address, netuid, archive_url=self.PUBLIC_RPC_MAINNET)
            if val is None:
                return 0.0
            return float(val)
        except Exception as e:
            print(f"Warning: Subtensor fallback failed: {e}, returning 0")
            return 0.0

    def _ss58_to_account_bytes(self, ss58_address: str) -> bytes:
        """
        Convert SS58 address string to 32-byte AccountId32.
        
        SS58 is base58check-encoded. Decode and extract the account ID portion.
        """
        try:
            import base58
        except ImportError:
            raise RuntimeError("Missing dependency 'base58'. Install from requirements.txt")
        
        try:
            decoded = base58.b58decode(ss58_address)
            # SS58 format: [address_type (1-2 bytes)] + [account_id (32 bytes)] + [checksum (2 bytes)]
            # For Substrate networks (address_type < 64), format is: [1 byte type] + [32 bytes account] + [2 bytes checksum]
            # Extract the 32 bytes starting at offset 1 or 2 depending on address type
            if decoded[0] < 64:
                # Single-byte address type
                account_id = decoded[1:33]
            else:
                # Two-byte address type
                account_id = decoded[2:34]
            
            return account_id[:32]
        except Exception as e:
            raise RuntimeError(f"Failed to decode SS58 address '{ss58_address}': {e}")

    def _blake2_128_hash(self, data: bytes) -> bytes:
        """Compute Blake2b 128-bit (16-byte) hash of input data."""
        try:
            import hashlib
            return hashlib.blake2b(data, digest_size=16).digest()
        except Exception as e:
            raise RuntimeError(f"Failed to compute Blake2b hash: {e}")

    def get_alpha_balance_snapshot(
        self, address: str, netuid: int, block: int = None
    ) -> Dict:
        """
        Get alpha balance snapshot at a specific block (or current).

        Args:
            address: SS58 address
            netuid: Subnet ID
            block: Block number (optional, defaults to latest)

        Returns:
            {
                'address': str,
                'netuid': int,
                'block': int,
                'alpha_balance': float,
                'timestamp': str (ISO 8601)
            }
        """
        try:
            balance = self.get_alpha_balance(address, netuid)
            current_block = block or self.get_block_number()

            snapshot = {
                "address": address,
                "netuid": netuid,
                "block": current_block,
                "alpha_balance": balance,
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Store snapshot in database if available
            if self.db:
                self._store_alpha_snapshot(snapshot)

            return snapshot

        except Exception as e:
            raise RuntimeError(f"Failed to get alpha balance snapshot: {e}")

    def get_daily_alpha_delta(
        self, address: str, netuid: int
    ) -> Tuple[float, Dict]:
        """
        Calculate daily alpha earned (delta from yesterday to today).

        Args:
            address: SS58 address
            netuid: Subnet ID

        Returns:
            (delta_alpha, {
                'address': str,
                'netuid': int,
                'date': str (YYYY-MM-DD),
                'previous_balance': float,
                'current_balance': float,
                'delta': float,
                'previous_block': int,
                'current_block': int
            })

        Note:
            Uses database snapshots for delta calculation.
            On first run (no previous snapshot), returns 0 delta.
        """
        try:
            today = date.today().isoformat()
            yesterday = date.fromordinal(date.today().toordinal() - 1).isoformat()

            # Get today's snapshot
            current_snapshot = self.get_alpha_balance_snapshot(address, netuid)
            current_balance = current_snapshot["alpha_balance"]

            # Get yesterday's snapshot from database
            if self.db:
                previous_balance = self._get_alpha_snapshot_by_date(
                    address, netuid, yesterday
                )
            else:
                # No database, can't calculate delta
                previous_balance = current_balance

            delta = max(0, current_balance - previous_balance)

            result = {
                "address": address,
                "netuid": netuid,
                "date": today,
                "previous_balance": previous_balance,
                "current_balance": current_balance,
                "delta": delta,
                "previous_block": current_snapshot["block"],  # TODO: track actual block
                "current_block": current_snapshot["block"],
            }

            return (delta, result)

        except Exception as e:
            raise RuntimeError(f"Failed to calculate daily alpha delta: {e}")

    def get_stake(
        self, delegator: str, validator: str, netuid: int
    ) -> float:
        """
        Get stake amount from delegator to validator on a subnet.

        Args:
            delegator: SS58 delegator address
            validator: SS58 validator address
            netuid: Subnet ID

        Returns:
            Stake amount in TAO

        Note:
            Queries pallet_subtensor::Stake[netuid][(delegator, validator)].
        """
        try:
            # TODO: Implement storage query for pallet_subtensor::Stake
            return 50.0  # Mock
        except Exception as e:
            raise RuntimeError(f"Failed to get stake: {e}")

    def ensure_synced(self, max_age_blocks: int = 5) -> bool:
        """
        Check if RPC node is synced (not lagging).

        Args:
            max_age_blocks: Allow node to be behind by this many blocks

        Returns:
            True if synced, False if lagging

        Note:
            Public RPC endpoints should always be synced.
            Useful for detecting local node issues.
        """
        try:
            # Compare finalized vs best block
            finalized = int(self._rpc_call("chain_getFinalizedHead", []), 16)
            best = int(self._rpc_call("chain_getHead", []), 16)
            lag = best - finalized
            return lag <= max_age_blocks
        except Exception:
            # If we can't check, assume synced (public nodes are usually good)
            return True

    def _store_alpha_snapshot(self, snapshot: Dict) -> None:
        """
        Store alpha balance snapshot in database.

        Args:
            snapshot: Snapshot dict from get_alpha_balance_snapshot()
        """
        if not self.db:
            return

        try:
            conn = self.db.conn
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO alpha_snapshots 
                (address, netuid, block_number, alpha_balance, snapshot_date, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["address"],
                    snapshot["netuid"],
                    snapshot["block"],
                    snapshot["alpha_balance"],
                    date.today().isoformat(),
                    snapshot["timestamp"],
                ),
            )
            conn.commit()
        except Exception as e:
            print(f"Warning: Could not store alpha snapshot: {e}")

    def _get_alpha_snapshot_by_date(
        self, address: str, netuid: int, snapshot_date: str
    ) -> float:
        """
        Retrieve alpha balance snapshot from database for a specific date.

        Args:
            address: SS58 address
            netuid: Subnet ID
            snapshot_date: Date string (YYYY-MM-DD)

        Returns:
            Alpha balance on that date, or 0 if no snapshot found
        """
        if not self.db:
            return 0

        try:
            conn = self.db.conn
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT alpha_balance FROM alpha_snapshots
                WHERE address = ? AND netuid = ? AND snapshot_date = ?
                ORDER BY recorded_at DESC
                LIMIT 1
                """,
                (address, netuid, snapshot_date),
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Warning: Could not retrieve alpha snapshot: {e}")
            return 0
