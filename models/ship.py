"""
Data models for ships and cargo.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class ShipNavStatus(Enum):
    """Ship navigation status."""
    IN_TRANSIT = "IN_TRANSIT"
    IN_ORBIT = "IN_ORBIT"
    DOCKED = "DOCKED"


class ShipRole(Enum):
    """Ship roles."""
    COMMAND = "COMMAND"
    TRANSPORT = "TRANSPORT"
    PATROL = "PATROL"
    SURVEYOR = "SURVEYOR"
    EXCAVATOR = "EXCAVATOR"
    INTERCEPTOR = "INTERCEPTOR"
    REFINERY = "REFINERY"


@dataclass
class ShipCargoItem:
    """Item in ship cargo."""
    symbol: str
    name: str
    description: str
    units: int
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ShipCargoItem':
        """Create ShipCargoItem from API response."""
        return cls(
            symbol=data.get('symbol', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            units=data.get('units', 0)
        )


@dataclass
class ShipCargo:
    """Ship cargo information."""
    capacity: int
    units: int
    inventory: List[ShipCargoItem] = field(default_factory=list)
    
    @property
    def available_space(self) -> int:
        """Get available cargo space."""
        return self.capacity - self.units
    
    @property
    def is_full(self) -> bool:
        """Check if cargo is full."""
        return self.units >= self.capacity
    
    def get_item_quantity(self, symbol: str) -> int:
        """Get quantity of a specific item."""
        for item in self.inventory:
            if item.symbol == symbol:
                return item.units
        return 0
    
    def has_item(self, symbol: str, quantity: int = 1) -> bool:
        """Check if cargo has sufficient quantity of an item."""
        return self.get_item_quantity(symbol) >= quantity
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ShipCargo':
        """Create ShipCargo from API response."""
        inventory = [
            ShipCargoItem.from_api_response(item_data)
            for item_data in data.get('inventory', [])
        ]
        
        return cls(
            capacity=data.get('capacity', 0),
            units=data.get('units', 0),
            inventory=inventory
        )


@dataclass
class ShipNav:
    """Ship navigation information."""
    system_symbol: str
    waypoint_symbol: str
    route: Dict[str, Any]
    status: ShipNavStatus
    flight_mode: str = "CRUISE"
    
    @property
    def is_in_transit(self) -> bool:
        """Check if ship is in transit."""
        return self.status == ShipNavStatus.IN_TRANSIT
    
    @property
    def is_docked(self) -> bool:
        """Check if ship is docked."""
        return self.status == ShipNavStatus.DOCKED
    
    @property
    def is_in_orbit(self) -> bool:
        """Check if ship is in orbit."""
        return self.status == ShipNavStatus.IN_ORBIT
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ShipNav':
        """Create ShipNav from API response."""
        status_str = data.get('status', 'IN_ORBIT')
        try:
            status = ShipNavStatus(status_str)
        except ValueError:
            status = ShipNavStatus.IN_ORBIT
        
        return cls(
            system_symbol=data.get('systemSymbol', ''),
            waypoint_symbol=data.get('waypointSymbol', ''),
            route=data.get('route', {}),
            status=status,
            flight_mode=data.get('flightMode', 'CRUISE')
        )


@dataclass
class ShipFuel:
    """Ship fuel information."""
    current: int
    capacity: int
    consumed: Dict[str, int] = field(default_factory=dict)
    
    @property
    def percentage(self) -> float:
        """Get fuel percentage."""
        if self.capacity == 0:
            return 0.0
        return (self.current / self.capacity) * 100
    
    @property
    def is_full(self) -> bool:
        """Check if fuel is full."""
        return self.current >= self.capacity
    
    @property
    def needs_refuel(self) -> bool:
        """Check if ship needs refueling (less than 25%)."""
        return self.percentage < 25.0
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'ShipFuel':
        """Create ShipFuel from API response."""
        return cls(
            current=data.get('current', 0),
            capacity=data.get('capacity', 0),
            consumed=data.get('consumed', {})
        )


@dataclass
class Ship:
    """Ship data model."""
    symbol: str
    registration: Dict[str, Any]
    nav: ShipNav
    crew: Dict[str, Any]
    frame: Dict[str, Any]
    reactor: Dict[str, Any]
    engine: Dict[str, Any]
    modules: List[Dict[str, Any]]
    mounts: List[Dict[str, Any]]
    cargo: ShipCargo
    fuel: ShipFuel
    
    @property
    def role(self) -> ShipRole:
        """Get ship role from registration."""
        role_str = self.registration.get('role', 'COMMAND')
        try:
            return ShipRole(role_str)
        except ValueError:
            return ShipRole.COMMAND
    
    @property
    def cargo_capacity(self) -> int:
        """Get cargo capacity."""
        return self.cargo.capacity
    
    def get_available_cargo_space(self) -> int:
        """Get available cargo space."""
        return self.cargo.available_space
    
    @property
    def is_at_waypoint(self) -> bool:
        """Check if ship is at a waypoint (docked or in orbit)."""
        return self.nav.status in [ShipNavStatus.DOCKED, ShipNavStatus.IN_ORBIT]
    
    def can_carry_cargo(self, units: int) -> bool:
        """Check if ship can carry additional cargo."""
        return self.get_available_cargo_space() >= units
    
    def is_suitable_for_contract(self, contract: 'Contract') -> bool:
        """Check if ship is suitable for a contract."""
        # Check if ship has enough cargo capacity for any single delivery
        max_delivery = max(
            (delivery.remaining_units for delivery in contract.terms.deliveries),
            default=0
        )
        return self.cargo_capacity >= max_delivery
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Ship':
        """Create Ship from API response."""
        nav_data = data.get('nav', {})
        cargo_data = data.get('cargo', {})
        fuel_data = data.get('fuel', {})
        
        return cls(
            symbol=data.get('symbol', ''),
            registration=data.get('registration', {}),
            nav=ShipNav.from_api_response(nav_data),
            crew=data.get('crew', {}),
            frame=data.get('frame', {}),
            reactor=data.get('reactor', {}),
            engine=data.get('engine', {}),
            modules=data.get('modules', []),
            mounts=data.get('mounts', []),
            cargo=ShipCargo.from_api_response(cargo_data),
            fuel=ShipFuel.from_api_response(fuel_data)
        )


# Import to avoid circular import
from .contract import Contract  # noqa: E402