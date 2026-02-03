"""
Aggregate harvestable rows from an earnings report, write a harvest plan,
and ask for user confirmation before executing prepared harvest transactions.

Usage:
    python harvest_execute.py [path/to/earnings_report.csv]

Behavior:
 - Reads the CSV (default latest `reports/earnings_report_<today>.csv`).
 - Aggregates rows where `should_harvest` is True.
 - Prepares dry-run transactions via `src.harvester.prepare_harvest_tx`.
 - Writes `reports/harvest_plan_<date>.json` containing prepared txs and totals.
 - Shows totals and prompts the user to confirm execution.
 - If confirmed, calls `src.harvester.execute_harvest_tx` for each prepared tx.

Note: Actual broadcasting requires setting environment `ENABLE_HARVEST=true`.
This script will not broadcast unless that env var is set and the user confirms.
"""

import sys
import os
import csv
import json
from datetime import date
from collections import defaultdict


def load_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def aggregate_harvestable(rows):
    by_netuid = defaultdict(float)
    entries = []
    for r in rows:
        # Normalize should_harvest values
        should = str(r.get('should_harvest', '')).lower() in ('true', '1', 'yes')
        if not should:
            continue
        try:
            net = int(r.get('netuid'))
        except Exception:
            continue
        amt = float(r.get('harvestable_alpha', 0.0))
        by_netuid[net] += amt
        entries.append((net, amt, r))
    return by_netuid, entries


def main():
    # Determine report path
    if len(sys.argv) > 1:
        report_path = sys.argv[1]
    else:
        today = date.today().isoformat()
        report_path = os.path.join('reports', f'earnings_report_{today}.csv')

    if not os.path.exists(report_path):
        print(f"Report not found: {report_path}")
        return

    rows = load_csv(report_path)
    by_netuid, entries = aggregate_harvestable(rows)

    if not entries:
        print("No harvestable rows found in report.")
        return

    total_harvestable = sum(by_netuid.values())

    # Prepare transactions
    prepared = []
    try:
        from src.harvester import prepare_harvest_tx, execute_harvest_tx
    except Exception:
        print("Could not import harvester helper. Ensure src/harvester.py exists.")
        return

    for netuid, amt in by_netuid.items():
        tx = prepare_harvest_tx(int(netuid), float(amt), rows[0].get('address'))
        prepared.append({'netuid': netuid, 'amount_alpha': amt, 'prepared_tx': tx})

    plan = {
        'report_path': report_path,
        'total_harvestable': total_harvestable,
        'per_subnet': dict(by_netuid),
        'prepared': prepared,
    }

    plan_path = os.path.join('reports', f'harvest_plan_{date.today().isoformat()}.json')
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=2)

    print(f"Harvest plan written: {plan_path}")
    print(f"Total harvestable alpha: {total_harvestable:.9f} TAO")
    print("Per-subnet:")
    for net, amt in sorted(by_netuid.items()):
        print(f"  SN{net}: {amt:.9f} TAO")

    # Prompt for confirmation
    ans = input("Proceed to execute prepared transactions? (y/N): ").strip().lower()
    if ans != 'y':
        print("Aborting execution. Transactions remain in dry-run prepared state.")
        return

    # Execute prepared txs (will remain dry-run unless ENABLE_HARVEST=true)
    results = []
    for p in prepared:
        res = execute_harvest_tx(p['prepared_tx'], dry_run=False)
        results.append({'netuid': p['netuid'], 'result': res})
        print(f"Executed netuid {p['netuid']}: {res}")

    results_path = os.path.join('reports', f'harvest_results_{date.today().isoformat()}.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({'results': results}, f, indent=2)

    print(f"Execution results written: {results_path}")


if __name__ == '__main__':
    main()
