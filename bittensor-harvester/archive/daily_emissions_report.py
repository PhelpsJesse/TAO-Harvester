#!/usr/bin/env python3
"""
TAO Harvester - Daily Emissions Tracker

Tracks daily alpha earnings from validator emissions by:
1. Fetching current alpha balances from Taostats API
2. Storing snapshots in database
3. Calculating daily delta by comparing to previous day
4. Generating CSV report with alpha values and TAO estimates

Usage:
    python daily_emissions_report.py

Output:
    - Console: Summary of holdings and daily earnings
    - CSV: reports/daily_emissions_YYYY-MM-DD.csv
    - Database: harvester.db (daily_snapshots table)

Notes:
    - Alpha values are stored (not TAO) for accuracy over time
    - TAO estimates are calculated only for display
    - Taostats free tier = 5 API calls/minute (may return incomplete data)
    - Run daily to track emission trends
"""

import sys
import csv
import sqlite3
from datetime import date
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

# Import from parent config.py (not src/config.py)
sys.path.insert(0, '.')
import config as app_config
from chain import ChainClient
from alpha_swap import AlphaSwap


def init_database(db_path):
    """Initialize database with snapshots table."""
    conn = sqlite3.connect(db_path)
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            address TEXT NOT NULL,
            netuid INTEGER NOT NULL,
            alpha_balance REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, address, netuid)
        )
    ''')
    conn.commit()
    
    return conn


def get_previous_snapshot(conn, address, netuid, yesterday):
    """Get alpha balance from previous day's snapshot."""
    cursor = conn.execute(
        'SELECT alpha_balance FROM daily_snapshots WHERE date = ? AND address = ? AND netuid = ?',
        (yesterday, address, netuid)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def store_snapshot(conn, address, netuid, alpha_balance, today):
    """Store today's alpha balance snapshot."""
    conn.execute(
        'INSERT OR REPLACE INTO daily_snapshots (date, address, netuid, alpha_balance) VALUES (?, ?, ?, ?)',
        (today, address, netuid, alpha_balance)
    )


def estimate_tao_value(netuid, alpha_amount, address):
    """Estimate TAO value for alpha amount using AlphaSwap."""
    try:
        swap = AlphaSwap(netuid, address)
        return swap.estimate_tao_output(alpha_amount)
    except Exception:
        # Fallback rough estimate if AlphaSwap fails
        return alpha_amount * 0.01


def main():
    """Main execution function."""
    
    # Get validator addresses from config
    validators = app_config.config.get_validator_addresses()
    if not validators:
        print("ERROR: No validator addresses configured")
        print("Set VALIDATOR_HOTKEYS in .env file")
        return 1
    
    address = validators[0]  # Use first validator
    
    print("=" * 70)
    print("TAO HARVESTER - Daily Emissions Tracker")
    print("=" * 70)
    print(f"Validator: {address}")
    print(f"RPC: {app_config.config.RPC_URL}")
    print(f"Database: {app_config.config.DATABASE_PATH}")
    print("=" * 70)
    print()
    
    # Validate configuration
    warnings = app_config.config.validate()
    if warnings:
        print("Configuration Warnings:")
        for warning in warnings:
            print(f"   - {warning}")
        print()
    
    # Initialize database
    conn = init_database(app_config.config.DATABASE_PATH)
    
    # Initialize chain client with Taostats API key
    chain_client = ChainClient(rpc_url=app_config.config.RPC_URL, db=None)
    
    # Fetch all subnet balances from Taostats
    print("Fetching subnet balances from Taostats API...")
    print(f"(Rate limit: {app_config.config.TAOSTATS_RATE_LIMIT} requests/minute)")
    print()
    
    try:
        taostats_data = chain_client.taostats.get_alpha_balance_by_subnet(address)
        all_subnets = taostats_data.get("subnet_alpha", {})
        
        print(f"[OK] Fetched {len(all_subnets)} subnets with holdings")
        
        if len(all_subnets) < 20:
            print()
            print(f"WARNING: Only {len(all_subnets)} subnets returned (you may have ~25)")
            print(f"   Taostats free tier is rate-limited to {app_config.config.TAOSTATS_RATE_LIMIT} requests/minute")
            print(f"   Wait a few minutes and retry, or check manually:")
            print(f"   https://taostats.io/account/{address}")
        print()
        
    except Exception as e:
        print(f"ERROR: Could not fetch from Taostats: {e}")
        conn.close()
        return 1
    
    # Process all subnets
    subnets = sorted(all_subnets.keys())
    today = date.today().isoformat()
    yesterday = date.fromordinal(date.today().toordinal() - 1).isoformat()
    
    print(f"Processing {len(subnets)} subnets...")
    print()
    
    results = {}
    total_alpha_holdings = 0.0
    total_daily_alpha_earned = 0.0
    
    for netuid in subnets:
        # Current alpha balance from Taostats
        current_alpha = all_subnets[netuid]
        
        # Get previous snapshot from database
        previous_alpha = get_previous_snapshot(conn, address, netuid, yesterday)
        if previous_alpha is None:
            previous_alpha = current_alpha  # First run - use current as baseline
        
        # Calculate daily earnings (delta)
        daily_alpha_earned = max(0, current_alpha - previous_alpha)
        
        # Store today's snapshot
        store_snapshot(conn, address, netuid, current_alpha, today)
        
        # Estimate TAO values (for display only)
        current_tao_estimate = estimate_tao_value(netuid, current_alpha, address)
        daily_tao_estimate = estimate_tao_value(netuid, daily_alpha_earned, address) if daily_alpha_earned > 0 else 0
        
        results[netuid] = {
            'current_alpha': current_alpha,
            'previous_alpha': previous_alpha,
            'daily_alpha': daily_alpha_earned,
            'current_tao_est': current_tao_estimate,
            'daily_tao_est': daily_tao_estimate
        }
        
        total_alpha_holdings += current_alpha
        total_daily_alpha_earned += daily_alpha_earned
        
        # Print subnet summary
        if current_alpha > 0:
            print(f"SN{netuid:3d}: {current_alpha:12.8f} alpha  (~{current_tao_estimate:10.6f} TAO)  |  Daily: +{daily_alpha_earned:10.8f} alpha")
    
    conn.commit()
    
    # Calculate totals
    total_tao_holdings_est = sum(r['current_tao_est'] for r in results.values())
    total_daily_tao_est = sum(r['daily_tao_est'] for r in results.values())
    
    # Print summary
    print()
    print("=" * 70)
    print(f"TOTAL HOLDINGS:  {total_alpha_holdings:12.8f} alpha  (~{total_tao_holdings_est:10.6f} TAO)")
    print(f"DAILY EARNINGS:  {total_daily_alpha_earned:12.8f} alpha  (~{total_daily_tao_est:10.6f} TAO)")
    print("=" * 70)
    print()
    
    # Write CSV report
    report_file = app_config.config.REPORTS_DIR / f'daily_emissions_{today}.csv'
    
    with open(report_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Subnet',
            'Daily Alpha Earned',
            'Daily TAO Estimate',
            'Previous Alpha',
            'Current Alpha',
            'Current TAO Estimate'
        ])
        
        for netuid in sorted(results.keys()):
            data = results[netuid]
            writer.writerow([
                f'SN{netuid}',
                f'{data["daily_alpha"]:.8f}',
                f'{data["daily_tao_est"]:.8f}',
                f'{data["previous_alpha"]:.8f}',
                f'{data["current_alpha"]:.8f}',
                f'{data["current_tao_est"]:.8f}'
            ])
        
        # Summary row
        writer.writerow([
            'TOTAL',
            f'{total_daily_alpha_earned:.8f}',
            f'{total_daily_tao_est:.8f}',
            '',
            f'{total_alpha_holdings:.8f}',
            f'{total_tao_holdings_est:.8f}'
        ])
    
    print(f"[OK] Report saved: {report_file}")
    print(f"[OK] Snapshots saved: {app_config.config.DATABASE_PATH}")
    print()
    
    conn.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
