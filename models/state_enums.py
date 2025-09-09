"""
Enumerations for agent states.
"""

from enum import Enum


class AgentState(Enum):
    """Enumeration of all possible agent states."""
    INITIALIZE = "initialize"
    ASSESS_SITUATION = "assess_situation"
    NEGOTIATE_CONTRACT = "negotiate_contract"
    ACCEPT_CONTRACT = "accept_contract"
    PLAN_FULFILLMENT = "plan_fulfillment"
    ACQUIRE_RESOURCES = "acquire_resources"
    EXECUTE_CONTRACT = "execute_contract"
    DELIVER_GOODS = "deliver_goods"
    COMPLETE_CONTRACT = "complete_contract"
    EVALUATE_PERFORMANCE = "evaluate_performance"
    ERROR_RECOVERY = "error_recovery"