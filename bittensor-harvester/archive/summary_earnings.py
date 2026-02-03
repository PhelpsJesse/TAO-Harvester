#!/usr/bin/env python3
"""
Generate simplified earnings summary showing all subnets with their daily earnings and TAO conversion.
Pulls data from existing earnings_report.py output and enriches with holdings data.
"""

import os
import csv
import json
from datetime import datetime
from collections import defaultdict

# First, let's just read and summarize what we have
def main():
    # Read the existing report
    report_file = 'reports/earnings_report_2026-02-01.csv'
    
    if not os.path.exists(report_file):
        print(f"Report file not found: {report_file}")
        return
    
    # Parse the CSV
    earnings_by_subnet = {}
    total_tao = 0.0
    
    with open(report_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['date'] == 'TOTAL':
                total_tao = float(row.get('harvestable_tao', 0))
                continue
            
            netuid = int(row['netuid'])
            daily_earnings = float(row['daily_earnings'])
            harvestable_tao = float(row.get('harvestable_tao', 0))
            
            earnings_by_subnet[netuid] = {
                'daily_earnings': daily_earnings,
                'harvestable_tao': harvestable_tao
            }
    
    # Load known holdings from config
    config_data = {}
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            config_data = json.load(f)
    
    # For now, create a simple summary of what we have
    print("\n" + "="*70)
    print("EARNINGS SUMMARY (Last 24 Hours)")
    print("="*70)
    print(f"\nDate: 2026-02-01")
    print(f"Subnets with earnings: {len(earnings_by_subnet)}")
    print(f"\nSubnet  | Daily Earnings | Harvestable TAO")
    print("-" * 50)
    
    for netuid in sorted(earnings_by_subnet.keys()):
        data = earnings_by_subnet[netuid]
        print(f"SN{netuid:3d}   | {data['daily_earnings']:13.8f} α | {data['harvestable_tao']:13.8f} TAO")
    
    print("-" * 50)
    print(f"TOTAL   | {sum(d['daily_earnings'] for d in earnings_by_subnet.values()):13.8f} α | {total_tao:13.8f} TAO")
    print("="*70 + "\n")
    
    # Create simplified CSV output with all 25 subnets
    # For now, just the ones we have with earnings
    output_file = 'reports/earnings_summary_2026-02-01.csv'
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Subnet', 'Daily Earnings (Alpha)', 'Harvestable TAO'])
        
        for netuid in sorted(earnings_by_subnet.keys()):
            data = earnings_by_subnet[netuid]
            writer.writerow([
                f'SN{netuid}',
                f'{data["daily_earnings"]:.8f}',
                f'{data["harvestable_tao"]:.8f}'
            ])
        
        # Total row
        total_earnings = sum(d['daily_earnings'] for d in earnings_by_subnet.values())
        writer.writerow([
            'TOTAL',
            f'{total_earnings:.8f}',
            f'{total_tao:.8f}'
        ])
    
    print(f"✓ Summary report written to: {output_file}")

if __name__ == '__main__':
    main()
