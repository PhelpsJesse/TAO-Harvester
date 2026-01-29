"""Integration test: run a full harvest cycle with mock data."""

import tempfile
import os
from datetime import datetime
from src.database import Database
from src.config import HarvesterConfig
from src.chain import ChainClient
from src.accounting import Accounting
from src.harvest import HarvestPolicy
from src.executor import Executor
from src.export import TaxExporter


def test_full_cycle():
    """Run a complete harvest cycle (mock)."""
    print("\n" + "="*60)
    print("Testing Full Harvest Cycle (Mock Data)")
    print("="*60 + "\n")

    # Setup
    temp_fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(temp_fd)
    temp_dir = tempfile.mkdtemp()

    try:
        # Initialize components
        config = HarvesterConfig()
        config.db_path = temp_db
        config.harvest_destination_address = "5GrwvmD1HARVESTDEST"
        
        db = Database(temp_db)
        db.connect()
        
        chain = ChainClient()
        accounting = Accounting(db, chain)
        policy = HarvestPolicy(db, accounting, config.harvest_destination_address)
        executor = Executor(db, chain, dry_run=True)
        exporter = TaxExporter(db, temp_dir)

        # --- Simulate earning rewards ---
        print("Step 1: Record rewards earned")
        block = 12345
        earned_alpha = 15.0
        print(f"  Earned {earned_alpha} alpha on block {block}")
        
        db.insert_reward(
            netuid=1,
            block_number=block,
            alpha_amount=earned_alpha,
            tx_hash="0xMOCK123",
        )

        # --- Check harvestable amount ---
        print("\nStep 2: Calculate harvestable amount")
        harvestable = accounting.get_harvestable_amount(netuid=1, harvest_fraction=0.5)
        print(f"  Total accumulated: {harvestable['total_accumulated']:.12f} alpha")
        print(f"  Harvestable (50%): {harvestable['harvestable']:.12f} alpha")

        # --- Plan harvest ---
        print("\nStep 3: Plan harvest")
        plan = policy.plan_harvest(
            harvestable_alpha=harvestable["harvestable"],
            destination_address=config.harvest_destination_address,
            min_threshold=0.1,
            max_per_run=100.0,
            max_per_day=500.0,
        )
        print(f"  Can proceed: {plan['can_proceed']}")
        print(f"  Reason: {plan['reason']}")
        
        if plan["can_proceed"]:
            harvest_plan = plan["harvest_plan"]
            print(f"  Plan: {harvest_plan['alpha_amount']:.12f} alpha → {harvest_plan['tao_amount']:.12f} TAO")

            # --- Queue harvest ---
            print("\nStep 4: Queue harvest")
            harvest_id = policy.queue_harvest(
                alpha_amount=harvest_plan["alpha_amount"],
                tao_amount=harvest_plan["tao_amount"],
                destination_address=harvest_plan["destination"],
            )
            print(f"  Queued harvest ID: {harvest_id}")

            # --- Execute harvest ---
            print("\nStep 5: Execute harvest (dry-run)")
            exec_result = executor.execute_harvest(
                harvest_id=harvest_id,
                alpha_amount=harvest_plan["alpha_amount"],
                tao_destination=harvest_plan["destination"],
            )
            print(f"  Success: {exec_result['success']}")
            print(f"  TX Hash: {exec_result['tx_hash']}")
            print(f"  Reason: {exec_result['reason']}")

        # --- Export CSVs ---
        print("\nStep 6: Export tax CSVs")
        exports = exporter.export_all(temp_dir)
        for key, path in exports.items():
            print(f"  {key}: {os.path.basename(path)}")
            # Show file contents
            with open(path, 'r') as f:
                lines = f.readlines()
                print(f"    Lines: {len(lines)}")
                if len(lines) > 1:
                    print(f"    Header: {lines[0].strip()}")
                    if len(lines) > 2:
                        print(f"    First row: {lines[1].strip()}")

        print("\n" + "="*60)
        print("Full Cycle Test Completed Successfully!")
        print("="*60 + "\n")
        
        return True

    finally:
        db.disconnect()
        if os.path.exists(temp_db):
            os.remove(temp_db)
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_full_cycle()
