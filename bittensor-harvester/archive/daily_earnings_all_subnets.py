#!/usr/bin/env python3
"""
Generate daily earnings report for ALL 25 subnets based on actual holdings.

Key differences from earnings_report.py:
1. Uses actual wallet holdings (not hardcoded subnet_list)
2. Distributes all emissions across all owned subnets proportionally
3. Filters by transaction size to identify emissions vs manual trades
4. Shows all 25 subnets even if no emissions (0 earned)
5. Identifies and reports all emission sources found
"""

import os
import csv
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

sys.path.insert(0, 'src')
from config import get_config
from taostats import TaostatsClient

def get_all_holdings(client, address):
    """Get all subnets with positive holdings."""
    holdings = client.get_all_subnet_balances_api(address)
    owned = {netuid: balance for netuid, balance in holdings.items() if balance > 0}
    return owned

def get_all_transactions(client, address, days=2):
    """Fetch all transactions from the last N days."""
    earnings = client.get_alpha_earnings_history(address, days=days)
    all_txs = []
    
    for day, day_data in earnings.get('daily_earnings', {}).items():
        for tx in day_data.get('transfers', []):
            all_txs.append({
                'date': day,
                'amount': float(tx['amount']),
                'timestamp': tx['timestamp'],
                'block': tx['block'],
                'from': tx['from']
            })
    
    return all_txs

def distribute_earnings_by_holdings(amount, owned_subnets):
    """
    Distribute an emission amount across subnets based on holdings.
    
    Args:
        amount: Amount to distribute
        owned_subnets: Dict of {netuid: balance_tao}
    
    Returns:
        Dict of {netuid: share_of_amount}
    """
    if not owned_subnets:
        return {}
    
    total_holdings = sum(owned_subnets.values())
    if total_holdings == 0:
        return {}
    
    distribution = {}
    for netuid, balance in owned_subnets.items():
        share = (balance / total_holdings) * amount
        distribution[netuid] = share
    
    return distribution

def main():
    config = get_config()
    
    # Get validator address
    validator_hotkeys = config.validator_hotkeys if hasattr(config, 'validator_hotkeys') else ""
    validators = [h.strip() for h in validator_hotkeys.split(',') if h.strip()]
    address = validators[0] if validators else None
    
    if not address:
        print("ERROR: No validator hotkey configured. Set VALIDATOR_HOTKEYS in .env")
        return
    
    print(f"Address: {address}\n")
    
    # Initialize client
    api_key = os.getenv('TAOSTATS_API_KEY', '')
    client = TaostatsClient(api_key=api_key)
    
    # Get all holdings
    print("Fetching holdings for all subnets...")
    owned_subnets = get_all_holdings(client, address)
    print(f"  Found {len(owned_subnets)} subnets with positive holdings")
    print(f"  Total holdings: {sum(owned_subnets.values()):.8f} TAO\n")
    
    if not owned_subnets:
        print("ERROR: No holdings found!")
        return
    
    # Get all transactions
    print("Fetching transaction history...")
    transactions = get_all_transactions(client, address, days=2)
    print(f"  Found {len(transactions)} transactions\n")
    
    # Get time window
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    
    # Identify emission sources
    sources_in_24h = set()
    total_by_source_24h = defaultdict(float)
    
    for tx in transactions:
        try:
            tstamp = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00'))
        except:
            continue
        
        if tstamp >= yesterday:
            sources_in_24h.add(tx['from'])
            total_by_source_24h[tx['from']] += tx['amount']
    
    print("="*80)
    print("EMISSION SOURCES FOUND (Last 24 Hours)")
    print("="*80)
    for source in sources_in_24h:
        print(f"{source[:60]:60} | {total_by_source_24h[source]:10.4f} TAO")
    print(f"Total from all sources: {sum(total_by_source_24h.values()):.4f} TAO\n")
    
    # Distribute earnings across all 25 subnets
    daily_earnings = defaultdict(float)
    
    for tx in transactions:
        try:
            tstamp = datetime.fromisoformat(tx['timestamp'].replace('Z', '+00:00'))
        except:
            continue
        
        # Only last 24h
        if tstamp < yesterday:
            continue
        
        # Filter by size: small transactions are emissions, large are manual trades
        # Per config: exclude transactions > 5 TAO (manual trades/compounding)
        if tx['amount'] > 5.0:
            print(f"Skipping large transaction: {tx['amount']:.4f} TAO (likely manual trade)")
            continue
        
        # Distribute this transaction across subnets based on holdings
        distribution = distribute_earnings_by_holdings(tx['amount'], owned_subnets)
        
        for netuid, share in distribution.items():
            daily_earnings[netuid] += share
    
    # Generate report
    print("="*80)
    print("DAILY EARNINGS BY SUBNET (Last 24 Hours)")
    print("="*80)
    
    output_file = f"reports/subnet_earnings_{now.strftime('%Y-%m-%d')}.csv"
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subnet', 'Current Holdings (TAO)', 'Daily Earnings (TAO)'])
        
        total_earnings = 0
        
        # Report all 25 subnets
        for netuid in sorted(owned_subnets.keys()):
            holdings = owned_subnets[netuid]
            earnings = daily_earnings.get(netuid, 0)
            total_earnings += earnings
            
            writer.writerow([
                f'SN{netuid}',
                f'{holdings:.8f}',
                f'{earnings:.8f}'
            ])
            
            print(f"SN{netuid:3d} | Holdings: {holdings:12.8f} TAO | Daily Earnings: {earnings:12.8f} TAO")
        
        # Total row
        writer.writerow([
            'TOTAL',
            f'{sum(owned_subnets.values()):.8f}',
            f'{total_earnings:.8f}'
        ])
    
    print("="*80)
    print(f"Total Daily Earnings: {total_earnings:.8f} TAO")
    print(f"APY if sustained: {(total_earnings * 365 / sum(owned_subnets.values()) * 100):.2f}%")
    print(f"\nReport written to: {output_file}")

if __name__ == '__main__':
    main()
