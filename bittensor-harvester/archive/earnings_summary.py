#!/usr/bin/env python3
"""
Generate a simplified earnings summary report showing all 25 subnets 
with their daily earnings and TAO value sum.
"""

import os
import sys
from datetime import datetime, timedelta
import csv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from wallet_manager import WalletManager
from taostats import TaostatsClient
from config import get_config

def get_daily_earnings_per_subnet(client, address, hours=24):
    """
    Get daily earnings per subnet for the last N hours.
    Returns dict of {netuid: daily_earnings_alpha}
    """
    earnings = {}
    
    # Get all subnet holdings
    all_balances = client.get_all_subnet_balances_api(address)
    
    # Initialize earnings for all subnets
    for netuid in all_balances.keys():
        earnings[netuid] = 0.0
    
    # Get earnings history for the last 24 hours
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    history = client.get_history_data_api(address)
    
    config = get_config()
    min_transaction = config.min_transaction_alpha if hasattr(config, 'min_transaction_alpha') else 5
    emission_sources = config.emission_sources if hasattr(config, 'emission_sources') else {}
    
    for entry in history:
        try:
            entry_time = datetime.fromisoformat(entry.get('created_date', '').replace('Z', '+00:00'))
            
            # Only count last 24 hours
            if entry_time < start_time or entry_time > end_time:
                continue
            
            netuid = entry.get('netuid')
            amount_alpha = float(entry.get('amount_alpha', 0))
            source = entry.get('source', '')
            
            if netuid is None or amount_alpha <= 0:
                continue
            
            # Skip very large transfers (likely manual trades)
            if amount_alpha > min_transaction:
                continue
            
            # Only count emissions/dividends
            if source not in emission_sources.values():
                continue
            
            if netuid not in earnings:
                earnings[netuid] = 0.0
            
            earnings[netuid] += amount_alpha
        except (ValueError, KeyError, TypeError):
            continue
    
    return earnings, all_balances

def main():
    config = get_config()
    address = config.primary_address if hasattr(config, 'primary_address') else None
    
    # Initialize clients
    api_key = os.getenv("TAOSTATS_API_KEY", "")
    client = TaostatsClient(api_key=api_key)
    
    # Get earnings and balances
    earnings, all_balances = get_daily_earnings_per_subnet(client, address)
    
    # Get TAO conversion rate
    tao_conversion = client.get_tao_conversion_rate()
    
    # Prepare output
    output_dir = os.path.join(os.path.dirname(__file__), 'reports')
    os.makedirs(output_dir, exist_ok=True)
    
    today = datetime.now().strftime('%Y-%m-%d')
    output_file = os.path.join(output_dir, f'earnings_summary_{today}.csv')
    
    # Write CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subnet', 'Daily Earnings (Alpha)', 'Current Balance (TAO)', 'Earnings in TAO'])
        
        total_earnings_alpha = 0
        total_earnings_tao = 0
        
        # Sort by subnet number
        for netuid in sorted(all_balances.keys()):
            earnings_alpha = earnings.get(netuid, 0)
            balance_tao = all_balances[netuid]
            earnings_tao = earnings_alpha * tao_conversion
            
            total_earnings_alpha += earnings_alpha
            total_earnings_tao += earnings_tao
            
            writer.writerow([
                f'SN{netuid}',
                f'{earnings_alpha:.8f}',
                f'{balance_tao:.8f}',
                f'{earnings_tao:.8f}'
            ])
        
        # Write sum row
        total_earnings_tao_from_balance = total_earnings_alpha * tao_conversion
        writer.writerow(['TOTAL', f'{total_earnings_alpha:.8f}', '', f'{total_earnings_tao_from_balance:.8f}'])
    
    print(f"✓ Report generated: {output_file}")
    print(f"  Subnets: {len(all_balances)}")
    print(f"  Total Daily Earnings: {total_earnings_alpha:.8f} alpha ({total_earnings_tao_from_balance:.8f} TAO)")
    print(f"  Conversion Rate: 1 alpha = {tao_conversion:.8f} TAO")

if __name__ == '__main__':
    main()
