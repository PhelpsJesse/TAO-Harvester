"""
Archive Chain Client - TRANSACTION SIGNING ONLY

⚠️  IMPORTANT: This client is for signing and submitting transactions ONLY.

DO NOT use for querying historical balances or emissions data.
Archive RPC (wss://archive.chain.opentensor.ai:443) is heavily rate-limited:
- HTTP 429 on aggressive queries (rejected on connection)
- Not suitable for iterative balance checks
- Use Taostats API (https://api.taostats.io) for balance history

Purpose:
- Sign transactions using wallet seed
- Submit harvests and withdrawals to chain
- Read chain metadata (block number, block hash)

Rate Limiting Implications:
- Do NOT query same address/subnet multiple times in quick succession
- Do NOT query all 300 subnets in a loop
- Use Taostats API for analytics and trend data instead

Future Improvement:
- Consider HTTP RPC fallback if WebSocket is rate-limited
- Implement exponential backoff for 429 responses
- Cache block hashes to minimize queries
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from websockets import connect
import hashlib

from scalecodec import ScaleBytes
from scalecodec.base import RuntimeConfiguration, ScaleDecoder
from scalecodec.type_registry import load_type_registry_preset

from config import HarvesterConfig
from database import Database


class ArchiveChainClient:
    """Client for querying Bittensor archive node via WebSocket."""
    
    def __init__(self, config: HarvesterConfig, db: Database):
        """Initialize archive chain client.
        
        Args:
            config: Harvester configuration
            db: Database instance for tracking last processed block
        """
        self.config = config
        self.db = db
        # Archive node with full block history
        self.ws_url = self.config.archive_rpc_url  # Use config instead of hardcoding
        self.blocks_per_day = 7200  # ~12 second block time = 7200 blocks/day
        
    async def _ws_call(self, method: str, params: Optional[List] = None) -> Dict:
        """Make a WebSocket RPC call.
        
        Uses individual connections with rate limiting to avoid being blocked.
        """
        import time
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or [],
            "id": 1
        }
        
        try:
            async with connect(self.ws_url, ssl=True, close_timeout=5) as websocket:
                await websocket.send(json.dumps(payload))
                response = await websocket.recv()
                result = json.loads(response)
                
                if "error" in result:
                    raise RuntimeError(f"RPC error: {result['error']}")
                
                # Rate limiting: wait between calls
                await asyncio.sleep(0.15)
                
                return result.get("result")
        except Exception as e:
            raise RuntimeError(f"WebSocket call failed: {e}")
    
    async def close(self):
        """No-op for single-connection client."""
        pass
    
    async def get_current_block(self) -> int:
        """Get current block number."""
        header = await self._ws_call("chain_getHeader")
        block_hex = header.get("number", "0x0")
        return int(block_hex, 16)
    
    async def get_block_hash(self, block_number: int) -> str:
        """Get block hash for a specific block number."""
        return await self._ws_call("chain_getBlockHash", [block_number])
    
    async def get_yesterday_block(self, current_block: Optional[int] = None) -> int:
        """Get block number from ~24 hours ago.
        
        DEPRECATED: Use get_block_range() instead for incremental processing.
        """
        if current_block is None:
            current_block = await self.get_current_block()
        
        # Subtract ~7200 blocks (24 hours at 12 sec/block)
        return current_block - self.blocks_per_day
    
    def get_block_range(self, current_block: int) -> Tuple[int, int]:
        """Get block range to process based on last processed block.
        
        Uses database to track last_processed_block. If this is the first run,
        defaults to 1 day worth of blocks.
        
        Args:
            current_block: Current chain block number
            
        Returns:
            Tuple of (start_block, end_block) to process
        """
        last_processed = self.db.get_last_processed_block()
        
        if last_processed is None:
            # First run - default to 1 day of blocks
            start_block = current_block - self.blocks_per_day
            print(f"ℹ️  First run detected. Processing last {self.blocks_per_day:,} blocks (1 day)")
        else:
            # Incremental run - process from last to current
            start_block = last_processed
            blocks_to_process = current_block - start_block
            
            if blocks_to_process <= 0:
                print(f"ℹ️  Already up to date at block {current_block:,}")
                return (current_block, current_block)
            
            hours = (blocks_to_process * 12) / 3600  # 12 sec per block
            print(f"ℹ️  Processing {blocks_to_process:,} blocks (~{hours:.1f} hours since last run)")
        
        return (start_block, current_block)
    
    async def get_runtime_version(self) -> Dict:
        """Get chain runtime version info."""
        return await self._ws_call("state_getRuntimeVersion")
    
    async def get_metadata(self, block_hash: Optional[str] = None) -> str:
        """Get chain metadata (SCALE encoded).
        
        Args:
            block_hash: Optional block hash to get metadata at specific block
            
        Returns:
            Hex-encoded metadata
        """
        params = [block_hash] if block_hash else []
        return await self._ws_call("state_getMetadata", params)
    
    async def query_storage_at_block(
        self, 
        storage_key: str, 
        block_hash: str
    ) -> Optional[str]:
        """
        Query storage at a specific block.
        
        Args:
            storage_key: SCALE-encoded storage key
            block_hash: Block hash to query at
            
        Returns:
            SCALE-encoded storage value (hex string)
        """
        return await self._ws_call("state_getStorageAt", [storage_key, block_hash])
    
    def _encode_storage_key_alpha_balance(self, address: str, netuid: int) -> str:
        """
        Encode storage key for alpha balance query.
        
        Storage path: SubtensorModule.Stake[address][netuid]
        
        Bittensor uses double-map storage for Stake:
        - Key1: AccountId (SS58 address)
        - Key2: u16 (netuid)
        
        Storage key format:
        twox128(pallet) + twox128(storage_item) + 
        blake2_128(key1) + key1_bytes + twox64(key2) + key2_bytes
        
        Args:
            address: SS58 address (e.g., "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY")
            netuid: Subnet ID (e.g., 60)
            
        Returns:
            Hex-encoded storage key
        """
        from scalecodec.utils.ss58 import ss58_decode
        import xxhash
        
        # Pallet and storage item names
        pallet = b"SubtensorModule"
        storage_item = b"Stake"
        
        # Hash pallet name with xxhash128
        pallet_hash = xxhash.xxh128(pallet, seed=0).digest()
        
        # Hash storage item name with xxhash128
        storage_hash = xxhash.xxh128(storage_item, seed=0).digest()
        
        # Decode SS58 address to get account bytes (32 bytes for Substrate)
        try:
            account_bytes = bytes.fromhex(ss58_decode(address))
        except:
            # If ss58_decode fails, try manual decode
            # SS58 addresses are base58 encoded with checksum
            import base58
            decoded = base58.b58decode(address)
            # Remove prefix (1 byte) and checksum (2 bytes)
            account_bytes = decoded[1:-2]
        
        # Hash account with blake2_128
        import hashlib
        account_hash = hashlib.blake2b(account_bytes, digest_size=16).digest()
        
        # Encode netuid as u16 little-endian
        netuid_bytes = netuid.to_bytes(2, byteorder='little')
        
        # Hash netuid with xxhash64
        netuid_hash = xxhash.xxh64(netuid_bytes, seed=0).digest()
        
        # Concatenate all parts
        storage_key = (
            pallet_hash +
            storage_hash +
            account_hash +
            account_bytes +
            netuid_hash +
            netuid_bytes
        )
        
        # Return as hex string with 0x prefix
        return "0x" + storage_key.hex()
    
    async def get_alpha_balance_at_block(
        self, 
        address: str, 
        netuid: int,
        block_number: int
    ) -> float:
        """
        Get alpha balance for address on subnet at specific block.
        
        Args:
            address: SS58 address
            netuid: Subnet ID
            block_number: Block number to query at
            
        Returns:
            Alpha balance as float (converted from RAO - 1 alpha = 10^9 RAO)
        """
        # Get block hash for the block number
        block_hash = await self.get_block_hash(block_number)
        
        # Encode storage key
        storage_key = self._encode_storage_key_alpha_balance(address, netuid)
        
        # Query storage
        result = await self.query_storage_at_block(storage_key, block_hash)
        
        if result is None or result == "0x":
            # No balance (never staked on this subnet)
            return 0.0
        
        # Decode SCALE-encoded u64 (balance in RAO)
        scale_bytes = ScaleBytes(result)
        balance_rao = ScaleDecoder.get_decoder_class('u64').decode(scale_bytes).value
        
        # Convert RAO to alpha (1 alpha = 10^9 RAO)
        balance_alpha = balance_rao / 1_000_000_000
        
        return balance_alpha
    
    async def get_all_alpha_balances_at_block(
        self,
        address: str,
        block_number: int
    ) -> Dict[int, float]:
        """
        Get ALL alpha balances for address across all subnets at specific block.
        
        This is more efficient than querying each subnet individually:
        - 1 query instead of 26+ queries
        - Less likely to hit rate limits
        - Faster overall
        
        Args:
            address: SS58 address
            block_number: Block number to query at
            
        Returns:
            {netuid: alpha_balance} for all subnets where balance > 0
        """
        # Get block hash
        block_hash = await self.get_block_hash(block_number)
        
        # Query storage map for all stakes
        # This queries the entire Stake storage map at once
        storage_key_prefix = self._encode_storage_key_prefix_for_address(address)
        
        # Use state_getKeys to get all storage keys with this prefix
        # Then decode to get netuid and balance
        result = await self._query_storage_map(storage_key_prefix, block_hash)
        
        balances = {}
        for netuid, balance_rao in result.items():
            balance_alpha = balance_rao / 1_000_000_000
            if balance_alpha > 0:
                balances[netuid] = balance_alpha
        
        return balances
    
    def _encode_storage_key_prefix_for_address(self, address: str) -> str:
        """
        Encode storage key prefix to query all stakes for an address.
        This gets all subnet stakes for the address in one query.
        """
        from scalecodec.utils.ss58 import ss58_decode
        import xxhash
        
        pallet = b"SubtensorModule"
        storage_item = b"Stake"
        
        pallet_hash = xxhash.xxh128(pallet, seed=0).digest()
        storage_hash = xxhash.xxh128(storage_item, seed=0).digest()
        
        try:
            account_bytes = bytes.fromhex(ss58_decode(address))
        except:
            import base58
            decoded = base58.b58decode(address)
            account_bytes = decoded[1:-2]
        
        import hashlib
        account_hash = hashlib.blake2b(account_bytes, digest_size=16).digest()
        
        # Prefix includes pallet + storage + account (but NOT netuid)
        # This will match all netuids for this address
        storage_key_prefix = pallet_hash + storage_hash + account_hash + account_bytes
        
        return "0x" + storage_key_prefix.hex()
    
    async def _query_storage_map(
        self,
        key_prefix: str,
        block_hash: str
    ) -> Dict[int, int]:
        """
        Query storage map with given prefix to get all matching entries.
        
        Uses state_getKeys + state_getStorage to fetch all stake entries.
        
        Returns:
            {netuid: balance_rao}
        """
        try:
            # Method 1: Try state_getPairs first (more efficient if supported)
            try:
                pairs = await self._ws_call("state_getPairs", [key_prefix, block_hash])
                if pairs:
                    return self._decode_storage_pairs(pairs)
            except Exception:
                pass  # Fall through to method 2
            
            # Method 2: state_getKeys + individual state_getStorage calls
            keys = await self._ws_call("state_getKeys", [key_prefix, block_hash])
            
            if not keys:
                return {}
            
            balances = {}
            for key in keys:
                # Decode netuid from storage key
                netuid = self._decode_netuid_from_storage_key(key)
                
                # Query storage for this key
                value = await self._ws_call("state_getStorage", [key, block_hash])
                
                if value and value != "0x":
                    # Decode SCALE u64
                    from scalecodec.base import ScaleBytes, ScaleDecoder
                    scale_bytes = ScaleBytes(value)
                    balance_rao = ScaleDecoder.get_decoder_class('u64').decode(scale_bytes).value
                    balances[netuid] = balance_rao
            
            return balances
            
        except Exception as e:
            print(f"Warning: _query_storage_map failed: {e}")
            return {}
    
    def _decode_netuid_from_storage_key(self, key: str) -> int:
        """
        Extract netuid from storage key.
        
        Storage key format: pallet_hash + storage_hash + account_hash + account_bytes + netuid_hash + netuid_bytes
        The netuid is encoded as u16 little-endian at the end.
        """
        # Remove 0x prefix
        key_hex = key[2:] if key.startswith("0x") else key
        
        # Last 2 bytes are netuid (u16 little-endian)
        netuid_bytes = bytes.fromhex(key_hex[-4:])
        netuid = int.from_bytes(netuid_bytes, byteorder='little')
        
        return netuid
    
    def _decode_storage_pairs(self, pairs: list) -> Dict[int, int]:
        """
        Decode result from state_getPairs into {netuid: balance_rao}.
        """
        from scalecodec.base import ScaleBytes, ScaleDecoder
        
        balances = {}
        for pair in pairs:
            key = pair[0]
            value = pair[1]
            
            netuid = self._decode_netuid_from_storage_key(key)
            
            if value and value != "0x":
                scale_bytes = ScaleBytes(value)
                balance_rao = ScaleDecoder.get_decoder_class('u64').decode(scale_bytes).value
                balances[netuid] = balance_rao
        
        return balances
    
    async def get_block_level_emissions(
        self,
        address: str,
        netuids: List[int],
        start_block: int,
        end_block: int,
        delay_ms: int = 200
    ) -> Dict[int, Dict]:
        """
        Get block-level emissions for specific subnets across ALL blocks in range.
        
        OPTIMIZED APPROACH:
        - Query the entire wallet once PER BLOCK (returns all subnets at once)
        - For 100 blocks = 100 queries total (vs 5200 if querying each subnet separately)
        - Stores historical block-by-block data in database
        
        Args:
            address: SS58 address
            netuids: List of subnet IDs to filter results to (from Taostats discovery)
            start_block: Starting block number
            end_block: Ending block number
            delay_ms: Milliseconds to wait between queries (default 200ms for rate-limiting)
        
        Returns:
            {
                netuid: {
                    'start_balance': float,
                    'end_balance': float,
                    'emissions': float,
                    'start_block': int,
                    'end_block': int,
                    'blocks_elapsed': int,
                    'emissions_per_block': float,
                    'block_history': [(block_num, balance), ...]  # All blocks in range
                },
                ...
            }
        """
        blocks_in_range = end_block - start_block + 1
        
        print("=" * 80)
        print(f"BLOCK-LEVEL EMISSIONS QUERY")
        print("=" * 80)
        print(f"Address: {address}")
        print(f"Filter to subnets: {netuids} ({len(netuids)} total)")
        print(f"Block range: {start_block:,} → {end_block:,} ({blocks_in_range} blocks)")
        print(f"Total queries: {blocks_in_range} (1 per block, all subnets at once)")
        print(f"Estimated time: ~{blocks_in_range * delay_ms / 1000:.1f} seconds")
        print(f"Rate limit: {delay_ms}ms between queries")
        print()
        
        # Store all block data for database insertion
        all_block_data = []
        
        # Dictionary to track each subnet's history
        subnet_histories = {}
        
        try:
            # Query each block in the range
            for block_num in range(start_block, end_block + 1):
                progress = ((block_num - start_block + 1) / blocks_in_range) * 100
                print(f"[{progress:5.1f}%] Block {block_num:,}...", end='', flush=True)
                
                # Get ALL subnet balances at this block
                balances = await self.get_all_alpha_balances_at_block(address, block_num)
                
                # Filter to requested subnets
                filtered_balances = {
                    netuid: balance 
                    for netuid, balance in balances.items() 
                    if not netuids or netuid in netuids
                }
                
                print(f" {len(filtered_balances)} subnets")
                
                # Store for database
                for netuid, balance in filtered_balances.items():
                    all_block_data.append({
                        'netuid': netuid,
                        'block_number': block_num,
                        'alpha_balance': balance
                    })
                    
                    # Track history for each subnet
                    if netuid not in subnet_histories:
                        subnet_histories[netuid] = []
                    subnet_histories[netuid].append((block_num, balance))
                
                # Rate limiting
                await asyncio.sleep(delay_ms / 1000.0)
            
            print()
            print(f"✓ Queried {blocks_in_range} blocks successfully")
            print(f"✓ Collected {len(all_block_data)} data points")
            print()
            
            # Store in database
            if all_block_data:
                print("Storing block data in database...")
                self.db.insert_block_balances_batch(address, all_block_data)
                print(f"✓ Stored {len(all_block_data)} records")
                print()
            
            # Calculate emissions summary for each subnet
            emissions = {}
            for netuid, history in subnet_histories.items():
                if not history:
                    continue
                
                # Sort by block number
                history.sort(key=lambda x: x[0])
                
                start_balance = history[0][1]
                end_balance = history[-1][1]
                delta = end_balance - start_balance
                blocks_elapsed = end_block - start_block
                emissions_per_block = delta / blocks_elapsed if blocks_elapsed > 0 else 0
                
                emissions[netuid] = {
                    'start_balance': start_balance,
                    'end_balance': end_balance,
                    'emissions': delta,
                    'start_block': start_block,
                    'end_block': end_block,
                    'blocks_elapsed': blocks_elapsed,
                    'emissions_per_block': emissions_per_block,
                    'block_history': history
                }
            
            # Print summary
            print("=" * 80)
            print("EMISSIONS SUMMARY")
            print("=" * 80)
            
            total_emissions = 0.0
            for netuid in sorted(emissions.keys()):
                data = emissions[netuid]
                total_emissions += data['emissions']
                
                if data['emissions'] > 0:
                    print(f"  ✓ Subnet {netuid}: {data['emissions']:.9f} alpha "
                          f"({data['emissions_per_block']:.12f} per block)")
                elif data['emissions'] < 0:
                    print(f"  - Subnet {netuid}: {data['emissions']:.9f} alpha (decreased)")
                else:
                    print(f"  - Subnet {netuid}: No change")
            
            print()
            print(f"Total emissions: {total_emissions:.9f} alpha")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n✗ Error querying blocks: {e}")
            import traceback
            traceback.print_exc()
            return {}
        
        return emissions
    
    async def get_daily_emissions_estimate(
        self,
        address: str,
        netuids: List[int]
    ) -> Dict[int, Dict]:
        """Estimate emissions by comparing balances between last processed block and current.
        
        Uses incremental processing:
        - First run: Compare current vs 24 hours ago
        - Subsequent runs: Compare current vs last processed block
        
        NOTE: Now implemented with SCALE encoding via scalecodec library.
        """
        try:
            current_block = await self.get_current_block()
            start_block, end_block = self.get_block_range(current_block)
            
            if start_block == end_block:
                return {}  # Already up to date
            
            print(f"Current block: {current_block:,}")
            print(f"Processing range: {start_block:,} → {end_block:,}")
            print()
            
            # Query balances at both blocks and calculate delta
            emissions = {}
            
            for netuid in netuids:
                start_balance = await self.get_alpha_balance_at_block(address, netuid, start_block)
                end_balance = await self.get_alpha_balance_at_block(address, netuid, end_block)
                
                delta = end_balance - start_balance
                
                emissions[netuid] = {
                    'start_balance': start_balance,
                    'end_balance': end_balance,
                    'emissions': delta,
                    'start_block': start_block,
                    'end_block': end_block
                }
            
            return emissions
            
        except Exception as e:
            raise RuntimeError(f"Failed to estimate emissions: {e}")
    
    def mark_processing_complete(self, block_number: int, notes: str = None):
        """Mark a block as successfully processed.
        
        Updates last_processed_block in database.
        
        Args:
            block_number: Block number that was successfully processed
            notes: Optional notes about the processing
        """
        self.db.set_last_processed_block(block_number, notes)
    

# Convenience functions for one-off queries

async def test_archive_connection() -> bool:
    """Test connection to archive node."""
    try:
        config = HarvesterConfig()
        db = Database()
        db.connect()
        
        client = ArchiveChainClient(config, db)
        
        block_num = await client.get_current_block()
        runtime = await client.get_runtime_version()
        
        print(f"✓ Connected to archive node")
        print(f"  Current block: {block_num:,}")
        print(f"  Runtime version: {runtime.get('specVersion')}")
        print(f"  Blocks per day: {client.blocks_per_day:,}")
        
        # Show processing range
        start, end = client.get_block_range(block_num)
        print(f"  Next processing range: {start:,} → {end:,}")
        
        db.disconnect()
        return True
    except Exception as e:
        print(f"✗ Archive node connection failed: {e}")
        return False


async def get_block_range_for_period(days: int = 1) -> Tuple[int, int]:
    """Get block range for a time period.
    
    DEPRECATED: Use ArchiveChainClient.get_block_range() instead.
    """
    config = HarvesterConfig()
    db = Database()
    db.connect()
    
    client = ArchiveChainClient(config, db)
    
    current = await client.get_current_block()
    start = current - (client.blocks_per_day * days)
    
    db.disconnect()
    return start, current


if __name__ == "__main__":
    # Test archive node connectivity
    print("Testing Bittensor Archive Node Connection")
    print("="*80)
    asyncio.run(test_archive_connection())
    
    print("\n" + "="*80)
    print("NOTE: Balance queries require SCALE encoding")
    print("Recommended: Continue using Taostats API for now")
    print("="*80)
