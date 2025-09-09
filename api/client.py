"""
SpaceTraders API client for making HTTP requests to the SpaceTraders API.
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SpaceTradersAPIClient:
    """
    Client for interacting with the SpaceTraders API.
    
    Handles authentication, rate limiting, and provides methods for all
    API endpoints needed by the agent.
    """
    
    def __init__(self, base_url: str = "https://api.spacetraders.io", agent_token: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize the API client.
        
        Args:
            base_url: Base URL for the SpaceTraders API
            agent_token: Agent authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.agent_token = agent_token
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        
        # Setup session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.5  # 500ms between requests
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make a request to the API with proper error handling and rate limiting.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests
            
        Returns:
            Dict containing the API response data
            
        Raises:
            requests.HTTPError: For HTTP errors
            requests.RequestException: For other request errors
        """
        # Rate limiting
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            time.sleep(sleep_time)
        
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})
        
        if self.agent_token:
            headers["Authorization"] = f"Bearer {self.agent_token}"
        headers.setdefault("Content-Type", "application/json")
        
        self.logger.debug(f"Making {method} request to {url}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                timeout=self.timeout,
                **kwargs
            )
            self.last_request_time = time.time()
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error: {e}")
            raise
    
    # Agent endpoints
    
    def get_my_agent(self) -> Dict[str, Any]:
        """Get the current agent's details."""
        return self._make_request("GET", "/v2/my/agent")
    
    def register_agent(self, callsign: str, faction: str = "COSMIC") -> Dict[str, Any]:
        """Register a new agent."""
        data = {"symbol": callsign, "faction": faction}
        return self._make_request("POST", "/v2/register", json=data)
    
    # Contract endpoints
    
    def get_my_contracts(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """Get the agent's contracts."""
        params = {"page": page, "limit": limit}
        return self._make_request("GET", "/v2/my/contracts", params=params)
    
    def get_contract(self, contract_id: str) -> Dict[str, Any]:
        """Get a specific contract by ID."""
        return self._make_request("GET", f"/v2/my/contracts/{contract_id}")
    
    def accept_contract(self, contract_id: str) -> Dict[str, Any]:
        """Accept a contract."""
        return self._make_request("POST", f"/v2/my/contracts/{contract_id}/accept")
    
    def fulfill_contract(self, contract_id: str) -> Dict[str, Any]:
        """Fulfill a contract."""
        return self._make_request("POST", f"/v2/my/contracts/{contract_id}/fulfill")
    
    def deliver_contract_goods(self, contract_id: str, ship_symbol: str, trade_symbol: str, units: int) -> Dict[str, Any]:
        """Deliver goods for a contract."""
        data = {
            "shipSymbol": ship_symbol,
            "tradeSymbol": trade_symbol,
            "units": units
        }
        return self._make_request("POST", f"/v2/my/contracts/{contract_id}/deliver", json=data)
    
    # Ship endpoints
    
    def get_my_ships(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """Get the agent's ships."""
        params = {"page": page, "limit": limit}
        return self._make_request("GET", "/v2/my/ships", params=params)
    
    def get_ship(self, ship_symbol: str) -> Dict[str, Any]:
        """Get a specific ship by symbol."""
        return self._make_request("GET", f"/v2/my/ships/{ship_symbol}")
    
    def get_ship_cargo(self, ship_symbol: str) -> Dict[str, Any]:
        """Get a ship's cargo."""
        return self._make_request("GET", f"/v2/my/ships/{ship_symbol}/cargo")
    
    def orbit_ship(self, ship_symbol: str) -> Dict[str, Any]:
        """Put a ship in orbit."""
        return self._make_request("POST", f"/v2/my/ships/{ship_symbol}/orbit")
    
    def dock_ship(self, ship_symbol: str) -> Dict[str, Any]:
        """Dock a ship."""
        return self._make_request("POST", f"/v2/my/ships/{ship_symbol}/dock")
    
    def navigate_ship(self, ship_symbol: str, waypoint_symbol: str) -> Dict[str, Any]:
        """Navigate a ship to a waypoint."""
        data = {"waypointSymbol": waypoint_symbol}
        return self._make_request("POST", f"/v2/my/ships/{ship_symbol}/navigate", json=data)
    
    def refuel_ship(self, ship_symbol: str, units: Optional[int] = None, from_cargo: bool = False) -> Dict[str, Any]:
        """Refuel a ship."""
        data = {}
        if units is not None:
            data["units"] = units
        if from_cargo:
            data["fromCargo"] = from_cargo
        return self._make_request("POST", f"/v2/my/ships/{ship_symbol}/refuel", json=data)
    
    def purchase_cargo(self, ship_symbol: str, trade_symbol: str, units: int) -> Dict[str, Any]:
        """Purchase cargo for a ship."""
        data = {"symbol": trade_symbol, "units": units}
        return self._make_request("POST", f"/v2/my/ships/{ship_symbol}/purchase", json=data)
    
    def sell_cargo(self, ship_symbol: str, trade_symbol: str, units: int) -> Dict[str, Any]:
        """Sell cargo from a ship."""
        data = {"symbol": trade_symbol, "units": units}
        return self._make_request("POST", f"/v2/my/ships/{ship_symbol}/sell", json=data)
    
    # System and waypoint endpoints
    
    def get_system(self, system_symbol: str) -> Dict[str, Any]:
        """Get system information."""
        return self._make_request("GET", f"/v2/systems/{system_symbol}")
    
    def get_system_waypoints(self, system_symbol: str, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """Get waypoints in a system."""
        params = {"page": page, "limit": limit}
        return self._make_request("GET", f"/v2/systems/{system_symbol}/waypoints", params=params)
    
    def get_waypoint(self, system_symbol: str, waypoint_symbol: str) -> Dict[str, Any]:
        """Get waypoint information."""
        return self._make_request("GET", f"/v2/systems/{system_symbol}/waypoints/{waypoint_symbol}")
    
    def get_market(self, system_symbol: str, waypoint_symbol: str) -> Dict[str, Any]:
        """Get market information for a waypoint."""
        return self._make_request("GET", f"/v2/systems/{system_symbol}/waypoints/{waypoint_symbol}/market")
    
    def get_shipyard(self, system_symbol: str, waypoint_symbol: str) -> Dict[str, Any]:
        """Get shipyard information for a waypoint."""
        return self._make_request("GET", f"/v2/systems/{system_symbol}/waypoints/{waypoint_symbol}/shipyard")
    
    # Utility methods
    
    def extract_system_from_waypoint(self, waypoint_symbol: str) -> str:
        """Extract system symbol from waypoint symbol (e.g., 'X1-DF55-20250Z' -> 'X1-DF55')."""
        parts = waypoint_symbol.split('-')
        return f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else waypoint_symbol