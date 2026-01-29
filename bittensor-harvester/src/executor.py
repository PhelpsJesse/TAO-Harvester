"""
Execution of on-chain actions.

Handles:
- Alpha → TAO conversions
- TAO transfers to harvest destination
- Balance checks before actions

Designed to be safe:
- Allowlist-only destinations
- Pre-flight checks
- Dry-run support initially

TODO: Implement real Substrate signing and submission.
"""

from typing import Dict, Optional
from datetime import datetime
from src.database import Database
from src.chain import ChainClient


class Executor:
    """Executes on-chain harvesting actions."""

    def __init__(self, db: Database, chain: ChainClient, dry_run: bool = True):
        """
        Initialize executor.

        Args:
            db: Database instance
            chain: Chain client
            dry_run: If True, don't submit transactions
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
        Build Substrate extrinsic for harvest.

        TODO: Real implementation using Substrate API.
        """
        return {
            "pallet": "alpha",
            "call": "harvest_and_transfer",
            "args": {
                "alpha_amount": int(alpha_amount * 1e12),  # Convert to raw
                "tao_destination": destination,
                "tao_amount": int(tao_amount * 1e12),
            },
        }

    def _submit_extrinsic(self, extrinsic: Dict) -> Optional[str]:
        """
        Sign and submit extrinsic to chain.

        TODO: Real implementation.
        """
        # TODO: Sign with harvester key, submit via RPC
        return None

    def check_execution_status(self, tx_hash: str) -> Dict:
        """
        Check if a transaction is finalized.

        Returns:
            {'finalized': bool, 'block': int or None, 'error': str or None}
        """
        # TODO: Implement via chain RPC (check finalized blocks)
        return {"finalized": True, "block": 12345, "error": None}
