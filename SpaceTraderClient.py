import os
from typing import Optional, Dict, Any
import logging
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # default, can be overridden by app config

class SpaceTraderClient:
    """
       Thin client for the SpaceTraders API.
       - No persistent Session, just plain requests.
       - Centralizes headers, tokens, and error handling.
       """

    def __init__(
            self,
            account_token: Optional[str] = None,
            agent_token: Optional[str] = None,
            base_url: str = "https://api.spacetraders.io",
            timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.account_token = account_token or os.getenv("ACCOUNT_TOKEN")
        self.agent_token = agent_token or os.getenv("AGENT_TOKEN")

    # ---------- public API ----------

    def register_agent(self, callsign: str, faction: str) -> Dict[str, Any]:
        """POST /v2/register"""
        payload = {"symbol": callsign, "faction": faction}
        return self._send_request("POST", "/v2/register", json=payload, token=self.account_token)

    def get_my_agent(self) -> Dict[str, Any]:
        """GET /v2/my/agent"""
        return self._send_request("GET", "/v2/my/agent", token=self.agent_token)

    def get_waypoint_info(self, waypoint_symbol: str) -> Dict[str, Any]:
        """GET /v2/systems/system_symbol/waypoints/waypoint_symbol"""
        system_symbol = "-".join(waypoint_symbol.split("-")[:2])
        path = f"/v2/systems/{system_symbol}/waypoints/{waypoint_symbol}"
        return self._send_request("GET", path)

    def get_my_contracts(self):
        """GET /v2/my/contracts"""
        return self._send_request("GET", path="/v2/my/contracts", token=self.agent_token)

    def get_my_ships(self):
        """GET /v2/my/ships"""
        return self._send_request("GET", path="/v2/my/ships", token=self.agent_token)

    def negotiate_new_contract(self, ship_symbol:str):
        """POST /v2/my/ships/:shipSymbol/negotiate/contract"""
        path = f"/v2/my/ships/{ship_symbol}/negotiate/contract"
        return self._send_request("POST", path=path, json={}, token=self.agent_token)

    def accept_contract(self, contract_id:str):
        """POST /v2/my/contracts/:contractId/accept"""
        path = f"/v2/my/contracts/{contract_id}/accept"
        return self._send_request("POST", path=path, json={}, token=self.agent_token)

    # ---------- internals ----------

    def _send_request(
            self,
            method: str,
            path: str,
            token: Optional[str] = None,
            **kwargs: Any,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Content-Type", "application/json")

        logger.info(">> %s %s", method, url)
        # logger.("Headers: %s | Payload: %s", headers, kwargs.get("json") or kwargs.get("data"))

        resp = requests.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        # Parse JSON safely
        try:
            data = resp.json()
            logger.debug("<< Response %s: %s", resp.status_code, resp.text)
        except ValueError:
            logger.debug("<< Response %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
            raise
        if not resp.ok:
            logger.error("Request failed [%s]: %s", resp.status_code, resp.text)
            msg = f"{resp.status_code} {resp.reason}: {resp.text}"
            raise requests.HTTPError(msg, response=resp)
        return data
