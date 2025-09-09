"""
Data models for agent information and shared context.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime

from api.client import SpaceTradersAPIClient


@dataclass
class AgentData:
    """Data model for agent information."""
    account_id: str
    symbol: str
    headquarters: str
    credits: int
    starting_faction: str
    ship_count: int = 0
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'AgentData':
        """Create AgentData from API response."""
        return cls(
            account_id=data.get('accountId', ''),
            symbol=data.get('symbol', ''),
            headquarters=data.get('headquarters', ''),
            credits=data.get('credits', 0),
            starting_faction=data.get('startingFaction', ''),
            ship_count=data.get('shipCount', 0)
        )


@dataclass
class PerformanceMetrics:
    """Performance tracking metrics for the agent."""
    contracts_completed: int = 0
    total_credits_earned: int = 0
    total_execution_time: float = 0.0
    errors_encountered: int = 0
    contracts_failed: int = 0
    average_contract_completion_time: float = 0.0
    last_contract_profit: int = 0
    
    def calculate_efficiency(self) -> float:
        """Calculate contracts completed per hour."""
        if self.total_execution_time > 0:
            return self.contracts_completed / (self.total_execution_time / 3600)
        return 0.0
    
    def log_contract_completion(self, profit: int, completion_time: float) -> None:
        """Log a completed contract."""
        self.contracts_completed += 1
        self.total_credits_earned += profit
        self.last_contract_profit = profit
        
        # Update average completion time
        total_time = self.average_contract_completion_time * (self.contracts_completed - 1) + completion_time
        self.average_contract_completion_time = total_time / self.contracts_completed


@dataclass
class AgentContext:
    """
    Shared context passed to all states.
    
    Contains all data and resources needed by states to execute their logic.
    """
    api_client: SpaceTradersAPIClient
    logger: logging.Logger
    agent_data: Optional[AgentData] = None
    current_contract: Optional['Contract'] = None
    ships: List['Ship'] = field(default_factory=list)
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    strategy_config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default strategy configuration."""
        if not self.strategy_config:
            self.strategy_config = {
                'min_profit_margin': 0.1,  # 10% minimum profit margin
                'max_contract_duration': 3600,  # 1 hour max contract duration
                'safety_credit_reserve': 10000,  # Keep 10k credits in reserve
                'max_ships': 5,  # Maximum number of ships to own
                'preferred_contract_types': ['PROCUREMENT', 'TRANSPORT'],
                'risk_tolerance': 'MEDIUM'
            }
    
    def update_agent_data(self, api_response: Dict[str, Any]) -> None:
        """Update agent data from API response."""
        if 'data' in api_response:
            self.agent_data = AgentData.from_api_response(api_response['data'])
    
    def has_sufficient_credits(self, amount: int) -> bool:
        """Check if agent has sufficient credits for an operation."""
        if not self.agent_data:
            return False
        available = self.agent_data.credits - self.strategy_config['safety_credit_reserve']
        return available >= amount
    
    def get_total_cargo_capacity(self) -> int:
        """Get total cargo capacity across all ships."""
        return sum(ship.cargo_capacity for ship in self.ships)
    
    def get_available_cargo_space(self) -> int:
        """Get available cargo space across all ships."""
        return sum(ship.get_available_cargo_space() for ship in self.ships)
    
    def log_performance_summary(self) -> None:
        """Log current performance metrics."""
        metrics = self.performance_metrics
        self.logger.info("=== PERFORMANCE SUMMARY ===")
        self.logger.info(f"Contracts completed: {metrics.contracts_completed}")
        self.logger.info(f"Contracts failed: {metrics.contracts_failed}")
        self.logger.info(f"Total credits earned: {metrics.total_credits_earned}")
        self.logger.info(f"Current credits: {self.agent_data.credits if self.agent_data else 0}")
        self.logger.info(f"Last contract profit: {metrics.last_contract_profit}")
        self.logger.info(f"Efficiency: {metrics.calculate_efficiency():.2f} contracts/hour")
        self.logger.info(f"Errors encountered: {metrics.errors_encountered}")


# Import here to avoid circular imports
from .contract import Contract  # noqa: E402
from .ship import Ship  # noqa: E402