"""
Clean repository of historical data artifacts.

Removes:
- Top-level generated CSVs: rewards.csv, harvest.csv, sales.csv, withdrawals.csv
- Reports/*.csv files
- Logs: harvester.log
- Optional: SQLite DB file (harvester.db) if --include-db is passed

Usage:
  python -m src.clean_repository [--include-db]
"""

import os
import glob
from pathlib import Path


def clean(include_db: bool = False) -> dict:
    root = Path(__file__).resolve().parents[1]
    removed = []
    patterns = [
        str(root / "rewards.csv"),
        str(root / "harvest.csv"),
        str(root / "sales.csv"),
        str(root / "withdrawals.csv"),
        str(root / "harvester.log"),
        str(root / "reports" / "*.csv"),
    ]

    for pat in patterns:
        for path in glob.glob(pat):
            try:
                os.remove(path)
                removed.append(path)
            except FileNotFoundError:
                continue
            except Exception:
                continue

    if include_db:
        db_path = root / "harvester.db"
        if db_path.exists():
            try:
                os.remove(db_path)
                removed.append(str(db_path))
            except Exception:
                pass

    return {"removed": removed}


def main():
    import argparse
    p = argparse.ArgumentParser(description="Scrub historical data from repository")
    p.add_argument("--include-db", action="store_true", help="Also delete harvester.db")
    args = p.parse_args()
    res = clean(include_db=args.include_db)
    print(f"Removed {len(res['removed'])} files:")
    for f in res["removed"]:
        print(f" - {f}")


if __name__ == "__main__":
    main()
