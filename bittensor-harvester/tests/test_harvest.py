"""Tests for harvest policy module."""

import unittest
from src.database import Database
from src.chain import ChainClient
from src.accounting import Accounting
from src.harvest import HarvestPolicy
import tempfile
import os


class TestHarvestPolicy(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.temp_fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(self.temp_db)
        self.db.connect()
        
        self.chain = ChainClient()
        self.accounting = Accounting(self.db, self.chain)
        self.policy = HarvestPolicy(
            self.db,
            self.accounting,
            config_harvest_dest="5GrwvmD1test",
        )

    def tearDown(self):
        """Clean up."""
        self.db.disconnect()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_destination_allowlist(self):
        """Test destination allowlisting."""
        # Config destination should be in allowlist
        self.assertTrue(self.policy.is_destination_allowed("5GrwvmD1test"))
        
        # Random address should not be
        self.assertFalse(self.policy.is_destination_allowed("5RandomAddress"))

    def test_plan_harvest_bad_destination(self):
        """Test harvest plan with bad destination."""
        plan = self.policy.plan_harvest(
            harvestable_alpha=10.0,
            destination_address="5BadAddress",
        )
        self.assertFalse(plan["can_proceed"])
        self.assertIn("allowlist", plan["reason"].lower())

    def test_plan_harvest_below_threshold(self):
        """Test harvest plan below threshold."""
        plan = self.policy.plan_harvest(
            harvestable_alpha=0.05,
            destination_address="5GrwvmD1test",
            min_threshold=0.1,
        )
        self.assertFalse(plan["can_proceed"])

    def test_plan_harvest_valid(self):
        """Test valid harvest plan."""
        plan = self.policy.plan_harvest(
            harvestable_alpha=5.0,
            destination_address="5GrwvmD1test",
            min_threshold=0.1,
            max_per_run=10.0,
        )
        self.assertTrue(plan["can_proceed"])
        self.assertIsNotNone(plan["harvest_plan"])
        self.assertAlmostEqual(plan["harvest_plan"]["alpha_amount"], 5.0)

    def test_queue_harvest(self):
        """Test queueing a harvest."""
        harvest_id = self.policy.queue_harvest(
            alpha_amount=5.0,
            tao_amount=5.0,
            destination_address="5GrwvmD1test",
        )
        self.assertIsNotNone(harvest_id)
        
        # Check it was recorded
        pending = self.policy.get_pending_harvests()
        self.assertEqual(len(pending), 1)


if __name__ == "__main__":
    unittest.main()
