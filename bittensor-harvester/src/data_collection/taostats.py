"""
Taostats API client for retrieving earnings statistics.

IMPORTANT: Secondary data source only. Primary source is Bittensor RPC for on-chain truth.
Taostats provides historical/indexed data for reference but should not be trusted
for real-time alpha balance calculations.

API Information (verified):
- Base URL: https://api.taostats.io
- Authentication: Header-based, "Authorization: <api_key>" (no "Bearer" prefix)
- Rate limit: 5 requests/minute (CRITICAL - requires request throttling)
- Verified endpoints:
  - /api/dtao/hotkey_emission/v1 - hotkey emission data for dTAO
  - /api/validator/latest/v1 - latest validator info
  - /api/delegation/v1 - delegation/stake data
  - /api/dtao/subnet_emission/v1 - subnet-level emission data
- Non-working endpoints (may require different parameters):
  - /api/accounting/v1 - returns 400 (parameter format issue)
  - /api/account/history/v1 - returns 400 (parameter format issue)

Issue: Taostats may not index multi-validator setups reliably.
Users validating on multiple subnets may see incomplete data.

Usage: Use as fallback if RPC is unavailable, never as primary source of truth.
"""

import logging
import requests
import time
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class TaostatsClient:

    def get_all_subnet_balances_api(self, address: str, network: str = "finney") -> Dict[int, float]:
        """
        Fetch all subnet alpha balances for a wallet using the paginated Taostats API.
        Returns: {netuid: alpha_balance (float), ...}
        """
        balances = self.get_subnet_balances_with_tao(address, network)
        return balances.get("subnet_alpha", {})

    def get_subnet_balances_with_tao(self, address: str, network: str = "finney") -> Dict[str, Dict[int, float]]:
        """
        Fetch all subnet balances for a wallet using the paginated Taostats API.

        Returns:
            {
                "subnet_alpha": {netuid: alpha_balance (float), ...},
                "subnet_tao": {netuid: tao_equivalent (float), ...}
            }
        """
        def normalize_amount(value):
            if value is None:
                return None
            try:
                amount = float(value)
            except Exception:
                return None
            return amount / 1e9 if amount > 1e6 else amount

        endpoint = f"{self.BASE_URL}/api/account/latest/v1"
        page = 1
        limit = 50
        subnet_alpha: Dict[int, float] = {}
        subnet_tao: Dict[int, float] = {}

        while True:
            params = {"address": address, "network": network, "page": page, "limit": limit}
            if self.REQUEST_DELAY_SECONDS:
                time.sleep(self.REQUEST_DELAY_SECONDS)
            resp = self.session.get(endpoint, params=params, timeout=10)
            if resp.status_code == 429:
                time.sleep(self.REQUEST_DELAY_SECONDS)
                resp = self.session.get(endpoint, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break

            for item in items:
                alpha_balances = item.get("alpha_balances", [])
                if isinstance(alpha_balances, list) and alpha_balances:
                    for entry in alpha_balances:
                        try:
                            netuid = int(entry.get("netuid"))
                        except Exception:
                            continue

                        alpha_value = normalize_amount(entry.get("balance") or entry.get("balance_rao"))
                        tao_value = normalize_amount(entry.get("balance_as_tao") or entry.get("balance_alpha_as_tao"))

                        if alpha_value is not None and alpha_value > 0:
                            subnet_alpha[netuid] = subnet_alpha.get(netuid, 0.0) + alpha_value
                        if tao_value is not None and tao_value > 0:
                            subnet_tao[netuid] = subnet_tao.get(netuid, 0.0) + tao_value
                else:
                    netuid = item.get("subnet_uid")
                    try:
                        netuid = int(netuid)
                    except Exception:
                        continue

                    alpha_value = normalize_amount(item.get("balance_staked_alpha") or item.get("balance"))
                    tao_value = normalize_amount(item.get("balance_staked_alpha_as_tao") or item.get("balance_as_tao"))

                    if alpha_value is not None and alpha_value > 0:
                        subnet_alpha[netuid] = subnet_alpha.get(netuid, 0.0) + alpha_value
                    if tao_value is not None and tao_value > 0:
                        subnet_tao[netuid] = subnet_tao.get(netuid, 0.0) + tao_value

            pagination = data.get("pagination", {})
            if pagination.get("next_page") and pagination.get("next_page") != page:
                page = pagination["next_page"]
            else:
                break

        return {"subnet_alpha": subnet_alpha, "subnet_tao": subnet_tao}
    """
    Client for Taostats API queries (secondary source).
    
    Note: Use only as fallback when RPC is unavailable.
    Real-time alpha calculations should come from RPC.
    """

    BASE_URL = "https://api.taostats.io"
    # Rate limit: 5 requests per minute. Implement throttling in calling code.
    REQUEST_DELAY_SECONDS = 12  # (60 seconds / 5 requests = 12 seconds per request)

    def __init__(self, api_key: str = ""):
        """
        Initialize Taostats client.

        Args:
            api_key: Taostats API key (from https://taostats.io)
                     Format: "tao-<uuid>:<hex_string>"
                     No "Bearer" prefix needed.
        """
        # Safety check: Verify Taostats is enabled in config
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            import config as app_config
            if not app_config.config.TAOSTATS_ENABLED:
                logger.warning("⚠️  Taostats API is DISABLED in config. Set TAOSTATS_ENABLED=true to use.")
                api_key = ""  # Disable API usage
        except Exception as e:
            logger.debug(f"Could not check config: {e}")
        
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            # Authorization header format: just the API key, no "Bearer" prefix
            self.session.headers.update({"Authorization": api_key})

    def get_delegators(self, validator_address: str, netuid: int) -> List[Dict]:
        """
        Get list of delegators for a validator.

        Args:
            validator_address: Validator SS58 address (hotkey)
            netuid: Subnet ID

        Returns:
            List of delegator records with amounts
        """
        try:
            endpoint = f"{self.BASE_URL}/api/delegation/v1"
            params = {"validator_hotkey": validator_address, "subnet_uid": netuid}
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except requests.RequestException as e:
            logger.error(f"Failed to fetch delegators: {e}")
            return []

    def get_accounting_by_date(self, address: str, netuid: int) -> Dict:
        """
        Get accounting/earnings data by date for a validator.
        
        This endpoint provides daily emission and income breakdown,
        perfect for calculating last 24h earnings.

        Args:
            address: Validator SS58 address (hotkey)
            netuid: Subnet ID

        Returns:
            {
                'address': str,
                'netuid': int,
                'daily_data': [{'date': str, 'emission': float, ...}, ...],
                'last_24h_emission': float (in TAO),
                'timestamp': str,
                'raw_data': dict (full response)
            }
        """
        try:
            endpoint = f"{self.BASE_URL}/api/accounting/v1"
            params = {
                "validator_hotkey": address,
                "subnet_uid": netuid,
                "limit": 10,  # Get last 10 days
            }
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract daily data
            daily_data = data.get('data', [])
            
            # Calculate last 24h emissions (most recent entry)
            last_24h = 0.0
            if daily_data:
                # First entry should be most recent (today)
                latest = daily_data[0]
                # Divide by 1e9 to convert from rao to TAO
                last_24h = latest.get('emission', 0) / 1e9 if latest.get('emission') else 0
            
            return {
                "address": address,
                "netuid": netuid,
                "daily_data": daily_data,
                "last_24h_emission": last_24h,
                "timestamp": datetime.utcnow().isoformat(),
                "raw_data": data
            }
        except requests.RequestException as e:
            logger.error(f"Failed to fetch accounting data: {e}")
            return {
                "address": address,
                "netuid": netuid,
                "error": str(e),
                "daily_data": [],
                "last_24h_emission": 0.0,
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_account_balance(self, address: str) -> Dict:
        """
        Get account balance history for a validator.

        Args:
            address: Validator SS58 address (hotkey)

        Returns:
            {
                'address': str,
                'current_balance': float (in TAO),
                'balance_history': [{'date': str, 'balance': float}, ...],
                'timestamp': str,
                'raw_data': dict (full response)
            }
        """
        try:
            endpoint = f"{self.BASE_URL}/api/account/history/v1"
            params = {
                "validator_hotkey": address,
                "limit": 10,  # Get last 10 entries
            }
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract balance history
            balance_history = data.get('data', [])
            
            # Get current balance (most recent entry)
            current_balance = 0.0
            if balance_history:
                latest = balance_history[0]
                # Divide by 1e9 to convert from rao to TAO
                current_balance = latest.get('balance', 0) / 1e9 if latest.get('balance') else 0
            
            return {
                "address": address,
                "current_balance": current_balance,
                "balance_history": balance_history,
                "timestamp": datetime.utcnow().isoformat(),
                "raw_data": data
            }
        except requests.RequestException as e:
            logger.error(f"Failed to fetch account balance: {e}")
            return {
                "address": address,
                "error": str(e),
                "current_balance": 0.0,
                "balance_history": [],
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_alpha_earnings_history(self, address: str, days: int = 1) -> Dict:
        """
        Get daily alpha earnings from transfer history.
        
        Queries the transfers API to find all inbound transfers (earnings/dividends)
        to the address over the specified number of days.

        Args:
            address: Validator SS58 address (hotkey)
            days: Number of days of history to fetch (default 1 = last 24 hours)

        Returns:
            {
                'address': str,
                'total_earnings': float (total TAO earned),
                'daily_earnings': {
                    'YYYY-MM-DD': {
                        'total': float (daily total),
                        'transfers': [
                            {
                                'amount': float (in TAO),
                                'timestamp': str (ISO 8601),
                                'block': int,
                                'from': str (SS58 address - source of emission)
                            },
                            ...
                        ]
                    },
                    ...
                },
                'timestamp': str,
                'raw_data': dict (full response)
            }
        """
        try:
            # Get transfer history (limit 100 should get ~30 days)
            limit = min(days * 5, 100)  # Rough estimate: ~5 transfers per day
            endpoint = f"{self.BASE_URL}/api/transfer/v1?address={address}&limit={limit}"
            
            response = self.session.get(endpoint, params={}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            transfers = data.get('data', [])
            
            # Filter to only inbound transfers (earnings TO the address)
            daily_earnings = {}
            total_earnings = 0.0
            
            for transfer in transfers:
                to_addr = transfer.get('to', {})
                from_addr = transfer.get('from', {})
                
                # Handle both dict and string formats
                to_ss58 = to_addr.get('ss58', '') if isinstance(to_addr, dict) else to_addr
                
                # Only count transfers TO the address
                if to_ss58 == address:
                    amount_rao = int(transfer.get('amount', '0'))
                    amount_tao = amount_rao / 1e9
                    timestamp = transfer.get('timestamp', '')
                    block = transfer.get('block_number', '')
                    from_ss58 = from_addr.get('ss58', 'unknown') if isinstance(from_addr, dict) else from_addr
                    
                    # Parse date from timestamp
                    day = 'unknown'
                    if timestamp:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            day = dt.strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    # Accumulate by day
                    if day not in daily_earnings:
                        daily_earnings[day] = {
                            'total': 0.0,
                            'transfers': []
                        }
                    
                    daily_earnings[day]['total'] += amount_tao
                    daily_earnings[day]['transfers'].append({
                        'amount': amount_tao,
                        'timestamp': timestamp,
                        'block': block,
                        'from': from_ss58
                    })
                    
                    total_earnings += amount_tao
            
            return {
                "address": address,
                "total_earnings": total_earnings,
                "daily_earnings": daily_earnings,
                "timestamp": datetime.utcnow().isoformat(),
                "raw_data": data
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch earnings history from Taostats: {e}")
            return {
                "address": address,
                "error": str(e),
                "total_earnings": 0.0,
                "daily_earnings": {},
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_alpha_balance_by_subnet(self, address: str) -> Dict[int, float]:
        """
        Get alpha balance breakdown by subnet using Taostats API.

        Args:
            address: Validator SS58 address (hotkey)

        Returns:
            {
                'address': str,
                'total_alpha': float (total across all subnets, alpha units),
                'subnet_balances': {
                    netuid: alpha_balance (float),
                    ...
                },
                'subnet_tao': {
                    netuid: tao_equivalent (float),
                    ...
                },
                'alpha_inferred_from_tao': [netuid, ...],
                'timestamp': str,
                'source': 'taostats_api',
                'error': str (if any)
            }
        """
        try:
            balances = self.get_subnet_balances_with_tao(address)
            subnet_alpha = balances.get("subnet_alpha", {})
            subnet_tao = balances.get("subnet_tao", {})
            
            if not subnet_alpha and not subnet_tao:
                return {
                    "address": address,
                    "error": "API returned no subnet balances (may be rate-limited or address has no holdings)",
                    "total_alpha": 0.0,
                    "subnet_balances": {},
                    "subnet_tao": {},
                    "alpha_inferred_from_tao": [],
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "taostats_api"
                }
            
            alpha_inferred_from_tao = []
            combined_alpha = dict(subnet_alpha)
            for netuid, tao_value in subnet_tao.items():
                if netuid not in combined_alpha:
                    combined_alpha[netuid] = tao_value
                    alpha_inferred_from_tao.append(netuid)

            if alpha_inferred_from_tao:
                logger.warning(
                    f"Alpha balances missing for {len(alpha_inferred_from_tao)} subnets; using TAO-equivalent as alpha for those entries"
                )

            if len(combined_alpha) < 20:
                logger.warning(
                    f"API returned only {len(combined_alpha)} subnets for {address} (may be rate-limited or incomplete)"
                )
            
            return {
                "address": address,
                "total_alpha": sum(combined_alpha.values()),
                "subnet_balances": combined_alpha,
                "subnet_tao": subnet_tao,
                "alpha_inferred_from_tao": alpha_inferred_from_tao,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "taostats_api"
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch subnet balances from API: {e}")
            return {
                "address": address,
                "error": str(e),
                "total_alpha": 0.0,
                "subnet_balances": {},
                "subnet_tao": {},
                "alpha_inferred_from_tao": [],
                "timestamp": datetime.utcnow().isoformat(),
                "source": "error"
            }

    def get_seven_day_emissions(self, address: str, max_netuid: int = 300) -> Dict:
        """
        Get 7-day rolling window emissions for all subnets using Taostats API.
        
        Uses daily accounting data from Taostats (no rate limiting).
        Queries all subnets and aggregates daily emissions.
        
        Args:
            address: Validator SS58 address (hotkey)
            max_netuid: Maximum subnet ID to query (0 to max_netuid, inclusive)
        
        Returns:
            {
                'address': str,
                'subnets_queried': int,
                'subnets_with_emissions': int,
                'total_7day_emissions': float (in TAO),
                'daily_breakdown': {
                    'subnet_1': [daily_emission_1, daily_emission_2, ...],
                    'subnet_2': [...],
                },
                'rate_analysis': {
                    'per_hour': float,
                    'per_day': float,
                    'per_week': float,
                },
                'timestamp': str,
                'error': str (if any)
            }
        """
        try:
            # Dictionary to store daily emissions by subnet
            daily_by_subnet = {}
            total_7day = 0.0
            subnets_queried = 0
            subnets_with_emissions = 0
            
            print(f"Querying 7-day emissions from Taostats for {max_netuid+1} subnets...")
            
            # Query each subnet for daily accounting data
            for netuid in range(max_netuid + 1):
                subnets_queried += 1
                
                # Show progress every 50 subnets
                if subnets_queried % 50 == 0:
                    print(f"  Progress: {subnets_queried}/{max_netuid + 1} subnets...")
                
                # Respect rate limiting (Taostats: 5 req/minute = ~200ms per request)
                time.sleep(0.25)  # 250ms between requests for safety margin
                
                try:
                    result = self.get_accounting_by_date(address, netuid)
                    
                    # Skip if error or no data
                    if "error" in result or not result.get("daily_data"):
                        continue
                    
                    # Extract daily emissions for this subnet
                    daily_emissions = []
                    subnet_total = 0.0
                    
                    for daily_entry in result.get("daily_data", []):
                        emission = daily_entry.get("emission", 0)
                        # Convert from rao to TAO (1 TAO = 1e9 rao)
                        emission_tao = emission / 1e9 if emission else 0.0
                        daily_emissions.append(emission_tao)
                        subnet_total += emission_tao
                    
                    # Store if this subnet has any emissions
                    if subnet_total > 0 and daily_emissions:
                        daily_by_subnet[netuid] = daily_emissions
                        total_7day += subnet_total
                        subnets_with_emissions += 1
                        print(f"    Subnet {netuid}: {subnet_total:.6f} TAO over {len(daily_emissions)} days")
                
                except Exception as e:
                    # Skip individual subnet errors
                    logger.debug(f"Subnet {netuid} query failed: {e}")
                    continue
            
            # Calculate emission rates
            # Average the daily data to get rates
            if daily_by_subnet:
                # Find the minimum number of days we have data for
                min_days = min(len(daily) for daily in daily_by_subnet.values())
                
                # Calculate average daily emission
                avg_daily = total_7day / max(min_days, 1) if min_days > 0 else 0
                avg_hourly = avg_daily / 24.0
                avg_weekly = avg_daily * 7.0
            else:
                avg_daily = avg_hourly = avg_weekly = 0.0
            
            return {
                "address": address,
                "subnets_queried": subnets_queried,
                "subnets_with_emissions": subnets_with_emissions,
                "total_7day_emissions": total_7day,
                "daily_breakdown": daily_by_subnet,
                "rate_analysis": {
                    "per_hour": avg_hourly,
                    "per_day": avg_daily,
                    "per_week": avg_weekly,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Failed to get 7-day emissions: {e}")
            return {
                "address": address,
                "error": str(e),
                "subnets_queried": 0,
                "subnets_with_emissions": 0,
                "total_7day_emissions": 0.0,
                "daily_breakdown": {},
                "rate_analysis": {"per_hour": 0.0, "per_day": 0.0, "per_week": 0.0},
                "timestamp": datetime.utcnow().isoformat(),
            }

    def check_api_key_valid(self) -> bool:
        """
        Check if API key is valid by testing a simple endpoint.

        Returns:
            True if API key is valid, False otherwise
        """
        if not self.api_key:
            logger.warning("No API key configured")
            return False

        try:
            # Try a simple endpoint to verify auth
            endpoint = f"{self.BASE_URL}/api/validator/latest/v1"
            params = {"subnet_uid": 1, "limit": 1}
            response = self.session.get(endpoint, params=params, timeout=5)
            # Success if we get any response (not 401/403 auth errors)
            return response.status_code != 401 and response.status_code != 403
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False
