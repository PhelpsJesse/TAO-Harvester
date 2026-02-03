"""
Harvester helper (dry-run safe).

Provides helpers to prepare harvest (convert alpha -> TAO) transactions without
broadcasting. Actual on-chain execution requires RPC credentials and is opt-in
via environment variable `ENABLE_HARVEST=true` and explicit call.

This module returns a simulated transaction payload for review.
"""

import os
import uuid
from typing import Dict, Any


def prepare_harvest_tx(netuid: int, amount_alpha: float, wallet: str) -> Dict[str, Any]:
    """
    Prepare a harvest transaction payload (dry-run).

    Args:
        netuid: Subnet ID
        amount_alpha: Amount of alpha to convert (TAO units)
        wallet: Hotkey address initiating harvest

    Returns:
        Dict representing prepared tx (not broadcast).
    """
    tx_id = str(uuid.uuid4())
    payload = {
        "tx_id": tx_id,
        "netuid": netuid,
        "amount_alpha": float(amount_alpha),
        "wallet": wallet,
        "action": "convert_alpha_to_tao",
        "status": "prepared",
    }
    return payload


def execute_harvest_tx(prepared_tx: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    """
    Execute a prepared harvest transaction.

    If `dry_run` is True or execution is disabled, will NOT broadcast.
    Requires BOTH ENABLE_HARVEST=true AND EXECUTION_ENABLED=true in config.
    """
    enable_env = os.getenv('ENABLE_HARVEST', 'false').lower() == 'true'
    
    # Check config kill switch
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        import config as app_config
        enable_config = app_config.config.EXECUTION_ENABLED
    except:
        enable_config = False
    
    if dry_run or not enable_env or not enable_config:
        return {
            "tx_id": prepared_tx.get('tx_id'),
            "status": "dry_run",
            "message": f"Not broadcast (dry_run={dry_run}, ENABLE_HARVEST={enable_env}, EXECUTION_ENABLED={enable_config})",
        }

    # Placeholder for real broadcast logic
    # Implement on-chain RPC call here when ready (requires key management)
    return {
        "tx_id": prepared_tx.get('tx_id'),
        "status": "broadcasted",
        "message": "Broadcasting not implemented in this helper",
    }
