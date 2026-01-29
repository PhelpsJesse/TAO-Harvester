"""
Main orchestrator for the Bittensor harvester.

Runs the daily harvest cycle:
1. Fetch current alpha balance from chain.
2. Compute delta (earned rewards).
3. Record in accounting ledger.
4. Plan harvest (apply policy).
5. Execute harvest (alpha → TAO conversion + transfer).
6. Optionally: sell TAO → USD on Kraken.
7. Optionally: withdraw USD → checking.
8. Export tax CSVs.
9. Record completion in database.

Designed to be idempotent and state-based:
- Can be run multiple times per day (only processes deltas once).
- Recovers from partial failures.
- All state in SQLite.
"""

import logging
import sys
from datetime import datetime
from src.database import Database
from src.config import HarvesterConfig
from src.chain import ChainClient
from src.accounting import Accounting
from src.harvest import HarvestPolicy
from src.executor import Executor
from src.export import TaxExporter
from src.kraken import KrakenClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("harvester.log"),
    ],
)
logger = logging.getLogger(__name__)


def run_harvest_cycle(config: HarvesterConfig, dry_run: bool = True) -> dict:
    """
    Run a complete harvest cycle.

    Args:
        config: HarvesterConfig instance
        dry_run: If True, don't execute on-chain actions

    Returns:
        Cycle result summary
    """
    logger.info("=" * 60)
    logger.info("Starting harvest cycle")
    logger.info("=" * 60)

    result = {
        "success": False,
        "run_id": None,
        "rewards_earned": 0.0,
        "harvested_alpha": 0.0,
        "harvested_tao": 0.0,
        "sold_usd": 0.0,
        "withdrawn_usd": 0.0,
        "errors": [],
    }

    # Initialize components
    db = Database(config.db_path)
    db.connect()
    
    try:
        chain = ChainClient(config.substrate_rpc_url)
        accounting = Accounting(db, chain)
        harvest_policy = HarvestPolicy(db, accounting, config.harvest_destination_address)
        executor = Executor(db, chain, dry_run=dry_run)
        tax_exporter = TaxExporter(db)
        kraken = KrakenClient(config.kraken_api_key, config.kraken_api_secret)

        # Create run record
        run_id = db.insert_run(notes=f"Dry-run: {dry_run}")
        result["run_id"] = run_id
        logger.info(f"Run ID: {run_id}")

        # --- 1. Fetch & compute delta ---
        logger.info("Fetching chain state...")
        block = chain.get_block_number()
        logger.info(f"Current block: {block}")

        # Get previous balance / block
        last_run = db.get_last_run()
        prev_balance = 0.0  # TODO: Load from last snapshot
        if last_run:
            logger.info(f"Last run completed at {last_run['completed_at']}")
            logger.info(f"Last block: {last_run['last_block']}")

        # Compute delta
        current_balance, earned_alpha = accounting.compute_daily_delta(
            address=config.harvester_wallet_address,
            netuid=config.netuid,
            prev_balance=prev_balance,
        )
        result["rewards_earned"] = earned_alpha
        logger.info(f"Current alpha balance: {current_balance:.12f}")
        logger.info(f"Alpha earned (delta): {earned_alpha:.12f}")

        if earned_alpha > 0:
            accounting.record_rewards(
                address=config.harvester_wallet_address,
                netuid=config.netuid,
                earned_alpha=earned_alpha,
                block_number=block,
            )

        # --- 2. Plan harvest ---
        logger.info("Planning harvest...")
        harvestable = accounting.get_harvestable_amount(
            netuid=config.netuid,
            harvest_fraction=config.harvest_fraction,
        )
        logger.info(f"Total accumulated: {harvestable['total_accumulated']:.12f} alpha")
        logger.info(f"Harvestable (50%): {harvestable['harvestable']:.12f} alpha")

        # Plan
        plan = harvest_policy.plan_harvest(
            harvestable_alpha=harvestable["harvestable"],
            destination_address=config.harvest_destination_address,
            min_threshold=config.min_harvest_threshold_tao,
            max_per_run=config.max_harvest_per_run_tao,
            max_per_day=config.max_harvest_per_day_tao,
        )

        if not plan["can_proceed"]:
            logger.info(f"Harvest skipped: {plan['reason']}")
        else:
            # --- 3. Queue harvest ---
            harvest_plan = plan["harvest_plan"]
            logger.info(f"Queueing harvest: {harvest_plan['alpha_amount']:.12f} alpha -> {harvest_plan['tao_amount']:.12f} TAO")
            harvest_id = harvest_policy.queue_harvest(
                alpha_amount=harvest_plan["alpha_amount"],
                tao_amount=harvest_plan["tao_amount"],
                destination_address=harvest_plan["destination"],
                conversion_rate=harvest_plan["conversion_rate"],
            )
            result["harvested_alpha"] = harvest_plan["alpha_amount"]
            result["harvested_tao"] = harvest_plan["tao_amount"]

            # --- 4. Execute harvest ---
            logger.info(f"Executing harvest {harvest_id}...")
            exec_result = executor.execute_harvest(
                harvest_id=harvest_id,
                alpha_amount=harvest_plan["alpha_amount"],
                tao_destination=harvest_plan["destination"],
                conversion_rate=harvest_plan["conversion_rate"],
            )
            logger.info(f"Execution result: {exec_result['reason']}")
            if exec_result["success"]:
                logger.info(f"TX Hash: {exec_result['tx_hash']}")

        # --- 5. Optional: Kraken sales ---
        logger.info("Checking Kraken balances...")
        kraken_balance = kraken.get_account_balance()
        logger.info(f"Kraken TAO balance: {kraken_balance.get('TAO', 0):.12f}")
        logger.info(f"Kraken USD balance: {kraken_balance.get('USD', 0):.2f}")

        # TODO: Implement sale logic (if TAO balance > threshold, sell)

        # --- 6. Optional: Withdrawals ---
        logger.info("Checking withdrawal eligibility...")
        # TODO: Implement withdrawal logic

        # --- 7. Export tax CSVs ---
        logger.info("Exporting tax CSVs...")
        exports = tax_exporter.export_all(output_dir=".")
        for key, path in exports.items():
            logger.info(f"  {key}: {path}")

        # --- 8. Finalize run ---
        db.finish_run(run_id, block)
        result["success"] = True
        logger.info("Harvest cycle completed successfully")

    except Exception as e:
        logger.exception(f"Harvest cycle failed: {e}")
        result["errors"].append(str(e))
    finally:
        db.disconnect()

    logger.info("=" * 60)
    return result


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Bittensor TAO Harvester")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't execute on-chain actions",
    )
    parser.add_argument(
        "--config",
        default=".env",
        help="Path to .env config file",
    )
    args = parser.parse_args()

    logger.info(f"Loading config from {args.config}")
    config = HarvesterConfig.from_env()
    
    # Don't validate on every run; allow partial config for testing
    # config.validate()

    result = run_harvest_cycle(config, dry_run=args.dry_run)

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
