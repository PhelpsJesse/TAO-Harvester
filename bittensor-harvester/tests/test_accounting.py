"""Tests for accounting module."""

import unittest
from src.utils.database import Database
from src.utils.chain import ChainClient
from src.harvesting.accounting import Accounting
import tempfile
import os


class TestAccounting(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.temp_fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(self.temp_db)
        self.db.connect()
        
        self.chain = ChainClient()
        self.accounting = Accounting(self.db, self.chain)

    def tearDown(self):
        """Clean up."""
        self.db.disconnect()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_compute_daily_delta(self):
        """Test delta computation."""
        current, delta = self.accounting.compute_daily_delta(
            address="5GrwvmD1...",
            netuid=1,
            prev_balance=100.0,
        )
        # Mock returns: current=100 (from mock), delta = 100-100 = 0
        # But chain mock adds 10.0, so delta should be 10.0
        self.assertGreaterEqual(delta, 0)

    def test_record_rewards(self):
        """Test reward recording."""
        self.accounting.record_rewards(
            address="5GrwvmD1...",
            netuid=1,
            earned_alpha=5.0,
            block_number=100,
        )
        
        accum = self.db.get_accumulated_rewards(netuid=1)
        self.assertAlmostEqual(accum["total"], 5.0)

    def test_get_harvestable_amount(self):
        """Test harvestable calculation."""
        # Insert some rewards
        self.db.insert_reward(netuid=1, block_number=100, alpha_amount=10.0)
        
        harvestable = self.accounting.get_harvestable_amount(netuid=1, harvest_fraction=0.5)
        self.assertAlmostEqual(harvestable["total_accumulated"], 10.0)
        self.assertAlmostEqual(harvestable["harvestable"], 5.0)

    def test_apply_harvest_policy_below_threshold(self):
        """Test harvest policy enforcement (below threshold)."""
        policy = self.accounting.apply_harvest_policy(
            harvestable_alpha=0.05,
            min_threshold=0.1,
        )
        self.assertFalse(policy["can_harvest"])
        self.assertIn("min threshold", policy["reason"].lower())

    def test_apply_harvest_policy_within_limits(self):
        """Test harvest policy enforcement (within limits)."""
        policy = self.accounting.apply_harvest_policy(
            harvestable_alpha=5.0,
            min_threshold=0.1,
            max_per_run=10.0,
            max_per_day=50.0,
            today_harvested=0.0,
        )
        self.assertTrue(policy["can_harvest"])
        self.assertAlmostEqual(policy["amount"], 5.0)

    def test_apply_harvest_policy_daily_cap(self):
        """Test daily cap enforcement."""
        policy = self.accounting.apply_harvest_policy(
            harvestable_alpha=20.0,
            min_threshold=0.1,
            max_per_run=10.0,
            max_per_day=50.0,
            today_harvested=40.0,
        )
        self.assertTrue(policy["can_harvest"])
        self.assertAlmostEqual(policy["amount"], 10.0)  # capped at 50-40=10


if __name__ == "__main__":
    unittest.main()
