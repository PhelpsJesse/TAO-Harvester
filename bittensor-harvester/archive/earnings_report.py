"""
Report daily alpha earnings by subnet.

Pulls daily earnings from Taostats transfer history and maps to subnets
based on configurable emission source mapping.

Key features:
- Dynamically checks wallet holdings (not hardcoded)
- Only reports on subnets you currently own
- Uses configurable emissions_config.json for source -> subnet mapping
- Generic: works for any wallet and subnet combination

Output: reports/earnings_report_<YYYYMMDD>.csv

Columns:
- date: Report date (YYYY-MM-DD)
- address: Validator hotkey
- netuid: Subnet ID (or 'unknown' if mapping not found)
- daily_earnings: Alpha earned from this subnet on this date
- harvestable: Amount eligible for harvest (daily_earnings * harvest_fraction)
- block: Approximate block number when earnings were recorded
- source: Source address of the emission
"""

import os
import csv
import json
from datetime import date
from collections import defaultdict
from src.config import HarvesterConfig
from src.database import Database
from src.taostats import TaostatsClient

from src.wallet_manager import WalletManager
from src.alpha_swap import AlphaSwap


def load_emissions_mapping():
    """
    Load configurable emissions source to subnet mapping.
    
    Returns dict: {source_address -> {'subnets': [list of netuid], 'description': str, ...}}
    """
    # Prefer unified config.json, fall back to emissions_config.json
    config_json = 'config.json'
    mapping_file = 'emissions_config.json'

    # Try config.json first
    if os.path.exists(config_json):
        try:
            with open(config_json, 'r') as f:
                data = json.load(f)
                em = data.get('emissions_mapping', {})
                if 'sources' in em:
                    return em['sources']
        except Exception as e:
            print(f"Warning: Could not load config.json: {e}")

    # Fallback to legacy emissions_config.json
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r') as f:
                data = json.load(f)
                if 'emissions_mapping' in data and 'sources' in data['emissions_mapping']:
                    return data['emissions_mapping']['sources']
        except Exception as e:
            print(f"Warning: Could not load emissions_config.json: {e}")

    # Final fallback: empty mapping
    return {}


def get_subnets_for_source(source_addr, mapping, owned_subnets=None):
    """
    Get list of subnets for a given source address.
    
    Args:
        source_addr: Emission source SS58 address
        mapping: Emissions mapping dict
        owned_subnets: List of subnets user actually owns (filter to these)
        
    Returns:
        List of subnet UIDs [29, 34, 44, ...]
    """
    if source_addr in mapping:
        subnets = mapping[source_addr].get('subnets', [])
        
        # Filter to only subnets user owns
        if owned_subnets:
            subnets = [s for s in subnets if s in owned_subnets]
        
        return subnets
    
    return []


def main():
    config = HarvesterConfig.from_env()
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    window_days = getattr(config, 'aggregation_window_days', 1)
    window_start = now - timedelta(days=window_days)
    # Initialize all variables before aggregation
    validators = config.get_validator_list()
    if not validators:
        print("No validators configured. Set VALIDATOR_HOTKEYS or HARVESTER_WALLET_ADDRESS in .env")
        return
    taostats = TaostatsClient(api_key=os.getenv("TAOSTATS_API_KEY", ""))
    wallet_manager = WalletManager(taostats, validators[0])
    print("\nFetching current wallet holdings...")
    # Get all subnets with a positive alpha balance (not just those in emissions mapping)
    holdings = wallet_manager.get_current_holdings(force_refresh=True)
    owned_subnets = sorted([netuid for netuid, balance in holdings.items() if balance > 0])
    total_alpha = wallet_manager.get_total_alpha()
    print(f"  Wallet: {validators[0]}")
    print(f"  Owned subnets: {owned_subnets}")
    print(f"  Total alpha: {total_alpha:.9f} TAO")
    if not owned_subnets:
        print("\nWarning: No alpha holdings found on any subnet. Check wallet or API access.")
        return
    emissions_mapping = load_emissions_mapping()
    # Load thresholds from config
    config_json = 'config.json'
    default_threshold = 0.1
    per_subnet_thresholds = {}
    if os.path.exists(config_json):
        try:
            with open(config_json, 'r') as f:
                data = json.load(f)
            hs = data.get('emissions_mapping', {}).get('harvest_settings', {})
            default_threshold = hs.get('default_threshold', 0.1)
            per_subnet_thresholds = hs.get('per_subnet', {})
        except Exception:
            pass
    # Only process last 24h
    daily_by_subnet = defaultdict(lambda: {
        'total_earnings': 0.0,
        'transfers': [],
        'block': '',
    })
    unknown_sources_found = {}  # {source: total_amount}
    
    # Alpha-to-TAO conversion rate (average, varies by subnet)
    # Default: 1 alpha ≈ 0.01 TAO (5 alpha threshold = 0.05 TAO)
    alpha_to_tao_rate = 0.01
    max_transaction_alpha = 5.0  # Filter out transactions > 5 alpha per transaction (manual trades)
    max_transaction_tao = max_transaction_alpha * alpha_to_tao_rate  # 0.05 TAO
    
    for addr in validators:
        print(f"\nFetching earnings for {addr} (last {window_days} day(s))...")
        try:
            earnings = taostats.get_alpha_earnings_history(addr, days=2)
            if 'error' in earnings:
                print(f"  Error: {earnings['error']}")
                continue
            daily_earnings = earnings.get('daily_earnings', {})
            subnet_earnings_24h = defaultdict(float)
            block_by_subnet = {}
            for day, day_data in daily_earnings.items():
                for t in day_data['transfers']:
                    try:
                        tstamp = datetime.fromisoformat(t['timestamp'].replace('Z', '+00:00'))
                        if tstamp.tzinfo is None:
                            tstamp = tstamp.replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                    if tstamp < window_start:
                        continue
                    # Filter: exclude transactions > 5 alpha (manual trades, not emissions)
                    # API returns amounts in TAO, so convert threshold to TAO
                    if t['amount'] > max_transaction_tao:
                        from_addr = t['from']
                        if from_addr not in unknown_sources_found:
                            unknown_sources_found[from_addr] = 0.0
                        unknown_sources_found[from_addr] += t['amount']
                        continue
                    source_addr = t['from']
                    subnets_for_source = get_subnets_for_source(source_addr, emissions_mapping, owned_subnets)
                    if subnets_for_source:
                        holdings = wallet_manager.get_current_holdings()
                        balances = [float(holdings.get(int(n), 0.0)) for n in subnets_for_source]
                        total_bal = sum(balances)
                        for i, netuid in enumerate(subnets_for_source):
                            share = (balances[i] / total_bal) if total_bal > 0 else (1.0 / len(subnets_for_source))
                            subnet_earnings_24h[netuid] += t['amount'] * share
                            if netuid not in block_by_subnet:
                                block_by_subnet[netuid] = t['block']
                    else:
                        if source_addr not in unknown_sources_found:
                            unknown_sources_found[source_addr] = 0.0
                        unknown_sources_found[source_addr] += t['amount']
            for netuid, total_earned in subnet_earnings_24h.items():
                key = (now.strftime('%Y-%m-%d'), netuid)
                daily_by_subnet[key]['total_earnings'] += total_earned
                if netuid in block_by_subnet:
                    daily_by_subnet[key]['block'] = block_by_subnet[netuid]
        except Exception as e:
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()
        
        except Exception as e:
            print(f"  Exception: {e}")
            import traceback
            traceback.print_exc()
    
    # Generate rows from consolidated data
    rows = []
    for (day, netuid), data in sorted(daily_by_subnet.items(), key=lambda x: (x[0][0], x[0][1] if isinstance(x[0][1], int) else 9999)):
        if netuid == 'unknown':
            continue  # Skip unknown sources for now
        
        daily = data['total_earnings']
        if daily == 0:
            continue
        
        harvestable = daily * config.harvest_fraction
        threshold = float(per_subnet_thresholds.get(str(netuid), default_threshold))
        should = harvestable >= threshold
        
        # Prepare dry-run harvest action (not broadcast)
        try:
            from src.harvester import prepare_harvest_tx
            prepared = prepare_harvest_tx(int(netuid), harvestable, validators[0])
        except Exception:
            prepared = {"error": "prepare_failed"}
        
        row = {
            "date": day,
            "address": validators[0],
            "netuid": netuid,
            "daily_earnings": daily,
            "harvestable_alpha": harvestable,
            "harvest_threshold": threshold,
            "should_harvest": should,
            "prepared_action": prepared,
            "block": data['block'],
        }
        rows.append(row)
        
        print(f"  {day} SN{netuid} earnings={daily:.6f} harvestable={harvestable:.6f} should_harvest={should}")
    
    # Write CSV
    out_path = f"reports/earnings_report_{now.strftime('%Y-%m-%d')}.csv"
    headers = [
        "date", "address", "netuid", "daily_earnings", "harvestable_alpha", "harvestable_tao", "harvest_threshold", "should_harvest", "prepared_action", "block"
    ]
    total_tao = 0.0
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            # Calculate harvestable_tao for each subnet using AlphaSwap
            try:
                swap = AlphaSwap(int(r["netuid"]), r["address"])
                harvestable_tao = swap.estimate_tao_output(r["harvestable_alpha"])
            except Exception:
                harvestable_tao = 0.0
            r["harvestable_tao"] = harvestable_tao
            total_tao += harvestable_tao
            writer.writerow(r)
        # Write a final summary row
        summary_row = {k: "" for k in headers}
        summary_row["date"] = "TOTAL"
        summary_row["harvestable_tao"] = total_tao
        writer.writerow(summary_row)
    print(f"\nReport written: {out_path}")
    print(f"Total rows: {len(rows)} (report includes all owned subnets)")
    
    # Report unknown sources (likely manual trades)
    if unknown_sources_found:
        print(f"\n⚠️  Unknown sources excluded from earnings (likely manual buy/sell trades):")
        for source, amount in sorted(unknown_sources_found.items(), key=lambda x: -x[1]):
            print(f"  {source[:20]}... : {amount:.9f} TAO")
        total_excluded = sum(unknown_sources_found.values())
        print(f"  TOTAL EXCLUDED: {total_excluded:.9f} TAO")
    


if __name__ == "__main__":
    main()
