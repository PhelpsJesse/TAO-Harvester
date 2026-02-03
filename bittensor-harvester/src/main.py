"""
Main orchestrator for the Bittensor harvester.

SIMPLIFIED WORKFLOW:
1. Run import_snapshot.py daily (stores balances in database)
2. Calculate emissions from database snapshots (today - yesterday - transfers)
3. Record emissions in rewards table
4. Check if accumulated alpha >= harvest threshold
5. Execute harvest (alpha → TAO swap via RPC) - NOT YET IMPLEMENTED
6. Sell TAO → USD on Kraken (when TAO balance > threshold)
7. Withdraw USD → checking account (when USD balance > threshold)
8. Export tax CSVs

State management:
- All balances stored in SQLite (alpha_snapshots table)
- Emissions calculated from snapshot deltas
- No RPC queries for balances (Taostats API only)
- RPC only used for alpha→TAO swap execution (when implemented)

Usage:
  # Take daily snapshot first
  python import_snapshot.py --transfers
  
  # Calculate emissions from snapshots
  python calculate_emissions.py
  
  # Run full harvest cycle (dry-run by default)
  python -m src.main --dry-run
  
  # Execute real harvests (after testing)
  python -m src.main
"""

import logging
import sys
from datetime import datetime, timedelta
from src.utils.database import Database
from src.utils.config import HarvesterConfig
from src.harvesting.accounting import Accounting
from src.harvesting.harvest_decision import HarvestPolicy
from src.harvesting.alpha_harvester import Executor
from src.trading.export import TaxExporter
from src.trading.kraken import KrakenClient

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
        accounting = Accounting(db)
        harvest_policy = HarvestPolicy(db, accounting, config.harvest_destination_address)
        executor = Executor(db, chain=None, dry_run=dry_run)  # No chain client needed for dry-run
        tax_exporter = TaxExporter(db)
        kraken = KrakenClient(config.kraken_api_key, config.kraken_api_secret)

        # Create run record
        run_id = db.insert_run(notes=f"Dry-run: {dry_run}")
        result["run_id"] = run_id
        logger.info(f"Run ID: {run_id}")

        # --- 1. Check if we have today's snapshot ---
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()
        
        today_snapshots = db.get_all_snapshots_by_date(config.harvester_wallet_address, today)
        
        if not today_snapshots:
            logger.warning("No snapshots found for today. Run import_snapshot.py first.")
            logger.info("  python import_snapshot.py --transfers")
            return result

        logger.info(f"Found {len(today_snapshots)} subnet snapshots for {today}")

        # --- 2. Compute deltas from database snapshots ---
        logger.info("Computing emissions from database snapshots...")
        subnet_deltas = accounting.compute_all_subnets_delta(
            config.harvester_wallet_address,
            today_date=today,
            yesterday_date=yesterday
        )
        
        total_earned = sum(d['earned_alpha'] for d in subnet_deltas.values())
        result["rewards_earned"] = total_earned
        
        logger.info(f"Total emissions earned: {total_earned:.6f} alpha across {len(subnet_deltas)} subnets")
        
        # Record emissions as rewards
        for netuid, data in subnet_deltas.items():
            if data['earned_alpha'] > 0:
                accounting.record_rewards(
                    address=config.harvester_wallet_address,
                    netuid=netuid,
                    earned_alpha=data['earned_alpha'],
                    block_number=0,  # Not tracking blocks from Taostats
                    tx_hash=None
                )

        # --- 2. Plan harvest ---
        logger.info("Planning harvest...")
        
        # Get total accumulated rewards across all subnets
        accumulated = db.get_accumulated_rewards(netuid=None)  # All subnets
        total_accumulated = sum(accumulated.values()) if isinstance(accumulated, dict) else 0.0
        harvestable = total_accumulated * config.harvest_fraction
        
        logger.info(f"Total accumulated: {total_accumulated:.6f} alpha")
        logger.info(f"Harvestable ({config.harvest_fraction*100:.0f}%): {harvestable:.6f} alpha")

        # Plan
        # Compute weighted conversion rate across subnets using latest subnet_snapshots
        # Weight by accumulated rewards per subnet to reflect harvest allocation
        weighted_rate = 1.0
        try:
            # Get today's subnet snapshots (alpha + tao_per_alpha)
            today_subnet_snaps = db.conn.execute(
                """
                SELECT netuid, alpha_balance, tao_per_alpha
                FROM subnet_snapshots
                WHERE address = ? AND snapshot_date = ?
                """,
                (config.harvester_wallet_address, today),
            ).fetchall()

            per_netuid_rate = {row[0]: (row[2] if row[2] is not None else 1.0) for row in today_subnet_snaps}
            per_netuid_accum = accumulated if isinstance(accumulated, dict) else {}

            # Weighted average: sum(alpha_i * rate_i) / sum(alpha_i)
            numer = sum((per_netuid_accum.get(nuid, 0.0) or 0.0) * (per_netuid_rate.get(nuid, 1.0) or 1.0)
                        for nuid in per_netuid_rate.keys())
            denom = sum((per_netuid_accum.get(nuid, 0.0) or 0.0) for nuid in per_netuid_rate.keys())
            if denom > 0:
                weighted_rate = numer / denom
        except Exception as e:
            logger.warning(f"Could not compute weighted conversion rate; defaulting to 1.0: {e}")

        plan = harvest_policy.plan_harvest(
            harvestable_alpha=harvestable,
            destination_address=config.harvest_destination_address,
            min_threshold=config.min_harvest_threshold_tao,
            max_per_run=config.max_harvest_per_run_tao,
            max_per_day=config.max_harvest_per_day_tao,
            conversion_rate_alpha_to_tao=weighted_rate,
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
        db.finish_run(run_id, last_block=0)  # Not tracking blocks from Taostats
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
