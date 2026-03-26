import json
import tempfile
import unittest
from pathlib import Path

from v2.tao_harvester.operator_gui import build_preview_summary, suggest_expected_db_date


class TestOperatorGuiHelpers(unittest.TestCase):
    def _write_report(self, payload: dict[str, object]) -> str:
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        path = Path(tmp_dir.name) / "report.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_suggest_expected_db_date_uses_report_date(self):
        path = self._write_report({"report_date": "2026-03-24", "execution_handoff": {"subnets": []}})
        self.assertEqual(suggest_expected_db_date(path), "2026-03-24")

    def test_build_preview_summary_counts_valid_unstakes(self):
        path = self._write_report(
            {
                "report_date": "2026-03-24",
                "execution_handoff": {
                    "subnets": [
                        {"netuid": 1, "alpha_to_harvest": 2.5},
                        {"netuid": 2, "alpha_to_harvest": 0.0},
                        {"netuid": 3, "alpha_to_harvest": 1.25},
                    ]
                },
            }
        )
        summary = build_preview_summary(path)
        self.assertEqual(summary["report_date"], "2026-03-24")
        self.assertEqual(summary["request_count"], 2)
        self.assertEqual(summary["netuids"], [1, 3])
        self.assertAlmostEqual(float(summary["total_alpha_to_unstake"]), 3.75)


if __name__ == "__main__":
    unittest.main()
