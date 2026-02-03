"""
Dynamic wallet and holdings management.

Queries current wallet holdings from Taostats instead of using static config.
Allows users to add/remove subnets over time without code changes.
"""

import os
from typing import Dict, List, Tuple


class WalletManager:
    """Manages wallet holdings dynamically from Taostats."""
    
    def __init__(self, taostats_client, wallet_address: str):
        """
        Initialize wallet manager.
        
        Args:
            taostats_client: TaostatsClient instance for API queries
            wallet_address: SS58 hotkey address
        """
        self.taostats = taostats_client
        self.wallet_address = wallet_address
        self._cached_holdings = None
        self._cache_timestamp = None
    
    def get_current_holdings(self, force_refresh=False) -> Dict[int, float]:
        """
        Get current alpha holdings by subnet.
        
        Queries Taostats API to get real-time holdings.
        Results are cached for 5 minutes to avoid excessive API calls.
        
        Args:
            force_refresh: Force cache refresh
            
        Returns:
            Dict mapping subnet_uid -> alpha_balance
            Example: {29: 20.5, 34: 15.3, 44: 8.7, ...}
        """
        import time
        
        # Use cache if recent and not forcing refresh
        if self._cached_holdings and not force_refresh:
            if time.time() - self._cache_timestamp < 300:  # 5 min cache
                return self._cached_holdings
        
        # Query Taostats for wallet holdings
        try:
            response = self.taostats.get_alpha_balance_by_subnet(self.wallet_address)
            
            if isinstance(response, dict) and 'error' not in response:
                holdings = response.get('subnet_alpha', {})
                
                self._cached_holdings = holdings
                self._cache_timestamp = time.time()
                return holdings
            else:
                # Fallback: return empty dict if API fails
                print(f"Warning: Could not fetch holdings from Taostats: {response}")
                return {}
        
        except Exception as e:
            print(f"Warning: Error fetching wallet holdings: {e}")
            return {}
    
    def get_owned_subnets(self, min_balance=0.0) -> List[int]:
        """
        Get list of subnets where user has alpha.
        
        Args:
            min_balance: Minimum balance to include (default 0.0)
            
        Returns:
            List of subnet UIDs [29, 34, 44, ...]
        """
        holdings = self.get_current_holdings()
        return sorted([
            netuid for netuid, balance in holdings.items()
            if balance > min_balance
        ])
    
    def get_subnet_alpha(self, netuid: int) -> float:
        """Get current alpha balance for a specific subnet."""
        holdings = self.get_current_holdings()
        return holdings.get(netuid, 0.0)
    
    def get_total_alpha(self) -> float:
        """Get total alpha across all subnets."""
        holdings = self.get_current_holdings()
        return sum(holdings.values())
    
    def clear_cache(self):
        """Clear the holdings cache."""
        self._cached_holdings = None
        self._cache_timestamp = None
