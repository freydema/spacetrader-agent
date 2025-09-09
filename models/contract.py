"""
Data models for contracts.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class ContractType(Enum):
    """Contract types."""
    PROCUREMENT = "PROCUREMENT"
    TRANSPORT = "TRANSPORT"
    SHUTTLE = "SHUTTLE"


class ContractStatus(Enum):
    """Contract status."""
    AVAILABLE = "AVAILABLE"
    ACCEPTED = "ACCEPTED"
    FULFILLED = "FULFILLED"
    FAILED = "FAILED"


@dataclass
class ContractDelivery:
    """Contract delivery requirement."""
    trade_symbol: str
    destination_symbol: str
    units_required: int
    units_fulfilled: int = 0
    
    @property
    def is_completed(self) -> bool:
        """Check if delivery is completed."""
        return self.units_fulfilled >= self.units_required
    
    @property
    def remaining_units(self) -> int:
        """Get remaining units to deliver."""
        return max(0, self.units_required - self.units_fulfilled)
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ContractDelivery':
        """Create ContractDelivery from API response."""
        return cls(
            trade_symbol=data.get('tradeSymbol', ''),
            destination_symbol=data.get('destinationSymbol', ''),
            units_required=data.get('unitsRequired', 0),
            units_fulfilled=data.get('unitsFulfilled', 0)
        )


@dataclass
class ContractTerms:
    """Contract terms and payments."""
    deadline: datetime
    payment_on_accepted: int
    payment_on_fulfilled: int
    deliveries: List[ContractDelivery]
    
    @property
    def total_payment(self) -> int:
        """Get total payment for the contract."""
        return self.payment_on_accepted + self.payment_on_fulfilled
    
    @property
    def is_expired(self) -> bool:
        """Check if contract is expired."""
        return datetime.now() > self.deadline
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ContractTerms':
        """Create ContractTerms from API response."""
        deadline_str = data.get('deadline', '')
        deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00')) if deadline_str else datetime.now()
        
        deliveries = [
            ContractDelivery.from_api_response(delivery)
            for delivery in data.get('deliver', [])
        ]
        
        return cls(
            deadline=deadline,
            payment_on_accepted=data.get('payment', {}).get('onAccepted', 0),
            payment_on_fulfilled=data.get('payment', {}).get('onFulfilled', 0),
            deliveries=deliveries
        )


@dataclass
class Contract:
    """Contract data model."""
    contract_id: str
    faction_symbol: str
    contract_type: ContractType
    terms: ContractTerms
    accepted: bool = False
    fulfilled: bool = False
    expiration: Optional[datetime] = None
    
    @property
    def status(self) -> ContractStatus:
        """Get contract status."""
        if self.fulfilled:
            return ContractStatus.FULFILLED
        elif self.accepted:
            return ContractStatus.ACCEPTED
        elif self.is_expired:
            return ContractStatus.FAILED
        else:
            return ContractStatus.AVAILABLE
    
    @property
    def is_expired(self) -> bool:
        """Check if contract is expired."""
        if self.expiration:
            return datetime.now() > self.expiration
        return self.terms.is_expired
    
    @property
    def all_deliveries_completed(self) -> bool:
        """Check if all deliveries are completed."""
        return all(delivery.is_completed for delivery in self.terms.deliveries)
    
    def calculate_profitability_score(self, cargo_capacity: int, estimated_costs: int = 0) -> float:
        """
        Calculate a profitability score for this contract.
        
        Args:
            cargo_capacity: Available cargo capacity
            estimated_costs: Estimated costs for fulfilling the contract
            
        Returns:
            Float score (higher is better, negative means unprofitable)
        """
        if self.is_expired:
            return -1000.0  # Heavily penalize expired contracts
        
        total_units_needed = sum(delivery.remaining_units for delivery in self.terms.deliveries)
        
        if total_units_needed > cargo_capacity:
            return -500.0  # Cannot fulfill with available capacity
        
        profit = self.terms.total_payment - estimated_costs
        
        if profit <= 0:
            return -100.0  # Unprofitable
        
        # Score based on profit per unit and profit margin
        profit_per_unit = profit / max(1, total_units_needed)
        profit_margin = profit / max(1, self.terms.total_payment)
        
        # Time factor - prefer contracts with more time remaining
        time_remaining = (self.terms.deadline - datetime.now()).total_seconds()
        time_factor = min(1.0, time_remaining / 86400)  # Normalize to 1 day
        
        score = profit_per_unit * profit_margin * time_factor * 100
        return score
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Contract':
        """Create Contract from API response."""
        contract_type_str = data.get('type', 'PROCUREMENT')
        try:
            contract_type = ContractType(contract_type_str)
        except ValueError:
            contract_type = ContractType.PROCUREMENT
        
        terms = ContractTerms.from_api_response(data.get('terms', {}))
        
        expiration_str = data.get('expiration')
        expiration = None
        if expiration_str:
            expiration = datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
        
        return cls(
            contract_id=data.get('id', ''),
            faction_symbol=data.get('factionSymbol', ''),
            contract_type=contract_type,
            terms=terms,
            accepted=data.get('accepted', False),
            fulfilled=data.get('fulfilled', False),
            expiration=expiration
        )