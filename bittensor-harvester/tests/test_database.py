"""Tests for database module."""

import unittest
import tempfile
import os
from datetime import datetime
from src.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        """Create temp database for testing."""
        self.temp_fd, self.temp_db = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_fd)
        self.db = Database(self.temp_db)
        self.db.connect()

    def tearDown(self):
        """Clean up temp database."""
        self.db.disconnect()
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_schema_creation(self):
        """Test that schema is created."""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected = {"runs", "rewards", "harvests", "daily_caps", "kraken_sales", "withdrawals", "config_state"}
        self.assertTrue(expected.issubset(tables))

    def test_insert_reward(self):
        """Test reward insertion."""
        self.db.insert_reward(
            netuid=1,
            block_number=100,
            alpha_amount=10.0,
            tx_hash="0xabc123",
        )
        
        accum = self.db.get_accumulated_rewards(netuid=1)
        self.assertAlmostEqual(accum["total"], 10.0)

    def test_get_accumulated_rewards(self):
        """Test reward accumulation."""
        self.db.insert_reward(netuid=1, block_number=100, alpha_amount=5.0)
        self.db.insert_reward(netuid=1, block_number=101, alpha_amount=3.0)
        self.db.insert_reward(netuid=2, block_number=100, alpha_amount=2.0)
        
        rewards_1 = self.db.get_accumulated_rewards(netuid=1)
        self.assertAlmostEqual(rewards_1["total"], 8.0)
        
        rewards_all = self.db.get_accumulated_rewards()
        self.assertAlmostEqual(rewards_all[1], 8.0)
        self.assertAlmostEqual(rewards_all[2], 2.0)

    def test_harvest_insertion(self):
        """Test harvest insertion."""
        self.db.insert_harvest(
            harvest_date="2024-01-15",
            alpha_amount=8.0,
            tao_amount=8.0,
            destination_address="5GrwvmD1...",
            conversion_rate=1.0,
        )
        
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM harvests")
        count = cursor.fetchone()[0]
        self.assertEqual(count, 1)

    def test_daily_caps(self):
        """Test daily cap tracking."""
        date = "2024-01-15"
        self.db.update_daily_harvest(date, 5.0, 50.0)
        self.db.update_daily_harvest(date, 3.0, 50.0)
        
        total = self.db.get_daily_total_harvest(date)
        self.assertAlmostEqual(total, 8.0)

    def test_config_state(self):
        """Test config state storage."""
        self.db.set_config_state("test_key", "test_value")
        value = self.db.get_config_state("test_key")
        self.assertEqual(value, "test_value")

        # Update
        self.db.set_config_state("test_key", "new_value")
        value = self.db.get_config_state("test_key")
        self.assertEqual(value, "new_value")


if __name__ == "__main__":
    unittest.main()
