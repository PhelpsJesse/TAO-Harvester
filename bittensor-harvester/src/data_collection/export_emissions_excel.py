"""
Export alpha balance history to Excel with:
- One tab per subnet
- Transaction history included
- Daily emissions calculated (accounting for buys/sells)
"""

import os
import sys
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.database import Database

load_dotenv()

API_KEY = os.getenv("TAOSTATS_API_KEY")
WALLET = os.getenv("COLDKEY_SS58", "5EWvVeoscCk6atHj5ZncAqx7u7QtfvHvCifgKyysPsYbMfmh")

headers = {
    "accept": "application/json",
    "Authorization": API_KEY
}

print("Creating comprehensive Excel export with emissions calculations...\n")

# Step 1: Get all data from database
db = Database()
db.connect()

df = pd.read_sql_query(
    """
    SELECT date, subnet, hotkey, alpha_balance, tao_equivalent, block_number
    FROM alpha_balance_history
    ORDER BY subnet, date
    """,
    db.conn
)

print(f"Loaded {len(df)} records from database")

# Get unique subnets
subnets = sorted(df['subnet'].unique())
print(f"Found {len(subnets)} subnets\n")

# Step 2: Get alpha swap transactions from database
print("Loading alpha swap transactions from database...")
tx_df = pd.read_sql_query(
    """
    SELECT date, subnet, transaction_type, alpha_amount, tao_amount, block_number
    FROM alpha_transactions
    ORDER BY block_number
    """,
    db.conn
)

print(f"Loaded {len(tx_df)} transaction records")

# Process transactions into transfer_data structure
transfer_data = {}
for _, row in tx_df.iterrows():
    key = (row['date'], row['subnet'])
    if key not in transfer_data:
        transfer_data[key] = {'buys': 0, 'sells': 0, 'block': row['block_number']}
    
    if row['transaction_type'] == 'buy':
        transfer_data[key]['buys'] += row['alpha_amount']
    elif row['transaction_type'] == 'sell':
        transfer_data[key]['sells'] += row['alpha_amount']
    
    print(f"  {row['date']} SN{row['subnet']}: {row['transaction_type'].upper()} {row['alpha_amount']:.2f} alpha ({row['tao_amount']:.2f} TAO)")

print()

# Step 3: Create Excel file with one tab per subnet
excel_path = "alpha_emissions_by_subnet.xlsx"
with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
    
    # Summary tab
    summary_data = []
    
    for subnet in subnets:
        subnet_df = df[df['subnet'] == subnet].copy()
        subnet_df = subnet_df.sort_values('date')
        
        # Initialize transaction columns
        subnet_df['buys'] = 0.0
        subnet_df['sells'] = 0.0
        
        # Populate from transfer_data if available
        for idx, row in subnet_df.iterrows():
            key = (row['date'], subnet)
            if key in transfer_data:
                subnet_df.at[idx, 'buys'] = transfer_data[key].get('buys', 0)
                subnet_df.at[idx, 'sells'] = transfer_data[key].get('sells', 0)
        
        # Calculate daily emissions
        # Formula: current_balance - previous_balance - buys + sells
        subnet_df['prev_balance'] = subnet_df['alpha_balance'].shift(1)
        subnet_df['raw_change'] = subnet_df['alpha_balance'] - subnet_df['prev_balance']
        subnet_df['daily_emissions'] = subnet_df['raw_change'] - subnet_df['buys'] + subnet_df['sells']
        
        # First day has no previous balance, so no emissions calculation
        subnet_df.loc[subnet_df.index[0], 'daily_emissions'] = 0
        
        # Calculate cumulative emissions
        subnet_df['cumulative_emissions'] = subnet_df['daily_emissions'].cumsum()
        
        # Reorder columns for clarity
        output_df = subnet_df[[
            'date',
            'alpha_balance',
            'prev_balance',
            'raw_change',
            'buys',
            'sells',
            'daily_emissions',
            'cumulative_emissions',
            'tao_equivalent',
            'block_number'
        ]].copy()
        
        # Write to Excel tab
        sheet_name = f"Subnet {subnet}"
        output_df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Add to summary
        total_emissions = subnet_df['daily_emissions'].sum()
        avg_daily = subnet_df['daily_emissions'].mean()
        current_balance = subnet_df['alpha_balance'].iloc[-1] if len(subnet_df) > 0 else 0
        total_buys = subnet_df['buys'].sum()
        total_sells = subnet_df['sells'].sum()
        
        summary_data.append({
            'Subnet': subnet,
            'Current Balance': current_balance,
            'Total Emissions (30d)': total_emissions,
            'Avg Daily Emissions': avg_daily,
            'Total Buys': total_buys,
            'Total Sells': total_sells,
            'Net Trading': total_buys - total_sells
        })
        
        print(f"Subnet {subnet:3d}: {total_emissions:10.2f} alpha emissions (avg {avg_daily:.2f}/day)")
    
    # Write summary tab
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    # Add instructions tab
    instructions = pd.DataFrame({
        'Instructions': [
            'HOW TO USE THIS FILE',
            '',
            '1. Each subnet has its own tab showing daily alpha balance history',
            '',
            '2. KEY COLUMNS:',
            '   - date: Daily snapshot date',
            '   - alpha_balance: Current holdings on that day',
            '   - prev_balance: Previous day balance',
            '   - raw_change: Total change (includes emissions + buys - sells)',
            '   - buys: Manual alpha purchases (ADD THESE MANUALLY)',
            '   - sells: Manual alpha sales (ADD THESE MANUALLY)',
            '   - daily_emissions: ACTUAL EMISSIONS = raw_change - buys + sells',
            '   - cumulative_emissions: Running total of emissions',
            '',
            '3. TO ADD TRANSACTIONS:',
            '   - Find the date row in the subnet tab',
            '   - Enter the alpha amount in the "buys" or "sells" column',
            '   - The daily_emissions will auto-calculate',
            '   - Example: If you bought 100 alpha on Jan 15 in SN1:',
            '     Go to "Subnet 1" tab, find 2026-01-15, enter 100 in "buys"',
            '',
            '4. EMISSIONS FORMULA:',
            '   daily_emissions = current_balance - previous_balance - buys + sells',
            '',
            '5. Currently all buys/sells are 0 (no transactions detected)',
            '   This means daily_emissions = raw_change',
            '   Add your manual transactions to get accurate emissions'
        ]
    })
    instructions.to_excel(writer, sheet_name='README', index=False)
    
    print(f"\n✓ Created {excel_path} with {len(subnets) + 1} tabs")

print(f"\nTotal emissions across all subnets: {summary_df['Total Emissions (30d)'].sum():.2f} alpha")
print(f"Average daily emissions: {summary_df['Avg Daily Emissions'].sum():.2f} alpha/day")
