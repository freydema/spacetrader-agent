"""
Base state class for the SpaceTraders agent state machine.
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from models.agent_data import AgentContext
    from models.state_enums import AgentState


class BaseState(ABC):
    """
    Abstract base class for all agent states.
    
    Each state receives a shared context containing agent data, API client,
    and other resources needed for execution.
    """
    
    def __init__(self, context: 'AgentContext'):
        """
        Initialize the state with shared context.
        
        Args:
            context: Shared agent context containing API client, data, and resources
        """
        self.context = context
        self.logger = context.logger
        self.api_client = context.api_client
    
    @abstractmethod
    def execute(self) -> Optional['AgentState']:
        """
        Execute the state's logic and return the next state.
        
        Returns:
            Optional[AgentState]: Next state to transition to, or None to stay in current state
            
        Raises:
            Exception: Any error during state execution should be caught by the main loop
        """
        pass
    
    def log_state_entry(self) -> None:
        """Log entry into this state."""
        state_name = self.__class__.__name__.replace('State', '').upper()
        self.logger.info(f"Entering state: {state_name}")
    
    def log_state_exit(self, next_state: Optional['AgentState']) -> None:
        """Log exit from this state."""
        state_name = self.__class__.__name__.replace('State', '').upper()
        if next_state:
            self.logger.info(f"Exiting {state_name} -> {next_state.value.upper()}")
        else:
            self.logger.debug(f"Staying in {state_name}")