"""
Execution of on-chain actions.

Handles:
- Alpha → TAO swaps (using Bittensor RPC)
- TAO transfers to harvest destination (Kraken deposit address)
- Balance checks before actions

Safety measures:
- Allowlist-only destinations
- Pre-flight checks
- Dry-run support
- EXECUTION_ENABLED config flag

===================================================================================
CRITICAL: ALPHA → TAO SWAP IMPLEMENTATION
===================================================================================

This executor needs RPC access to submit signed extrinsics for alpha→TAO swaps.

BEFORE ENABLING:
1. Verify swap mechanism on Bittensor testnet
2. Test with small amounts first
3. Confirm extrinsic format matches current chain spec
4. Ensure signing key is secure (use hardware wallet or encrypted keystore)
5. Set EXECUTION_ENABLED=true in .env only after thorough testing

REQUIRED IMPLEMENTATION:
- Use src/services/opentensor_rpc.py for RPC calls
- Sign extrinsics with harvester wallet private key
- Submit swap transaction to convert alpha → TAO
- Wait for finalization and verify balances changed correctly
- Record tx_hash in database

RPC ENDPOINTS (for reference):
- Mainnet: https://archive-api.bittensor.com/rpc
- Testnet: https://archive-api.testnet.bittensor.com/rpc

SUBSTRATE EXTRINSIC FORMAT (example - VERIFY CURRENT SPEC):
{
  "pallet": "SubtensorModule",
  "call": "swap_alpha_for_tao",
  "args": {
    "netuid": <subnet_id>,
    "amount": <amount_in_rao>
  }
}

STATUS: NOT IMPLEMENTED - Currently returns mock data only
===================================================================================
"""

from typing import Dict, Optional
from datetime import datetime
from src.database import Database
from src.chain import ChainClient


class Executor:
    """Executes on-chain harvesting actions."""

    def __init__(self, db: Database, chain: ChainClient = None, dry_run: bool = True):
        """
        Initialize executor.

        Args:
            db: Database instance
            chain: Chain client (optional - needed for RPC submission)
            dry_run: If True, don't submit transactions (DEFAULT: True for safety)
        """
        self.db = db
        self.chain = chain
        self.dry_run = dry_run

    def preflight_harvest(
        self, alpha_amount: float, tao_destination: str
    ) -> Dict:
        """
        Pre-flight checks before harvest execution.

        Returns:
            {'ok': bool, 'reason': str, 'issues': [str]}
        """
        issues = []

        # Check alpha balance
        # TODO: Implement real balance check from chain
        current_alpha = 100.0  # Mock
        if alpha_amount > current_alpha:
            issues.append(
                f"Insufficient alpha balance ({alpha_amount} > {current_alpha})"
            )

        # Check TAO destination is accessible
        # TODO: Implement real check (e.g., address validation)
        if not tao_destination.startswith("5"):
            issues.append(f"Invalid destination format: {tao_destination}")

        return {
            "ok": len(issues) == 0,
            "reason": "Preflight OK" if not issues else "Preflight failed",
            "issues": issues,
        }

    def execute_harvest(
        self,
        harvest_id: int,
        alpha_amount: float,
        tao_destination: str,
        conversion_rate: float = 1.0,
    ) -> Dict:
        """
        Execute a harvest action.

        Steps:
        1. Pre-flight checks
        2. Construct extrinsic (alpha → TAO + transfer)
        3. Sign with harvester key
        4. Submit (or dry-run)
        5. Record result

        Args:
            harvest_id: Database harvest record ID
            alpha_amount: Amount of alpha to harvest
            tao_destination: Where to send TAO
            conversion_rate: Rate for conversion

        Returns:
            {
                'success': bool,
                'tx_hash': str or None,
                'reason': str,
                'dry_run': bool
            }
        """
        # Pre-flight
        check = self.preflight_harvest(alpha_amount, tao_destination)
        if not check["ok"]:
            return {
                "success": False,
                "tx_hash": None,
                "reason": f"Preflight failed: {'; '.join(check['issues'])}",
                "dry_run": self.dry_run,
            }

        # Build extrinsic
        # TODO: Real Substrate extrinsic construction
        tao_amount = alpha_amount * conversion_rate
        extrinsic = self._build_harvest_extrinsic(alpha_amount, tao_amount, tao_destination)

        # Sign and submit
        if self.dry_run:
            tx_hash = f"0x{'0' * 64}"  # Mock hash
            result = {
                "success": True,
                "tx_hash": tx_hash,
                "reason": f"Dry run: would harvest {alpha_amount} alpha -> {tao_amount} TAO to {tao_destination}",
                "dry_run": True,
            }
        else:
            # TODO: Sign and submit real extrinsic
            tx_hash = self._submit_extrinsic(extrinsic)
            result = {
                "success": bool(tx_hash),
                "tx_hash": tx_hash,
                "reason": "Submitted" if tx_hash else "Submission failed",
                "dry_run": False,
            }

        # Record in database
        if result["success"]:
            cursor = self.db.conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """
                UPDATE harvests
                SET status = ?, tx_hash = ?, executed_at = ?
                WHERE id = ?
                """,
                ("completed", tx_hash, now, harvest_id),
            )
            self.db.conn.commit()

        return result

    def _build_harvest_extrinsic(
        self, alpha_amount: float, tao_amount: float, destination: str
    ) -> Dict:
        """
        Build Substrate extrinsic for alpha→TAO swap.

        TODO: Implement using real Substrate API client (substrateinterface or py-substrate-interface).
        
        Steps:
        1. Create ExtrinsicCall for swap_alpha_for_tao
        2. Sign with harvester wallet keypair
        3. Return signed extrinsic ready for submission
        
        Current implementation: Returns mock structure only.
        """
        # MOCK - Replace with real implementation
        return {
            "pallet": "SubtensorModule",
            "call": "swap_alpha_for_tao",
            "args": {
                "netuid": 1,  # TODO: Pass netuid from caller
                "amount_rao": int(alpha_amount * 1e9),  # Convert alpha to rao (smallest unit)
            },
            "destination": destination,  # For transfer after swap
        }

    def _submit_extrinsic(self, extrinsic: Dict) -> Optional[str]:
        """
        Sign and submit extrinsic to chain via RPC.

        TODO: Implement using RPC service and signing.
        
        Required:
        1. Get RPC client from self.chain or src/services/opentensor_rpc.py
        2. Sign extrinsic with private key (SECURE KEY MANAGEMENT REQUIRED)
        3. Submit via author_submitExtrinsic RPC method
        4. Wait for inclusion in block
        5. Return transaction hash
        
        Security notes:
        - Never log or print private keys
        - Use hardware wallet or encrypted keystore
        - Test on testnet first
        - Verify extrinsic format matches current chain spec
        
        Current implementation: Returns None (not implemented)
        """
        # TODO: Real implementation
        # Example structure:
        # rpc_client = self.chain.rpc if self.chain else None
        # if not rpc_client:
        #     raise RuntimeError("No RPC client available for extrinsic submission")
        #
        # signed_extrinsic = sign_extrinsic(extrinsic, private_key)
        # tx_hash = rpc_client.call("author_submitExtrinsic", [signed_extrinsic])
        # return tx_hash
        
        return None

    def check_execution_status(self, tx_hash: str) -> Dict:
        """
        Check if a transaction is finalized.

        Returns:
            {'finalized': bool, 'block': int or None, 'error': str or None}
        """
        # TODO: Implement via chain RPC (check finalized blocks)
        return {"finalized": True, "block": 12345, "error": None}
